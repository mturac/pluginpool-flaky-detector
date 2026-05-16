# flaky-detector — examples

Each scenario shows: a test command, the number of runs, and the kind of report `flaky-detector` produces.

---

## Scenario 1 — pytest, 10 runs

**Command:**

```sh
python3 scripts/flaky.py --cmd "pytest -v" --runs 10 --format md
```

**Sample report** (with a mix of flaky, always-failing, and always-passing tests):

```
# Flaky-detector report (10 runs)

- flaky: **2**  |  always-failing: **1**  |  always-passing: 47

| test | pass | fail | flakiness % |
|---|---|---|---|
| tests/test_payment.py::test_idempotency  | 6 | 4 | 40.0 |
| tests/test_search.py::test_index_warmup  | 8 | 2 | 20.0 |
| tests/test_db.py::test_migration         | 0 | 10 | 100.0 |
```

**Exit code:** `2` (always-failing test present; takes precedence over flaky).

**What Claude does next:**

> The 100%-failing `test_db.py::test_migration` is not flaky — it's broken.
> Fix that first.
>
> `test_idempotency` at 40% flakiness suggests a race or shared state — the
> payment test probably touches a singleton or a DB row by primary key.
> Recommended next step: isolate the test with `pytest-xdist` or check
> for shared fixtures.
>
> `test_index_warmup` at 20% is probably a timing issue — search-index
> warmup usually involves an `await`. Increase the timeout or add a
> readiness probe.

---

## Scenario 2 — Jest

```sh
python3 scripts/flaky.py --cmd "jest --ci" --parser jest --runs 5
```

The parser auto-detects from the command, but you can force it with `--parser`. Supported: `pytest`, `jest`, `gotest`, `tap`.

---

## Scenario 3 — Go tests

```sh
python3 scripts/flaky.py --cmd "go test ./..." --runs 20 --format md
```

---

## Scenario 4 — parallel runs (only when safe!)

If your suite is parallel-clean, this is 4× faster:

```sh
python3 scripts/flaky.py --cmd "pytest -v" --runs 20 --parallel 4 --format md
```

> ⚠ Many test suites are not parallel-safe (shared DB rows, port binds, /tmp races). When in doubt, leave `--parallel` at `1`.

---

## Scenario 5 — `pytest -q` doesn't silently false-green

The most important safety property: if you use `pytest -q` (the default short reporter that doesn't print per-test lines), the helper either:

1. Parses the tail `FAILED path::test` summary lines (for failures it can attribute), or
2. Exits with code `3` and prints a stderr warning telling you to use `-v` instead.

It will **not** report "0 flaky tests" because it failed to parse anything. The test `test_parse_pytest_short_form_summary` covers the first case; the exit-3 path is in `main()`.

---

## Reference: parser shapes

The sample fixture [`sample-pytest-output.txt`](./sample-pytest-output.txt) shows the per-run output the parser expects from pytest. The other parsers (`jest`, `gotest`, `tap`) follow analogous shapes — see the `parse_*` functions in `scripts/flaky.py` for details.
