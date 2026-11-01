from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from promptcheck.assertions import CHECKS
from promptcheck.providers import Provider
from promptcheck.suite import Case, Suite


@dataclass
class Attempt:
    output: str
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass
class CaseResult:
    case_id: str
    attempts: list[Attempt]

    @property
    def pass_rate(self) -> float:
        return sum(a.passed for a in self.attempts) / len(self.attempts)

    @property
    def status(self) -> str:
        """pass / fail / flaky - flaky means the same prompt both passed and failed across repeats."""
        rate = self.pass_rate
        return "pass" if rate == 1 else "fail" if rate == 0 else "flaky"


@dataclass
class RunReport:
    suite: str
    results: list[CaseResult]

    def statuses(self) -> dict[str, str]:
        return {r.case_id: r.status for r in self.results}

    def to_dict(self) -> dict:
        return {"suite": self.suite, "results": [asdict(r) | {"status": r.status} for r in self.results]}


def check(output: str, case: Case, judge: Provider | None) -> Attempt:
    attempt = Attempt(output)
    for a in case.assert_:
        ok, reason = CHECKS[a.type](output, a.value, judge=judge)
        if not ok:
            attempt.failures.append(f"{a.type}: {reason}")
    return attempt


def run_suite(suite: Suite, provider: Provider, judge: Provider | None = None, workers: int = 1) -> RunReport:
    def run_case(case: Case) -> CaseResult:
        user = suite.render(case)
        attempts = [check(provider.complete(suite.system, user), case, judge) for _ in range(suite.repeats)]
        return CaseResult(case.id, attempts)

    # cases run in parallel; repeats within a case stay ordered so record/replay lines up
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run_case, suite.cases))
    return RunReport(suite.name, results)
