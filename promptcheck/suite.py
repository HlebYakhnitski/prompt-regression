"""Suite definition loaded from YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class Assertion(BaseModel):
    type: str
    value: Any = None

    @model_validator(mode="after")
    def _known(self) -> Assertion:
        from promptcheck.assertions import CHECKS

        if self.type not in CHECKS:
            raise ValueError(f"unknown assertion type '{self.type}', expected one of {sorted(CHECKS)}")
        return self


class Case(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    vars: dict[str, str] = Field(default_factory=dict)
    assert_: list[Assertion] = Field(alias="assert", min_length=1)


class Suite(BaseModel):
    name: str
    system: str = ""
    prompt: str
    repeats: int = Field(default=1, ge=1, le=20)
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Suite:
        ids = [c.id for c in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case ids must be unique")
        return self

    def render(self, case: Case) -> str:
        try:
            return self.prompt.format(**case.vars)
        except KeyError as err:
            raise ValueError(f"case '{case.id}' is missing variable {err}") from err


def load_suite(path: Path) -> Suite:
    return Suite.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
