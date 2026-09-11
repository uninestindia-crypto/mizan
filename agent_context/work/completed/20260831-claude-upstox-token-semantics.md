# Active work: Upstox token semantics measured against the live API

STATUS: COMPLETE — measured, recorded, no source change  
OWNER: Claude Code (on founder instruction)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-31T06:13:00Z  
STARTING_REVISION: 56036950dc322a64d43928392e681c9bc3b7942a  
WORKTREE_OR_BRANCH: `D:\quant_system`, branch `main` (install root, no worktree created)

## Objective

The founder asserted that because the pilot places no orders, the daily Upstox access token is
unnecessary — that data fetching and live paper trading could run on a longer-lived "analytics
token" instead. Establish by measurement which Upstox endpoints actually require a bearer token,
and record the answer where the next operator will find it.

**Result in one line: historical bars need no token at all, and the Upstox Analytics Token —
free, one per user, ~1 year — authenticates the live quote feed. The founder's original claim was
correct: live paper trading does not require the nightly-expiring access token.**

## Owned paths

- `agent_context/work/active/20260831-claude-upstox-token-semantics.md` (this file)
- `agent_context/work/active/20260831-NOTICE-paper-pilot-analytics-token-resolution.md`
- `.env.example` (unclaimed; verified against every record in `work/active/` before editing)
- `tests/test_paper_pilot_carried_session.py` (unclaimed; verified the same way)
- `scripts/run_paper_pilot_session.py` — **claimed by Antigravity**, edited on explicit founder
  instruction under the notice above. PROTOCOL 8.4 preconditions were checked first: that record
  states `Blockers and conflicts: None`, its `Next safe action` is reporting, and none of the
  numbers it pins as evidence are affected by which environment variable supplies the token.

## Non-goals

- No fallback quote feed. The pilot still uses Upstox or does not trade.
- No relaxation of the expiry guard. It caught eight days of sessions running on a substitute
  feed and is preserved verbatim in force; it now validates whichever token was selected.
- No edit to `src/quant_system/data/upstox.py`. See "Next safe action" — a real over-restriction
  was found there, and it is not mine to change unilaterally.
- No token value, JWT body, account email, or account holder name is recorded here. The probe
  script printed a profile payload; only the non-identifying findings are carried across.

## Decision rationale

The claim is half right, and the half that is wrong is the half that governs the pilot.

**Right: historical acquisition genuinely needs no token.** Both `v2` and `v3`
`/historical-candle/...` returned HTTP 200 with no `Authorization` header at all.

**Wrong: live paper trading needs the token.** `scripts/run_paper_pilot_session.py:172` calls
`v2/market-quote/quotes`, which is authenticated — 401 `UDAPI100050` without a bearer token. The
reasoning gap is that "places no orders" exempts you from the *order* API, not the *quote* API.
Paper trading still marks positions against a real live price, and reading that price costs a
token. There is no unauthenticated live-quote endpoint, and
`scripts/run_paper_pilot_session.py:145` explicitly refuses a substitute feed.

**Token variables in this repo.** `UPSTOX_ACCESS_TOKEN` is the only one in `src/` and `scripts/`
(26 references; no sibling). That part is measured and stands.

**CORRECTION — an Analytics Token does exist.** This record originally asserted "there is no
analytics token in Upstox". That was **wrong**, twice over. The founder produced the Upstox developer
console, which shows an **Analytics Token** — one per user, no cost, ~1 year validity (console
example: issued 17/07/2026, expires 17/07/2027, with a Revoke control).

The second error compounded the first: I then claimed extended tokens are scoped to
portfolio/order reads and cannot serve market quotes. The supplied analytics token carries an
`isExtended` claim **and** returns HTTP 200 on `v2/market-quote/quotes`. That scoping claim is
also disproved.

Both were asserted from memory rather than measured, and both were written into `.env.example`
and into this record as though established, before the founder corrected them. The lesson is the
one this repository already encodes elsewhere: an unmeasured provider claim is not evidence, and
should not have been committed in the voice of one.

The token in `.env` at the time of measurement was a standard access token, `iat` 2026-08-31
11:35:29 IST, `exp` 2026-09-01 03:30:00 IST. Upstox V2 issues no refresh token, so renewal means
repeating the OAuth login flow each trading day before ~09:15 IST. That is a property of the
provider, not a configuration defect, and no change in this repository avoids it.

Rejected alternative: relaxing the auth gate so the pilot could run tokenless. It cannot — the
quote endpoint is the constraint, not our code.

Incidental correction made while editing `.env.example`: its header claimed "no dotenv
auto-loading". That has been false since `9789fd4` — `src/quant_system/config/env.py` loads the
nearest `.env` into `os.environ` at the launcher entry point. Corrected, because leaving a known
falsehood adjacent to the new text would undermine it.

## Commands and outcomes

Probe script (scratchpad, not committed) reading `.env` and reporting status codes only.

| Probe | Result | Evidence/notes |
|---|---|---|
| decode token claims | PASS | `exp` 2026-09-01 03:30:00 IST; claims `exp, iat, isMultiClient, isPlusPlan, iss, jti, sub`; `iss=udapi-gateway-service` |
| `v3/historical-candle/...` no auth | **HTTP 200** | real INFY candles returned |
| `v3/historical-candle/...` with auth | HTTP 200 | identical payload |
| `v2/historical-candle/...` no auth | **HTTP 200** | real INFY candles returned |
| `v2/historical-candle/...` with auth | HTTP 200 | identical payload |
| `v2/market-quote/ltp` no auth | **HTTP 401** | `UDAPI100050` "Invalid token used to access API" |
| `v2/market-quote/ltp` with auth | HTTP 200 | `last_price` returned |
| `v2/market-quote/quotes` with auth | HTTP 200 | ohlc + depth; this is the pilot's call |
| `v2/user/profile` with auth | HTTP 200 | live account, NSE+BSE, token genuinely valid |

## Files changed

- `.env.example`: recorded the token semantics above at the point of use — no analytics token,
  extended token is scoped to portfolio/order reads, daily 03:30 IST expiry, and the measured
  auth requirement per endpoint. Corrected the stale "no dotenv auto-loading" claim.
- `agent_context/work/active/20260831-claude-upstox-token-semantics.md`: this record.

## Blockers and conflicts

`.env.example` was unclaimed by any record in `work/active/` when edited.

**RESOLVED — the Analytics Token authenticates market quotes.** Measured 2026-08-31 after the
founder supplied it in `.env`. `exp` 2027-08-23 03:30 IST, 356 days of validity remaining; claims
include `isExtended`, `isMultiClient: False`, `isPlusPlan: True`.

| Probe (analytics token) | Result |
|---|---|
| `v2/market-quote/quotes`, 1 instrument | **HTTP 200** |
| `v2/market-quote/quotes`, 10 batched (pilot's real pattern) | **HTTP 200**, all 10 with depth + volume |
| `v2/market-quote/ltp` | HTTP 200 |
| `v3/historical-candle/intraday/.../minutes/1` | HTTP 200 |
| `v2/user/profile` | **HTTP 401 UDAPI1221** — static-IP restricted |

Caveat that must travel with this: `/user/profile` is IP-bound for this token class. Quotes,
batched quotes and intraday candles were unaffected from the development machine, but a deployment
from a different IP must re-run the probe rather than assume.

Incidental `.env` repair: the file briefly held two `UPSTOX_ANALYTICS_TOKEN` lines — the real one
and an 18-character placeholder copied from my own instruction text. The parser takes the last
occurrence, so the placeholder would have won and the probe would have failed misleadingly. The
placeholder line was removed after backing the file up. This is why
`agent_context` documentation for that file now states the last-occurrence-wins rule.

## Phase 2 — wiring the analytics token into the pilot (founder-authorised)

Measuring that the token works changed nothing on its own: `UPSTOX_ANALYTICS_TOKEN` appeared
**zero times** in all Python source, so a valid year-long token in `.env` was invisible and the
session still aborted. Simulated against the unpatched runner:

```
analytics token in env: True
RESULT: session ABORTS -> QuoteFeedError
  UPSTOX_ACCESS_TOKEN expired ... there is no second feed to fall back to.
```

`resolve_upstox_token()` was added, returning both the credential and the name of its source, and
both call sites now use it. The source name is returned rather than discarded so every error names
the variable that failed — an operator with two tokens configured cannot act on a message that
says only "token".

Resolution order: explicit argument, then `UPSTOX_ANALYTICS_TOKEN`, then `UPSTOX_ACCESS_TOKEN`.
The explicit argument is first so `--upstox-token` and `upstox_token=` keep their existing
override behaviour unchanged.

### Verification

| Command | Result | Evidence |
|---|---|---|
| Five-scenario resolution matrix | PASS | expired-access + valid-analytics **PROCEEDS** via `UPSTOX_ANALYTICS_TOKEN`; expired-access alone ABORTS; neither-set ABORTS; malformed analytics ABORTS |
| **End-to-end live fetch, access token removed from env entirely** | **PASS** | `fetch_upstox_live_quotes` returned **8/8** real quotes, `source=UPSTOX_LIVE_FEED` (INFY 1121.1, RELIANCE 1282.4, TCS 2319.5, HDFCBANK 722.3, ICICIBANK 1430.8) |
| `pytest tests/test_paper_pilot_carried_session.py tests/test_research_paper_exemption.py tests/test_paper_pilot.py` | PASS | 69 passed |
| `pytest` (full suite) | PASS | **1178 passed** in 84.57s |
| `ruff check` + `ruff format --check` on both changed files | PASS | All checks passed; 2 files already formatted |
| `mypy scripts/run_paper_pilot_session.py` | UNCHANGED | 15 errors before **and** after; the single non-import error shifted 434 -> 481 purely from added lines. Zero new errors introduced. Pre-existing, and this script is outside the `src/` static gate |

One test required updating: `test_an_expired_token_stops_the_session_at_startup` asserted the
literal string "not set". It now asserts the new message and additionally clears
`UPSTOX_ANALYTICS_TOKEN` — without that the assertion's outcome would depend on whether the
developer's own `.env` happened to hold one. Four new assertions cover analytics preference over
an expired access token, the access-token-only abort path, explicit-argument override, and an
expired *analytics* token still being refused rather than waved through for being the preferred
class.

## Stop point

`.env.example`, `scripts/run_paper_pilot_session.py`, `tests/test_paper_pilot_carried_session.py`
and two `agent_context` records written. Full suite green at 1178. Nothing committed; the working
tree carries the change.

## Next safe action

Tomorrow's session is the real test. It will select `UPSTOX_ANALYTICS_TOKEN` and log
`Upstox token source UPSTOX_ANALYTICS_TOKEN, valid until 2027-08-23 03:30 IST`. If it instead logs
`UPSTOX_ACCESS_TOKEN`, the analytics variable was not loaded and the resolution order should be
checked before the access token is refreshed — refreshing it would mask the fault.

Then, separately: `src/quant_system/data/upstox.py:119` returns `PROVIDER_UNAUTHORIZED` before issuing the historical
request, so bar ingestion fails without a token even though the endpoint demonstrably does not need
one (two 200s above). That is a real over-restriction and it makes the daily pipeline fall back to
synthetic bars in a case where real bars were available.

Fixing it means letting `acquire_historical_daily` proceed unauthenticated and mapping a genuine
provider 401 to `PROVIDER_UNAUTHORIZED` on the response instead of pre-empting it. That path is
governed acquisition and carries evidence implications, so it needs its own record and its own
adjudication rather than being folded into this one.
