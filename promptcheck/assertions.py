"""Checks applied to one model output. Each returns (passed, reason)."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import jsonschema

Result = tuple[bool, str]


def _json(output: str) -> Any:
    text = output.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)   # tolerate a fenced block
    return json.loads(fence.group(1) if fence else text)


def contains(output: str, value: str, **_) -> Result:
    return (value.lower() in output.lower(), f"expected to contain {value!r}")


def not_contains(output: str, value: str, **_) -> Result:
    return (value.lower() not in output.lower(), f"must not contain {value!r}")


def regex(output: str, value: str, **_) -> Result:
    return (re.search(value, output, re.S) is not None, f"expected to match /{value}/")


def max_chars(output: str, value: int, **_) -> Result:
    return (len(output) <= int(value), f"{len(output)} chars, limit {value}")


def is_json(output: str, value: Any = None, **_) -> Result:
    try:
        _json(output)
        return True, "valid JSON"
    except ValueError as err:
        return False, f"not valid JSON: {err}"


def json_schema(output: str, value: dict, **_) -> Result:
    try:
        jsonschema.validate(_json(output), value)
        return True, "matches schema"
    except ValueError as err:
        return False, f"not valid JSON: {err}"
    except jsonschema.ValidationError as err:
        return False, f"schema: {err.message} at {'/'.join(map(str, err.absolute_path)) or 'root'}"


def json_field(output: str, value: dict, **_) -> Result:
    """``value: {path: "a.b", equals: x}`` - one field of the JSON output must equal x."""
    try:
        node = _json(output)
        for part in value["path"].split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
    except (ValueError, KeyError, IndexError, TypeError) as err:
        return False, f"field {value['path']} not found ({err.__class__.__name__})"
    return (node == value["equals"], f"{value['path']} = {node!r}, expected {value['equals']!r}")


JUDGE_SYSTEM = (
    "You grade an AI assistant's answer against a rubric. Reply with JSON only: "
    '{"pass": true|false, "reason": "<one sentence>"}. Be strict: if the rubric is not fully met, fail it.'
)


def llm_judge(output: str, value: str, judge=None, **_) -> Result:
    if judge is None:
        return False, "llm_judge needs a judge provider (--judge)"
    raw = judge.complete(JUDGE_SYSTEM, f"Rubric:\n{value}\n\nAnswer to grade:\n{output}")
    try:
        verdict = _json(raw)
        return bool(verdict["pass"]), f"judge: {verdict.get('reason', '')}"
    except (ValueError, KeyError, TypeError):
        return False, f"judge returned unparseable verdict: {raw[:80]!r}"


CHECKS: dict[str, Callable[..., Result]] = {
    "contains": contains,
    "not_contains": not_contains,
    "regex": regex,
    "max_chars": max_chars,
    "is_json": is_json,
    "json_schema": json_schema,
    "json_field": json_field,
    "llm_judge": llm_judge,
}
