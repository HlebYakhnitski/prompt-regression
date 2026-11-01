"""Model back-ends. Everything the runner needs is ``complete(system, user) -> str``."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol


class Provider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


def cache_key(system: str, user: str, attempt: int) -> str:
    return hashlib.sha256(json.dumps([system, user, attempt]).encode()).hexdigest()[:16]


class AnthropicProvider:
    def __init__(self, model: str | None = None, max_tokens: int = 800) -> None:
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        response = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in response.content if b.type == "text")


class Cassette:
    """Record real model outputs once, replay them in CI.

    Replay makes the suite deterministic and free to run on every commit; re-record
    deliberately when the prompt or model changes. Each repeat is stored separately so
    flakiness recorded once stays visible on replay.
    """

    def __init__(self, path: Path, inner: Provider | None = None) -> None:
        self.path, self.inner = path, inner
        self.data: dict[str, str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self._attempts: dict[tuple[str, str], int] = {}

    def complete(self, system: str, user: str) -> str:
        attempt = self._attempts.get((system, user), 0)
        self._attempts[(system, user)] = attempt + 1
        key = cache_key(system, user, attempt)
        if key in self.data:
            return self.data[key]
        if self.inner is None:
            raise KeyError(f"no recorded output for this prompt (attempt {attempt}); run with --record")
        self.data[key] = self.inner.complete(system, user)
        return self.data[key]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
