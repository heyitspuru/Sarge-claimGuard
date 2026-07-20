"""ClaimGuard CLI entrypoint: python -m claimguard <subcommand>."""

import argparse
from pathlib import Path

from claimguard import db, icd, llm
from claimguard.eval import runner as eval_runner
from claimguard.synth import denials as gen_denials
from claimguard.synth import generate as gen_data


def _cmd_load_refs(args: argparse.Namespace) -> None:
    conn = db.connect()
    icd.load_refs_into_db(conn)
    print("loaded ICD-10 codes and policy clauses into the database")


def _add_load_refs_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("load-refs", help="Embed ICD-10 codes + policy clauses into the db")
    p.set_defaults(func=_cmd_load_refs)


def _cmd_gen_denials(args: argparse.Namespace) -> None:
    n = gen_denials.generate_denials(Path(args.policies), Path(args.out))
    print(f"generated {n} denial scenarios into {args.out}")


def _add_gen_denials_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("gen-denials", help="Generate the synthetic denials corpus (no LLM)")
    p.add_argument("--policies", type=str, default="data/policies")
    p.add_argument("--out", type=str, default="data/denials")
    p.set_defaults(func=_cmd_gen_denials)


def _cmd_validate_translations(args: argparse.Namespace) -> None:
    from claimguard.comms import backcheck
    summary = backcheck.run_backcheck(llm.complete, artifact=Path(args.artifact),
                                       sidecar=Path(args.sidecar))
    print(f"checked   : {summary['checked']} strings")
    print(f"flagged   : {summary['flagged']} for human review")
    print(f"unchecked : {summary['unchecked']}")
    print(f"artifact  : {summary['artifact']}")
    print(f"sidecar   : {summary['sidecar']}")
    if summary["flagged"]:
        print("\nFlagged strings are meaning-drift candidates — read them before shipping.")
    print("\nNOTE: this screens for meaning drift only. It cannot establish warmth,\n"
          "register or reading level; those still need a native speaker.")


def _add_validate_translations_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("validate-translations",
                       help="Blind back-translation check of patient copy (~4 provider calls)")
    p.add_argument("--artifact", type=str, default="docs/TRANSLATION_BACKCHECK.md")
    p.add_argument("--sidecar", type=str, default="data/translation_checked.json")
    p.set_defaults(func=_cmd_validate_translations)


def _cmd_eval(args: argparse.Namespace) -> None:
    if args.real_report:
        from claimguard.eval import real_run
        real_run.print_real_report(real_run.report_from_checkpoint(Path(args.checkpoint)))
        return

    if args.real_run:
        from claimguard.eval import real_run
        retriever = icd.InMemoryRetriever(icd.load_csv(Path(args.data_dir) / "icd" / "icd10.csv"),
                                           llm.embed)
        summary = real_run.run_incremental(
            Path(args.golden), Path(args.checkpoint), limit=args.limit,
            retrieve=retriever, llm=llm.complete, pause=args.pause,
        )
        print(f"completed this run : {summary['completed_this_run']}")
        print(f"total accumulated  : {summary['total_done']} / {summary['total_available']}")
        print(f"remaining          : {summary['remaining']}")
        if summary["quota_stop"]:
            print("\nStopped on provider quota — this is expected on a free tier and is not\n"
                  "a failure. The unfinished records were left unrecorded; rerun the same\n"
                  "command tomorrow to resume exactly where this left off.")
        return

    if args.negotiation:
        from claimguard.agents.negotiator import draft_appeal
        from claimguard.coverage import PolicyRetriever, load_policies
        from claimguard.eval import grounding
        policies = load_policies(Path(args.policies))
        retriever = PolicyRetriever(policies, llm.embed)
        report = grounding.run_negotiation_eval(
            Path(args.denials),
            negotiator=lambda s: draft_appeal(s, retriever, llm.complete),
            policies_dir=Path(args.policies),
        )
        grounding.print_negotiation_report(report)
        return

    if args.packaging_check:
        report = eval_runner.run_packaging_check(Path(args.golden))
        print(f"packaging_validity (packager isolation, ready+rejected subset): "
              f"{report['packaging_validity']:.3f}  over {report['n']} records")
        return

    pipeline = None
    if args.pipeline:
        retriever = icd.InMemoryRetriever(icd.load_csv(Path(args.data_dir) / "icd" / "icd10.csv"),
                                           llm.embed)
        pipeline = eval_runner.make_pipeline(retriever, llm.complete)
    report = eval_runner.run_eval(Path(args.golden), pipeline=pipeline)
    eval_runner.print_report(report)


def _add_eval_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("eval", help="Run the eval harness against a golden dir")
    p.add_argument("--golden", type=str, default="data/golden")
    p.add_argument("--data-dir", type=str, default="data",
                    help="Root data dir (for --pipeline, to locate icd/icd10.csv)")
    p.add_argument("--pipeline", action="store_true",
                    help="Run the real orchestrator pipeline instead of the null baseline")
    p.add_argument("--packaging-check", action="store_true",
                    help="Run the packager-isolation DoD gate (no LLM): packaging validity "
                         "on the ready+rejected golden subset, must be 1.0")
    p.add_argument("--negotiation", action="store_true",
                    help="Run the Negotiator grounding eval over the denials corpus")
    p.add_argument("--denials", type=str, default="data/denials")
    p.add_argument("--policies", type=str, default="data/policies")
    p.add_argument("--real-run", action="store_true",
                    help="Resumable real-provider run: process --limit unprocessed golden "
                         "records and append to the checkpoint. Safe to stop on quota.")
    p.add_argument("--real-report", action="store_true",
                    help="Aggregate metrics + failure taxonomy from the accumulated checkpoint")
    p.add_argument("--checkpoint", type=str, default="data/eval_runs/pipeline_real.jsonl")
    p.add_argument("--limit", type=int, default=10,
                    help="Max records to process in this --real-run invocation")
    p.add_argument("--pause", type=float, default=0.0,
                    help="Seconds to sleep between records (pace under a per-minute limit)")
    p.set_defaults(func=_cmd_eval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimguard")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_data.add_subparser(sub)
    _add_load_refs_subparser(sub)
    _add_gen_denials_subparser(sub)
    _add_eval_subparser(sub)
    _add_validate_translations_subparser(sub)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
