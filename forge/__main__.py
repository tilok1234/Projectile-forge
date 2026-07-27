"""CLI: python3 -m forge build [--out DIR] | validate [--pack DIR]"""

from __future__ import annotations

import argparse
import json
import sys

from . import build, validate

DEFAULT_OUT = "dist/projectileforge"


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="forge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_build = sub.add_parser("build", help="render the pack + manifest + report + preview")
    p_build.add_argument("--out", default=DEFAULT_OUT)
    p_val = sub.add_parser("validate", help="re-audit a pack from disk")
    p_val.add_argument("--pack", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if args.cmd == "build":
        report = build.write_pack(args.out)
        _print_report(report)
        print(f"pack written to {args.out}")
        return 0 if report["pass"] else 1

    manifest, sheets = build.load_pack(args.pack)
    report = validate.validate_pack(manifest, sheets)
    _print_report(report)
    return 0 if report["pass"] else 1


def _print_report(report: dict) -> None:
    for row in report["rows"]:
        mark = "PASS" if row["pass"] else "FAIL"
        print(f"[{mark}] {row['check']:20s} ({row['law']})")
        if not row["pass"]:
            print("       " + json.dumps(row["detail"], sort_keys=True))
    print("verdict:", "PASS" if report["pass"] else "FAIL")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
