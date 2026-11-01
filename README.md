# prompt-regression

Regression tests for LLM prompts. Define cases and assertions in YAML, run them with repeats to catch flaky behaviour, compare against a baseline, and fail CI when a prompt change breaks something that used to work.

The point: "the new prompt is better" usually means "it fixed the cases I was looking at". This tool shows what it broke.

```
$ promptcheck examples/ticket_v2.yaml --cassette examples/cassettes/v2.json --baseline examples/baseline_v1.json

FAIL  double-charge                  0%
       - contains: expected to contain 'twice'
PASS  locked-out                   100%
PASS  pdf-export-bug               100%
PASS  feature-dark-mode            100%
PASS  prompt-injection             100%
PASS  polish-ticket                100%

ticket-triage-v2: 5 pass, 1 fail, 0 flaky

vs baseline: 1 regressed, 2 fixed, 0 new
  REGRESSED double-charge: was pass, now fail
  FIXED     pdf-export-bug
  FIXED     prompt-injection
$ echo $?
1
```

In the example, v2 of a ticket-triage prompt asks for "a single JSON object and nothing else" and tells the model not to follow instructions inside the ticket. That fixes the case where v1 wrapped its JSON in prose, and the prompt-injection case that v1 failed on one of two repeats. But v2 also limits summaries to 40 characters — and the summary for a double charge loses the word "twice". Two fixes, one regression, exit code 1.

## A suite

```yaml
name: ticket-triage-v2
system: |
  You triage customer support tickets. Respond with a single JSON object and nothing else...
repeats: 2                       # run every case twice; mixed results are reported as FLAKY
prompt: |
  Ticket subject: {subject}
  Ticket body: {body}
cases:
  - id: double-charge
    vars: {subject: "Charged twice", body: "I was billed twice for March..."}
    assert:
      - {type: json_schema, value: {type: object, required: [category, priority, summary], ...}}
      - {type: json_field, value: {path: category, equals: billing}}
      - {type: contains, value: twice}
```

| Assertion | Checks |
| --- | --- |
| `contains`, `not_contains` | substring, case-insensitive |
| `regex` | pattern match |
| `max_chars` | output length |
| `is_json` | parses as JSON (a single fenced block is accepted, prose around it is not) |
| `json_schema` | validates against a JSON Schema; the error names the failing path |
| `json_field` | one field, by dotted path (`items.0.name`), equals a value |
| `llm_judge` | a second model grades the output against a rubric; an unparseable verdict fails |

## Record once, replay in CI

Calling a model on every commit is slow, costs money and is non-deterministic. `--record --cassette file.json` runs the suite against the real model and stores every output, keyed by system prompt, rendered user prompt and repeat number. Without `--record`, the cassette is replayed: the suite runs in milliseconds, offline, with the same results every time — including any flakiness that was recorded. Re-record deliberately when the prompt or model changes; a prompt with no recording fails loudly instead of silently calling the API.

```bash
promptcheck suite.yaml --record --cassette cassettes/v3.json --out results/v3.json   # once, with ANTHROPIC_API_KEY
promptcheck suite.yaml --cassette cassettes/v3.json --baseline results/v2.json        # in CI
```

**About the example cassettes:** the outputs in `examples/cassettes/` are hand-written stand-ins for recorded responses (see `examples/make_cassettes.py`), chosen to demonstrate a fix-and-regress scenario. They are not real model outputs.

## Design notes

- **Pass, fail and flaky are different results.** A case that passes one repeat and fails another is neither working nor broken — it is a prompt that depends on sampling luck, and it is reported separately.
- **A regression is any case that was `pass` and is not anymore**, including pass → flaky.
- **The judge fails closed.** If the grading model does not return the expected JSON verdict, the assertion fails rather than passing by default.
- **Cases run in parallel, repeats in order**, so recording and replaying line up.
- **Suites are validated on load** — unknown assertion types, duplicate case ids and missing template variables are errors before anything runs.

## Install and test

```bash
pip install -e ".[dev]"
pytest
```

18 tests: every assertion including fenced JSON, error paths and judge verdicts; pass/fail/flaky classification; template rendering; suite validation; baseline diffs; cassette record-then-replay with separate repeats; and the full CLI example returning exit code 1 on the regression.

## License

MIT
