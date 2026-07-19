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


def _cmd_eval(args: argparse.Namespace) -> None:
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
    p.set_defaults(func=_cmd_eval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimguard")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_data.add_subparser(sub)
    _add_load_refs_subparser(sub)
    _add_gen_denials_subparser(sub)
    _add_eval_subparser(sub)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
