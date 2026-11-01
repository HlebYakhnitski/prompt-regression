"""Build the example cassettes.

The outputs below are HAND-WRITTEN stand-ins for recorded model responses, chosen to
demonstrate the harness: v1 wraps one answer in prose and follows an injected
instruction on one of two repeats; v2's stricter prompt fixes both, but its new
40-character limit drops the word "twice" from one summary - a regression.
Record real outputs with `promptcheck suite.yaml --record --cassette file.json`.
"""
from __future__ import annotations

import json
from pathlib import Path

from promptcheck.providers import cache_key
from promptcheck.suite import load_suite

HERE = Path(__file__).parent


def j(category: str, priority: str, summary: str) -> str:
    return json.dumps({"category": category, "priority": priority, "summary": summary})


OUTPUTS = {
    "v1": {
        "double-charge": [j("billing", "high", "Customer was charged twice for March")] * 2,
        "locked-out": [j("account_access", "high", "Account locked after failed logins")] * 2,
        "pdf-export-bug": ["Here is the triage:\n" + j("bug", "normal", "PDF export is missing the logo")] * 2,
        "feature-dark-mode": [j("feature_request", "low", "Requests a dark mode")] * 2,
        "prompt-injection": [j("other", "low", "Message contains no actual request"), "OK"],
        "polish-ticket": [j("account_access", "high", "Cannot log in: 2FA code not arriving")] * 2,
    },
    "v2": {
        "double-charge": [j("billing", "high", "Duplicate March charge")] * 2,
        "locked-out": [j("account_access", "high", "Account locked out")] * 2,
        "pdf-export-bug": [j("bug", "normal", "PDF export missing logo")] * 2,
        "feature-dark-mode": [j("feature_request", "low", "Dark mode request")] * 2,
        "prompt-injection": [j("other", "low", "No actual request")] * 2,
        "polish-ticket": [j("account_access", "high", "2FA code not arriving")] * 2,
    },
}


def main() -> None:
    for version, outputs in OUTPUTS.items():
        suite = load_suite(HERE / f"ticket_{version}.yaml")
        data = {}
        for case in suite.cases:
            user = suite.render(case)
            for attempt, output in enumerate(outputs[case.id]):
                data[cache_key(suite.system, user, attempt)] = output
        path = HERE / "cassettes" / f"{version}.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {len(data)} outputs to {path}")


if __name__ == "__main__":
    main()
