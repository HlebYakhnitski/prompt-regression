import pytest

from promptcheck.assertions import (
    contains,
    is_json,
    json_field,
    json_schema,
    llm_judge,
    max_chars,
    not_contains,
    regex,
)

SCHEMA = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}


def test_contains_is_case_insensitive():
    assert contains("Charged TWICE", "twice")[0]
    assert not not_contains("Charged twice", "TWICE")[0]


def test_regex_and_length():
    assert regex("code 2FA missing", r"(?i)2fa")[0]
    assert not max_chars("x" * 11, 10)[0]


@pytest.mark.parametrize("text", ['{"a": 1}', '```json\n{"a": 1}\n```', '  {"a": 1}  '])
def test_json_accepts_plain_and_fenced(text):
    assert is_json(text)[0] and json_schema(text, SCHEMA)[0]


def test_json_rejects_prose_wrapped_output():
    ok, reason = is_json('Here you go: {"a": 1}')
    assert not ok and "not valid JSON" in reason


def test_schema_reports_the_failing_path():
    ok, reason = json_schema('{"a": "one"}', SCHEMA)
    assert not ok and "at a" in reason


def test_json_field_nested_and_lists():
    out = '{"items": [{"name": "x"}], "meta": {"ok": true}}'
    assert json_field(out, {"path": "items.0.name", "equals": "x"})[0]
    assert json_field(out, {"path": "meta.ok", "equals": True})[0]
    ok, reason = json_field(out, {"path": "meta.missing", "equals": 1})
    assert not ok and "not found" in reason


class Judge:
    def __init__(self, reply: str):
        self.reply, self.prompts = reply, []

    def complete(self, system, user):
        self.prompts.append(user)
        return self.reply


def test_llm_judge_pass_and_fail():
    assert llm_judge("answer", "be polite", judge=Judge('{"pass": true, "reason": "polite"}'))[0]
    ok, reason = llm_judge("answer", "be polite", judge=Judge('{"pass": false, "reason": "rude"}'))
    assert not ok and "rude" in reason


def test_llm_judge_unparseable_verdict_fails_closed():
    ok, reason = llm_judge("answer", "rubric", judge=Judge("Looks good to me!"))
    assert not ok and "unparseable" in reason


def test_llm_judge_without_judge_fails_with_hint():
    ok, reason = llm_judge("answer", "rubric")
    assert not ok and "--judge" in reason
