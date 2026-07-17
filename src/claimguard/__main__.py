"""ClaimGuard CLI entrypoint: python -m claimguard <subcommand>."""

import argparse

from claimguard.synth import generate as gen_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimguard")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_data.add_subparser(sub)
    # "eval" (Task 8) and "load-refs" (Task 7) subcommands register themselves
    # here via the same add_subparser(sub) pattern once those tasks land.

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
