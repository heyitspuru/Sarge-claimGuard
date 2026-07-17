"""ClaimGuard CLI entrypoint: python -m claimguard <subcommand>."""

import argparse
from pathlib import Path

from claimguard import db, icd
from claimguard.eval import runner as eval_runner
from claimguard.synth import generate as gen_data


def _cmd_load_refs(args: argparse.Namespace) -> None:
    conn = db.connect()
    icd.load_refs_into_db(conn)
    print("loaded ICD-10 codes and policy clauses into the database")


def _add_load_refs_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("load-refs", help="Embed ICD-10 codes + policy clauses into the db")
    p.set_defaults(func=_cmd_load_refs)


def _cmd_eval(args: argparse.Namespace) -> None:
    report = eval_runner.run_eval(Path(args.golden), pipeline=None)
    eval_runner.print_report(report)


def _add_eval_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("eval", help="Run the eval harness against a golden dir")
    p.add_argument("--golden", type=str, default="data/golden")
    p.set_defaults(func=_cmd_eval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimguard")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_data.add_subparser(sub)
    _add_load_refs_subparser(sub)
    _add_eval_subparser(sub)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
