# Mutation Proof - Slice 01

DATE: 2026-08-20  
TARGET: NSE-only `HistoricalDailyRequest` validation  
TEST: `test_request_rejects_non_nse_equity_instrument`

## Mutation

The production regular expression was temporarily weakened from:

```python
re.compile(r"NSE_EQ\|[A-Z0-9]{12}")
```

to:

```python
re.compile(r"(?:NSE|BSE)_EQ\|[A-Z0-9]{12}")
```

## Raw failing output

```text
$ .venv\Scripts\python.exe -m pytest tests/test_upstox_v3_acquisition.py::test_request_rejects_non_nse_equity_instrument -q
collected 1 item

tests\test_upstox_v3_acquisition.py F

E   Failed: DID NOT RAISE ValueError

FAILED tests/test_upstox_v3_acquisition.py::test_request_rejects_non_nse_equity_instrument
1 failed
EXIT=1
```

## Restoration proof

The strict NSE-only expression was restored with `apply_patch`, followed by:

```text
$ .venv\Scripts\python.exe -m pytest tests/test_upstox_v3_acquisition.py::test_request_rejects_non_nse_equity_instrument -q
collected 1 item

tests\test_upstox_v3_acquisition.py .

1 passed
EXIT=0
```

The subsequent full repository suite also passed. This report is revisioned local evidence, not
yet a content-addressed Slice 2 evidence object.

