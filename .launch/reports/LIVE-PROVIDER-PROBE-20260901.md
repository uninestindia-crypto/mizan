# Live provider probe, 2026-09-01

PURPOSE: close round six's largest stated gap. R6-01, R6-02 and R6-15 were proven as **code paths**
and unproven as **provider behaviour**. The report's own remedy: one authenticated ten-instrument
quote request with the raw response inspected.

METHOD: one `GET https://api.upstox.com/v2/market-quote/quotes` with ten NIFTY 50 instrument keys,
authenticated with the analytics token, at approximately 17:00 IST -- after the 15:30 close. No
token value was printed or stored. Run twice, five minutes apart, with identical results.

RUN BY: Claude Code, `20260901-1030Z-claude-seven-item-sweep.md`.

## What was confirmed

| Claim under test | Result |
|---|---|
| The success envelope is `{"status": "success", "data": {...}}` | **CONFIRMED.** `top-level keys: ['data', 'status']`, `status='success'`. R6-01's guard matches the real shape |
| A per-symbol payload carries `last_price` as a number | **CONFIRMED.** Present on 10 of 10, type `float` |
| Zero and missing `last_price` occur | **NOT OBSERVED** in this sample: 0 of 10 zero, 0 of 10 missing. R6-02 remains a code-path finding, not a witnessed one |
| Negative depth prices occur | **NOT OBSERVED.** 0 of 100 levels negative. R6-15's negative bid remains unwitnessed |

## What was discovered, and neither round six nor I had predicted

### 1. The primary instrument-key lookup never matches. It is dead in production.

The request carries the ISIN form and the response is keyed by the symbol form:

```
requested (pipe) keys, e.g.: ['NSE_EQ|INE002A01018', 'NSE_EQ|INE467B01029']
returned keys, e.g.       : ['NSE_EQ:LT', 'NSE_EQ:HDFCBANK']
primary lookup by pipe key hits : 0 of 10
alt lookup by colon key hits    : 10 of 10
```

`payload.get(key) or payload.get(alt_key)` therefore resolves **every quote in the pilot** through
the fallback. The primary branch has never matched a single quote. Nothing is broken today, and the
finding is that a reader tidying away an apparently redundant fallback would silently empty the
book with no error anywhere. Recorded in the code at the lookup, with tests for both forms.

### 2. Zero-priced depth is normal outside market hours, and the old spread was the whole share price

```
depth levels seen        : 100
levels priced at zero    : 90
TOP-of-book at zero      : 10
```

Every one of the ten instruments had a top-of-book bid of `0.0`. The previous computation was
`best_ask - best_bid` with no validation, which gives:

| Symbol | bid | ask | spread, previous code | spread, now |
|---|---:|---:|---:|---:|
| RELIANCE | 0.0 | 1309.0 | **1309.00** | 0.05 |
| TCS | 0.0 | 2369.0 | **2369.00** | 0.05 |
| INFY | 0.0 | 1156.0 | **1156.00** | 0.05 |

**This is not a closed-market curiosity.** That spread builds the simulated order book, and the
pilot's opening fetch runs at **09:00, before the 09:15 open**, when the ladder looks exactly like
this. Every session so far has therefore opened by constructing books whose spread was the entire
share price.

This is stronger evidence for the R6-02/R6-15 repair than the finding that motivated it. Round six
argued from a constructed payload; this is the provider's own response, on an ordinary day,
exhibiting the input the repair was written for.

## Honest limits of this probe

- **One request, ten instruments, after hours.** It does not sample the 09:00 pre-open window, the
  500-name universe, or a chunked 100-symbol request.
- It cannot manufacture the malformed responses R6-01 and R6-02 describe, so those remain proven as
  code paths only. The correct reading is that the guards are *unfalsified*, not *exercised*.
- The token used was the analytics class. A 401 path was not probed because the token was valid.

## What would close the remainder

A 09:02 IST capture of the real 500-name chunked request, with the raw envelope logged, run on a
morning when someone is watching. That samples the pre-open ladder at the size the pilot actually
uses. It is the same one-line addition round six asked for, and it is still worth doing.
