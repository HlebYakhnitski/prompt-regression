import json

import pytest
from pydantic import ValidationError

from promptcheck.cli import main
from promptcheck.compare import diff
from promptcheck.providers import Cassette, cache_key
from promptcheck.runner import run_suite
from promptcheck.suite import Suite


def suite(repeats=1, **extra) -> Suite:
    return Suite.model_validate({
        "name": "s", "system": "sys", "prompt": "Say {word}", "repeats": repeats,
        "cases": [{"id": "c1", "vars": {"word": "hi"}, "assert": [{"type": "contains", "value": "hi"}]}],
        **extra,
    })


class Scripted:
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.outputs.pop(0)


def test_pass_fail_and_flaky():
    assert run_suite(suite(), Scripted("hi there")).results[0].status == "pass"
    assert run_suite(suite(), Scripted("bye")).results[0].status == "fail"
    flaky = run_suite(suite(repeats=2), Scripted("hi", "bye")).results[0]
    assert flaky.status == "flaky" and flaky.pass_rate == 0.5


def test_prompt_is_rendered_with_case_vars():
    provider = Scripted("hi")
    run_suite(suite(), provider)
    assert provider.calls == [("sys", "Say hi")]


def test_missing_variable_is_a_clear_error():
    s = Suite.model_validate({"name": "s", "prompt": "{nope}",
                              "cases": [{"id": "c", "assert": [{"type": "is_json"}]}]})
    with pytest.raises(ValueError, match="missing variable"):
        run_suite(s, Scripted("x"))


def test_suite_validation():
    with pytest.raises(ValidationError, match="unknown assertion"):
        suite(cases=[{"id": "c", "assert": [{"type": "magic"}]}])
    with pytest.raises(ValidationError, match="unique"):
        suite(cases=[{"id": "c", "assert": [{"type": "is_json"}]}] * 2)


def test_diff():
    baseline = {"a": "pass", "b": "fail", "c": "pass", "old": "pass"}
    current = {"a": "flaky", "b": "pass", "c": "pass", "new": "fail"}
    d = diff(baseline, current)
    assert d.regressions == ["a"] and d.fixes == ["b"]
    assert d.new_cases == ["new"] and d.removed_cases == ["old"]
    assert d.has_regressions


def test_cassette_records_each_repeat_then_replays(tmp_path):
    path = tmp_path / "c.json"
    live = Scripted("first", "second")
    rec = Cassette(path, live)
    assert [rec.complete("s", "u"), rec.complete("s", "u")] == ["first", "second"]
    rec.save()

    replay = Cassette(path)                         # no inner provider: replay only
    assert [replay.complete("s", "u"), replay.complete("s", "u")] == ["first", "second"]
    with pytest.raises(KeyError, match="--record"):
        replay.complete("s", "unseen prompt")
    assert set(json.loads(path.read_text())) == {cache_key("s", "u", 0), cache_key("s", "u", 1)}


def test_cli_example_regression_exits_nonzero(tmp_path, capsys):
    ex = "examples"
    base = tmp_path / "base.json"
    assert main([f"{ex}/ticket_v1.yaml", "--cassette", f"{ex}/cassettes/v1.json", "--out", str(base)]) == 0
    code = main([f"{ex}/ticket_v2.yaml", "--cassette", f"{ex}/cassettes/v2.json", "--baseline", str(base)])
    out = capsys.readouterr().out
    assert code == 1
    assert "REGRESSED double-charge" in out and "FIXED     pdf-export-bug" in out
