"""ClaimGuard CLI entrypoint: python -m claimguard <subcommand>."""

import argparse

from claimguard import db, icd
from claimguard.synth import generate as gen_data


def _cmd_load_refs(args: argparse.Namespace) -> None:
    conn = db.connect()
    icd.load_refs_into_db(conn)
    print("loaded ICD-10 codes and policy clauses into the database")


def _add_load_refs_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("load-refs", help="Embed ICD-10 codes + policy clauses into the db")
    p.set_defaults(func=_cmd_load_refs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimguard")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_data.add_subparser(sub)
    _add_load_refs_subparser(sub)
    # "eval" (Task 8) subcommand registers itself here via the same
    # add_subparser(sub) pattern once that task lands.

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
