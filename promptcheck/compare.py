"""Diff a run against a baseline: what broke, what got fixed, what changed stability."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Diff:
    regressions: list[str]     # passed before, fails or is flaky now
    fixes: list[str]           # failed or flaky before, passes now
    new_cases: list[str]
    removed_cases: list[str]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)


def diff(baseline: dict[str, str], current: dict[str, str]) -> Diff:
    shared = baseline.keys() & current.keys()
    return Diff(
        regressions=sorted(c for c in shared if baseline[c] == "pass" and current[c] != "pass"),
        fixes=sorted(c for c in shared if baseline[c] != "pass" and current[c] == "pass"),
        new_cases=sorted(current.keys() - baseline.keys()),
        removed_cases=sorted(baseline.keys() - current.keys()),
    )
