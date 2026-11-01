"""Run a prompt suite.

    promptcheck examples/ticket_summary.yaml --cassette examples/cassettes/v1.json
    promptcheck suite.yaml --record --cassette c.json              # call the real model, save outputs
    promptcheck suite.yaml --cassette c.json --baseline base.json  # exit 1 on regressions
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from promptcheck.compare import diff
from promptcheck.providers import AnthropicProvider, Cassette
from promptcheck.runner import RunReport, run_suite
from promptcheck.suite import load_suite

ICON = {"pass": "PASS ", "fail": "FAIL ", "flaky": "FLAKY"}


def print_report(report: RunReport) -> None:
    for r in report.results:
        print(f"{ICON[r.status]} {r.case_id:<28} {r.pass_rate:>4.0%}")
        if r.status != "pass":
            first_failure = next(a for a in r.attempts if not a.passed)
            for failure in first_failure.failures:
                print(f"       - {failure}")
    counts = {s: sum(r.status == s for r in report.results) for s in ICON}
    print(f"\n{report.suite}: {counts['pass']} pass, {counts['fail']} fail, {counts['flaky']} flaky")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--cassette", type=Path, help="replay recorded outputs from this file")
    parser.add_argument("--record", action="store_true", help="call the real model and save outputs to --cassette")
    parser.add_argument("--judge", action="store_true", help="enable llm_judge assertions (calls the real model)")
    parser.add_argument("--baseline", type=Path, help="report from an earlier run to compare against")
    parser.add_argument("--out", type=Path, help="write this run's report as JSON")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    suite = load_suite(args.suite)
    if args.cassette:
        provider = Cassette(args.cassette, AnthropicProvider() if args.record else None)
    elif args.record:
        parser.error("--record needs --cassette")
    else:
        provider = AnthropicProvider()
    judge = AnthropicProvider() if args.judge else None

    report = run_suite(suite, provider, judge, workers=args.workers)
    if isinstance(provider, Cassette) and args.record:
        provider.save()
    print_report(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    if args.baseline:
        base = {r["case_id"]: r["status"] for r in json.loads(args.baseline.read_text())["results"]}
        d = diff(base, report.statuses())
        print(f"\nvs baseline: {len(d.regressions)} regressed, {len(d.fixes)} fixed, {len(d.new_cases)} new")
        for c in d.regressions:
            print(f"  REGRESSED {c}: was pass, now {report.statuses()[c]}")
        for c in d.fixes:
            print(f"  FIXED     {c}")
        if d.has_regressions:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
