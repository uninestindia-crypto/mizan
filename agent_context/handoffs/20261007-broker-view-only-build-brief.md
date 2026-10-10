# Handoff: build "Broker view", a view-only connection to the person's broker

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code (Opus 5.5). Research and design only; no product code was written  
TO: Sonnet 5.5 (any agent may adopt it)  
DATE_UTC: 2026-10-07T15:40:00Z  
ACTIVE_RECORD: `agent_context/work/completed/20261007-1505Z-claude-broker-view-brief.md` (the design record)  
GOAL_LINE: **G6** (the person sees their real holdings, concentration and cash), with **G1** (fails closed),
**G2** (Mizan can later screen real holdings) and **G4** (every test runs with no broker and no key)  
FOUNDER INSTRUCTION (2026-10-07, chat, faithfully paraphrased): add a read-only direct connection to the user's broker,
so the platform and the platform's AI know where the account stands, without having access to it, at no cost.

---

## 0. Read this first

**What you are building.** The person clicks **Connect Upstox**. Upstox's own sign-in page opens in their browser,
they sign in there, and QuantOS can then show their holdings, open positions and available cash. Every figure carries
the time it was fetched. If the person switches it on, the Copilot can read a summary. Nothing in QuantOS can place,
change or cancel an order, move money, or change an account setting.

**What "view only" means here.** It is three locks, and each must hold even if the other two fail:

1. **The broker's lock.** Since 1 April 2026 Upstox and Zerodha require a static IP registered on the person's
   developer app for order place/modify/cancel calls. Upstox's notice says requests from other addresses "may be
   blocked". Reading needs no static IP. The person leaves that field empty. This is the broker's published rule, not
   something we test, and our code lock must not depend on it. **Never send an order to "check" it.**
2. **Our code's lock.** One new package holds the only broker addresses, as a closed allowlist. Reads go through the
   existing GET-only `HttpTransport` (`src/quant_system/data/upstox_http.py:33`). The two sign-in calls (a POST that
   exchanges the sign-in code, and a DELETE that ends the session) go through a transport that takes no URL at all, so
   it cannot be pointed anywhere else. Tests read the package source and fail on anything outside the allowlist.
3. **The AI's lock.** The Copilot gets a summary through one read-only tool. It never sees the key or any account
   identifier, and the tool is off until the person switches it on. It passes the existing guard tests
   (`tests/test_copilot_tools.py:125`: no tool name may contain `order`, `buy`, `sell`, and the rest).

**Hard rules for this feature. Breaking any one of them is a stop.**

- No order, GTT, position-conversion, payment, pledge/authorise, mutual-fund or order-book/trade-book address, in any
  phase of this brief.
- Never ask for, store or handle a trading PIN, a password or a TOTP secret. Sign-in happens on the broker's page only.
- The view key never goes into `os.environ`, a file, a log, a route response, an error message, an AI prompt, a test
  fixture or a commit.
- No real account data in the repository: fixtures are invented, and records state only totals and match results.
- No new Python or npm dependency in Phase 1. Everything here is standard library (`urllib`, `http.server`, `secrets`,
  `hmac`, `webbrowser`, `sqlite3`) plus what the app already has.
- No background job signs in without the person. Each day the person clicks to connect.

---

## 1. Before you write any code

1. Do the startup sequence in `AGENTS.md`. Then name `GOAL_LINE: G6` in your record.
2. Create your record in the install root **first**:
   `agent_context/work/active/<YYYYMMDD-HHMMZ>-claude-sonnet-broker-view.md`, from `agent_context/templates/work-item.md`,
   listing the owned paths in section 6.
3. **A worktree is recommended.** On 2026-10-07 another agent was committing to `main` in the shared checkout.
   Put the workspace path and branch in your record, then:
   `powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Kind Worktree -Purpose feature -Label broker-view -Branch claude/broker-view`
4. **Claimed paths.** `frontend/**` and `src/quant_system/server/v2/**` are claimed by
   `agent_context/work/active/20260928-claude-retail-redesign-build.md` (`HANDOFF_REQUIRED`). The founder asked for this
   work on 2026-10-07. Before editing those paths, file
   `agent_context/work/active/<date>-NOTICE-broker-view-under-retail-redesign-claim.md` under PROTOCOL section 8.4,
   modelled on `20261007-NOTICE-forward-back-navigation-under-retail-redesign-claim.md`. Never edit their record.
5. Re-check the facts in section 2 against the live Upstox pages. If a path, field or rule differs, stop, write it in
   your record, and design from the live docs, not from this file.
6. Create the decision record `agent_context/decisions/20261007-broker-view-only.md` from Appendix A.
7. Work test-first. Write the tests in section 10, watch them fail, then implement.

---

## 2. Facts this design rests on (checked 2026-10-07)

| Fact | Source (Appendix B) |
|---|---|
| Upstox charges nothing for API access. Brokerage applies only to executed orders, and this feature places none | [U-pricing] |
| Sign-in: the browser opens `GET https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=…&redirect_uri=…&state=…`. Upstox returns to `redirect_uri?code=…&state=…`. The redirect must match the app's registered URL | [U-authorize] |
| Exchange: `POST https://api.upstox.com/v2/login/authorization/token`, form fields `code`, `client_id`, `client_secret`, `redirect_uri`, `grant_type=authorization_code`. The code works once | [U-token] |
| The key **lasts until 3:30 AM IST the next day**, whenever it was made. There is no refresh token | [U-token] |
| The reply also carries profile fields (name, email, user id) and, **for business multi-client apps only**, an `extended_token`. Discard all of it except `access_token` | [U-token], [U-extended] |
| Reads: `GET /v2/portfolio/long-term-holdings`, `GET /v2/portfolio/short-term-positions`, `GET /v2/user/get-funds-and-margin?segment=SEC` | [U-holdings], [U-positions], [U-funds] |
| **The funds service is down every day from 12:00 AM to 5:30 AM IST** | [U-funds] |
| Ending a session: `DELETE https://api.upstox.com/v2/logout` | [U-logout] |
| From 1 April 2026 a static IP is mandatory for Place, Modify, Cancel, Multi and GTT order calls. Other calls are out of scope. **One active API app per user** | [U-mandate], [U-staticip] |
| The one-year **analytics key** is strictly read-only, but holdings, positions, funds and profile need a **whitelisted static IP**. Measured here 2026-08-31: `/v2/user/profile` returned `401 UDAPI1221` with it | [U-analytics]; `agent_context/work/active/20260831-NOTICE-paper-pilot-analytics-token-resolution.md` |
| Upstox accepts `localhost`/`127.0.0.1` redirect URLs for a personal app | [U-localhost] |
| Zerodha **Kite Connect Personal is free**. It covers orders, holdings, positions and funds, but no market data, which QuantOS does not need from it | [K-personal] |
| Kite sign-in: `https://kite.zerodha.com/connect/login?v=3&api_key=…`, then `POST /session/token` with `checksum = sha256(api_key + request_token + api_secret)`. The key expires at **6 AM the next day** (regulatory). Logout is `DELETE /session/token` | [K-user] |
| Kite needs a static IP only for order place, modify and cancel. Every other call works from any IP | [K-staticip] |

**What the codebase already has:**

- Keys live in Windows Credential Manager: `src/quant_system/server/v2/credentials.py:204`.
  `apply_to_environment()` (`:259`) copies every listed secret into `os.environ`. The view key must **not** be one of
  those (section 7.6).
- `UPSTOX_API_KEY` and `UPSTOX_API_SECRET` already exist as saved secrets (`credentials.py:32-40`). Settings →
  Accounts and keys already edits them. Reuse them and add no new fields for Upstox.
- There is a GET-only transport, `HttpTransport` / `UrlLibHttpTransport` (`data/upstox_http.py:33,59`), and a status
  mapper, `map_http_failure` (`data/upstox_failures.py`). Import them; do not edit them.
- `live/upstox_key.py` reads a key's expiry from the key itself (`key_expiry`, `key_problem`). Import it.
- The Copilot is read-only by design (`agent_context/decisions/20261006-copilot-design.md`). Tools are registered in
  `copilot/tools.py:37`, and `ToolContext` is at `copilot/registry.py:108`.
- The app port is **not fixed**. `launcher.py:160` takes the first free port from 8080, but a broker redirect has to
  match exactly. So the sign-in needs its own fixed return address (section 7.3).
- Hand-entered holdings and the Portfolio screen exist (`server/v2/portfolio.py`, `frontend/src/pages/Portfolio.tsx`).
  Leave them as they are. Broker holdings are a separate, labelled card.
- Nothing in `src/` places a real order. Keep it that way.

---

## 3. Free or not: the options, and the choice

| Option | Cost to the person | How it stays view-only | Verdict |
|---|---|---|---|
| **Upstox, their own personal app, signing in daily on Upstox's page** | ₹0. No server, no static IP, no paid plan | All three locks | **Build now (Phase 1)** |
| Zerodha Kite Connect Personal, same pattern | ₹0 | All three locks | Phase 2 |
| Upstox analytics key (one year, read-only by Upstox's rule) | A static IP from the internet provider is a paid add-on, and a laptop changes networks | The broker enforces it | Later, only if the founder buys a static IP |
| Upstox `extended_token` (long-lived, read-only) | Only for registered business partners | The broker enforces it | Not available to us now |
| Account Aggregator (RBI) | The user of the data must be a regulated entity | Consent | Not available |
| Statement import: the depositories' free monthly CAS, or the broker's holdings file | ₹0, no key at all | Nothing can be sent anywhere | Phase 3 (needs a PDF-library decision) |
| Angel One sign-in by client code + MPIN + TOTP secret | ₹0 | The app would hold a full sign-in | **Refused** for this feature |

---

## 4. What the person sees

**Settings → Broker view** (a new tab: `id: "broker"`, label `Broker view`):

> **Broker view**
> QuantOS can show what is in your broker account: your holdings, open positions and cash. It can only look. It cannot
> buy, sell, move money or change anything, and it never asks for your trading PIN or password.

The Upstox card has three states:

- **Not set up.** Three steps:
  1. "Open your Upstox app page" (link: the same Upstox developer-apps link the Accounts and keys tab already uses).
  2. "Create an app, or open the one you have. Set 'Redirect URL' to exactly this address:
     `http://127.0.0.1:47610/upstox/callback` [Copy]. Leave 'Static IP' empty. Upstox requires one before it
     accepts orders, so an app without it is not set up for trading."
  3. "Copy the two codes Upstox shows ('API Key' and 'API Secret') into Settings, then Accounts and keys."

  The **Connect Upstox** button is disabled, with the line "Save your Upstox app key and secret first."
  Quote the broker's own labels, in quotes, only where the person has to find them on Upstox's page.
- **Set up, not connected.** A **Connect Upstox** button. While waiting: "Sign in on the Upstox page that just opened in
  your browser. QuantOS never sees your password." There is a link, "If no page opened, click here", and a
  **Cancel** button.
- **Connected.** "Connected to Upstox. Updated 10:42 am. Upstox ends this sign-in at 3:30 am. After that, click Connect
  Upstox again (about 20 seconds)." There are **Refresh now** and **Disconnect** buttons.

There is also a switch, **Let the assistant read my broker account**, which is **off by default**. Under it:
"When you ask the assistant something and it uses an AI service, a summary of your holdings (names, quantities, values
and cash) is sent to that AI company with your question. Your key and your account details are never sent."

**Portfolio**: a card at the top, **From your Upstox account (view only)**. It shows:

- totals (Value, Invested, Profit or loss, Today), and cash available;
- a holdings table (Symbol, Quantity, Average, Last, Profit or loss, Share of holdings);
- open positions (Symbol, Type in words: Intraday, Delivery, Margin trading, Other; Quantity; Profit or loss);
- concentration warnings using the existing 25% rule (`server/v2/portfolio.py:18`; import the constant);
- the fetch time, which is **always visible**, and a note when rows could not be read.

When the person is not connected, the card shows the message that names the click. There are never Buy, Sell, Place,
Exit or Convert buttons, and no such wording.

**Copilot**: "What's in my broker account?" gets a short summary that quotes the fetch time, or, when the switch is off,
the sentence that tells the person where to switch it on.

Words: follow `agent_context/decisions/20261006-no-terminal-law.md` and the Copilot contract's list. No "terminal",
".env", "environment variable", "API", "JSON", "token" (say "key" or "sign-in"), "backend". Every problem names its
next click: "Open Settings, then Broker view".

---

## 5. Phases

- **Phase 1 (this brief):** Upstox; Settings → Broker view; the Portfolio card; the Copilot tool; Disconnect; all tests.
- **Phase 2 (only after the founder accepts Phase 1):** Zerodha Kite Personal (add `KITE_API_SECRET` to `SECRETS` and
  a `KITE_VIEW_KEY` to the vault). In Mizan mode, "Check my broker holdings" through the deterministic screener, with
  its sample-data notice. The exit-charge estimate on broker holdings, using `RetailCostModel`.
- **Phase 3 (founder decision first):** statement import that works for every broker with no key (a CAS PDF or the
  broker's holdings export). It needs a PDF dependency decision: check the licence, and refuse AGPL for the installer.
  It also needs `pyproject.toml`/`uv.lock` coordination.

**Phase 1 non-goals:** order book and trade book (their addresses contain `/order`); mutual funds; P&L reports; using
the view key for live prices (the one-year analytics key already serves those); adding broker data to second-opinion
fact packs (`copilot/factpack.py`); any change to paper books; a cloud relay or webhook; more than one Upstox account.

---

## 6. Files

Owned by you (new):

| Path | Responsibility |
|---|---|
| `src/quant_system/broker_view/__init__.py` | Public surface: `BrokerView`, `Snapshot`, the protocols |
| `src/quant_system/broker_view/endpoints.py` | **The only place broker addresses exist.** Plain string literals (no f-strings) and `ALLOWED_CALLS` |
| `src/quant_system/broker_view/messages.py` | Every sentence a person can read |
| `src/quant_system/broker_view/model.py` | Frozen dataclasses (`Decimal` money): `HoldingRow`, `PositionRow`, `Cash`, `Snapshot`, `Freshness` |
| `src/quant_system/broker_view/upstox_parse.py` | Strict parsing of the three replies; bad rows are skipped and counted |
| `src/quant_system/broker_view/upstox_read.py` | The three GETs through an injected `HttpTransport` |
| `src/quant_system/broker_view/login.py` | `LoginAttempt` (state, expiry, single use), the authorize address, and the reading of the code exchange |
| `src/quant_system/broker_view/session_http.py` | The **only** module that may import `urllib.request`: `UrlLibSessionTransport` with exactly `exchange_code()` (POST) and `end_session()` (DELETE) |
| `src/quant_system/broker_view/loopback.py` | The one-shot sign-in return listener on `127.0.0.1:47610` |
| `src/quant_system/broker_view/service.py` | `BrokerView`: `status`, `begin_login`, `finish_login`, `refresh`, `snapshot`, `disconnect`, `assistant_summary`, `set_assistant_access` |
| `src/quant_system/broker_view/store.py` | `SqliteSnapshotStore(path)`: the last snapshot and the assistant switch. The server passes `paths.state_dir() / "broker_view.sqlite"`, so this package imports nothing from `server/`. Note that the Settings tab label is "Accounts & keys" (`Settings.tsx:52`) |
| `src/quant_system/server/v2/broker_routes.py` | `APIRouter(prefix="/broker")`; wires the real transports, vault, store, listener and `webbrowser.open` |
| `src/quant_system/copilot/tools_broker.py` | The `broker_account` tool, its `ToolText`, and `broker_specs(ctx)` |
| `frontend/src/components/BrokerViewSettings.tsx` (+ `.test.tsx`) | The Settings tab content |
| `frontend/src/components/BrokerAccountCard.tsx` (+ `.test.tsx`) | The Portfolio card |
| `tests/test_broker_view_*.py`, `tests/test_copilot_broker_tool.py` | Section 10 |

Edited (small changes). Each claimed one needs the NOTICE:

| Path | Change |
|---|---|
| `src/quant_system/server/v2/router.py` (claimed) | One `include_router(broker_router, prefix="/api/v2")` beside lines 954-955 |
| `src/quant_system/server/v2/credentials.py` (claimed) | Add a public `ScopedCredentialStore` (section 7.6). `SECRETS`, `status()` and `apply_to_environment()` do not change |
| `src/quant_system/server/v2/copilot_wiring.py` (claimed) | `broker=_broker_account` in `tool_context()` (`:197`) |
| `src/quant_system/copilot/registry.py` | `ToolContext.broker: Callable[[], dict[str, Any]] \| None = None` |
| `src/quant_system/copilot/tools.py` | `*broker_specs(ctx)` in the registry list (`:37`) |
| `src/quant_system/copilot/rules.py` | Optional: a built-in route to `broker_account` for "broker", "Upstox", "cash", "positions", following the pattern at `:323` |
| `tests/test_no_terminal_copy.py` | Add `src/quant_system/broker_view` to the scanned packages |
| `frontend/src/pages/Settings.tsx` (claimed) | Add the `broker` section (`SECTIONS`, `:48`) |
| `frontend/src/pages/Portfolio.tsx` (claimed) | Show `BrokerAccountCard` above the hand-entered holdings |
| `frontend/src/lib/{api,queries,types}.ts` (claimed) | Types and hooks for section 8 |
| `src/quant_system/server/static/app/**` (claimed) | Rebuilt by `npm run build` (`frontend/vite.config.ts:6` writes there) |

---

## 7. Engine design

### 7.1 The allowlist (`endpoints.py`)

```python
UPSTOX_AUTHORIZE_URL = (
    "https://api.upstox.com/v2/login/authorization/dialog"  # opened in the person's browser only
)
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_LOGOUT_URL = "https://api.upstox.com/v2/logout"
UPSTOX_HOLDINGS_URL = "https://api.upstox.com/v2/portfolio/long-term-holdings"
UPSTOX_POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"
UPSTOX_FUNDS_URL = "https://api.upstox.com/v2/user/get-funds-and-margin"  # with ?segment=SEC
CALLBACK_PORT = 47610
CALLBACK_PATH = "/upstox/callback"
CALLBACK_ADDRESS = "http://127.0.0.1:47610/upstox/callback"

ALLOWED_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", UPSTOX_TOKEN_URL),
        ("DELETE", UPSTOX_LOGOUT_URL),
        ("GET", UPSTOX_HOLDINGS_URL),
        ("GET", UPSTOX_POSITIONS_URL),
        ("GET", UPSTOX_FUNDS_URL),
    }
)
```

Every read goes through one helper, `_get(url, query)`, which asserts `("GET", url) in ALLOWED_CALLS` before calling
the transport. If that assertion fails, the result is a typed failure. It is never sent.

### 7.2 Sign-in, step by step

1. `POST /api/v2/broker/upstox/connect`. If `UPSTOX_API_KEY` or `UPSTOX_API_SECRET` is not saved, return 422
   `BROKER_NOT_SET_UP` with a message that names the step. Read them the way `live_routes.py` reads keys: saved store
   first, then the environment.
2. Make a `LoginAttempt`: `state = secrets.token_urlsafe(32)`, `started_at = now`, valid for **300 s**, single use.
   A new click replaces any older attempt, and the older state stops working.
3. Start the listener (7.3). If the port is busy, return 409 `CALLBACK_BUSY` with `messages.PORT_BUSY`.
4. Build the authorize address with `urlencode`: `response_type=code`, `client_id`, `redirect_uri=CALLBACK_ADDRESS`,
   `state`. Call `webbrowser.open(address, new=2)` and return `{"opened": <bool>, "login_address": address}`. The
   address is never logged.
5. The person signs in on Upstox. Upstox sends their browser to `CALLBACK_ADDRESS?code=…&state=…`.
6. The listener checks `state` with `hmac.compare_digest`, then checks that it has not expired or been used. Only then
   does it call `session.exchange_code({"code", "client_id", "client_secret", "redirect_uri", "grant_type"})`.
7. From the reply, keep `access_token` and nothing else. Save it to the vault as `UPSTOX_VIEW_KEY`. Work out
   `key_ends_at` from `key_expiry()`, or the next 03:30 IST if the key does not say. Then fetch the first snapshot.
8. The browser shows a static page: "QuantOS is connected to your Upstox account (view only). You can close this tab."
   If the sign-in failed, it says: "QuantOS could not finish connecting. Go back to QuantOS to see why." The page
   never echoes `code`, `state` or any other parameter.
9. While waiting, the screen polls `GET /api/v2/broker/status` every 2 s, and stops at success, Cancel, or 5 minutes.

### 7.3 The return listener (`loopback.py`)

- `http.server.HTTPServer` on `("127.0.0.1", 47610)`, run in a daemon thread, alive only during an attempt.
- **Set `allow_reuse_address = False`, and on Windows set `SO_EXCLUSIVEADDRUSE` before binding.** Otherwise another
  local program could bind the same port and catch the code.
- Answer only `GET /upstox/callback`. Any other path gets 404. Any other method gets 405.
- **Override `log_message` to log nothing.** The default handler writes the request line, which includes the code and
  state, to standard error.
- Response headers: `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, and
  `Content-Security-Policy: default-src 'none'`. No external resources.
- Shut down after the first callback with a valid state, after 300 s, when Cancel is pressed, or when a new attempt
  starts.

### 7.4 Reading and parsing

- Each GET: 10 s timeout and a 2 MiB body cap (`UpstoxClientConfig` defaults). No retry on 401 or 403. No automatic
  retries at all in Phase 1; the person can click Refresh.
- **Between 00:00 and 05:30 IST, skip the funds call**: cash is `null`, with `messages.FUNDS_WINDOW`.
- If holdings succeed but positions or funds fail, show what came back and say which part is missing.
- Status mapping uses `map_http_failure`. Two extras:
  - If the body's first error code is `UDAPI1221` (static-IP restricted, measured 2026-08-31), use
    `messages.STATIC_IP_REQUIRED`, **keep the key**, and keep the last snapshot.
  - Any other 401 forgets the key, keeps the last snapshot, and uses `messages.KEY_REJECTED`.
- A key whose own expiry has passed is forgotten **without any network call** (`key_problem`), and the result is
  `messages.KEY_ENDED`.
- **Holdings fields kept.** Everything else is dropped, including `company_name`, `product`, `haircut`,
  `collateral_*`, `cnc_used_quantity` and `instrument_token`:
  - `trading_symbol` (fall back to `tradingsymbol`), upper-cased, matching `^[A-Z0-9&\-]{1,30}$`;
  - `exchange`, matching `^[A-Z_]{2,10}$`;
  - `isin`, matching `^[A-Z]{2}[A-Z0-9]{9}[0-9]$`, otherwise `None`;
  - `quantity` and `t1_quantity`, which must be whole and 0 or more (refuse a bool or a fraction);
  - `average_price`, `last_price`, `close_price`, as finite `Decimal` values of 0 or more;
  - `pnl`, as a finite `Decimal`.
- **Positions fields kept:** the symbol (spaces allowed, `^[A-Z0-9&\- ]{1,40}$`), `exchange`, and `product` mapped to
  words (`I` Intraday, `D` Delivery, `MTF` Margin trading, anything else Other). Also `quantity` (whole, signed),
  `average_price`, `last_price`, `pnl`, `realised` and `unrealised`. Positions with quantity 0 stay, labelled
  "closed today".
- **Funds.** Read `data.equity` if it exists, otherwise `data`. Keep `available_margin` (shown as "Available") and
  `used_margin` ("In use"). Confirm the real shape on the founder's account and pin it in an invented-number fixture.
- A row that fails any check is skipped and counted, and never guessed. A reply whose `status` is not `"success"`, or
  that is not JSON, is a failure.
- **Our own arithmetic, in `Decimal`:**
  - invested = Σ average × quantity;
  - value = Σ last × quantity;
  - profit or loss = value − invested;
  - today = Σ (last − close) × quantity.

  Do not use the broker's `day_change`: its unit is not documented. Rupees go to two places only at the JSON boundary,
  using `float()` the way `server/v2/portfolio.py` does.
- **T+1 shares are not guessed.** Value `quantity` only. Show `t1_quantity` as its own line, "Bought recently, arriving
  in your demat", with its value. Section 12 settles this against the real account.

### 7.5 Snapshot, freshness and throttle

- `Freshness` is `UP_TO_DATE` (fetched 5 minutes ago or less), `OLDER`, or `NONE`.
- The store keeps one snapshot per broker, with `fetched_at`, and replaces it atomically. It holds no key and no
  identifier. The file `broker_view.sqlite` is ignored by Git through `*.sqlite` (`.gitignore:26`); confirm it with
  `git check-ignore -v`.
- At most one broker call every 30 s. A refresh inside that window returns the stored snapshot with
  "Updated a moment ago."
- The Copilot tool refreshes only when the snapshot is older than 5 minutes **and** the key is still good. Otherwise it
  reads the stored snapshot, and says how old it is.
- `BrokerView` is shared between FastAPI's thread pool and the listener thread, so guard its state with one
  `threading.Lock`.

### 7.6 The key vault (never in the environment)

- `broker_view` defines `KeyVault` (`load`, `save`, `forget`) and imports nothing from `server/`.
- The server provides `ScopedCredentialStore(prefix=TARGET_PREFIX + "BrokerView:", names=frozenset({"UPSTOX_VIEW_KEY"}))`.
  It is added to `credentials.py` and reuses `_WinCredApi`. Deriving the prefix from `TARGET_PREFIX` keeps the existing
  test isolation through `QUANTOS_CREDENTIALS_PREFIX` working.
- Tests must prove three things: `os.environ` is unchanged after `save`; `CredentialStore().status()` does not list the
  name; and `apply_to_environment()` never applies it.
- Off Windows (`_WinCredApi` unavailable), Broker view reports "not available on this computer". Tests use an
  in-memory vault.

### 7.7 Messages (`messages.py`; wording may be improved, not loosened)

| Name | Sentence |
|---|---|
| `VIEW_ONLY` | "View only. QuantOS can look at this account. It cannot buy, sell, move money or change anything." |
| `NOT_SET_UP` | "To see your Upstox account here, open Settings, then Broker view, and follow the three steps." |
| `KEY_ENDED` | "Your Upstox sign-in has ended for today (Upstox ends it at 3:30 am). Open Settings, then Broker view, and click Connect Upstox." |
| `KEY_REJECTED` | "Upstox did not accept the sign-in. Open Settings, then Broker view, and click Connect Upstox again." |
| `STATIC_IP_REQUIRED` | "Upstox is asking for a registered internet address before it will show your holdings, so they could not be updated. Your last update is still shown." |
| `PORT_BUSY` | "QuantOS could not get ready to receive the Upstox sign-in, because another program is using what it needs. Close other programs, then click Connect Upstox again." |
| `STATE_MISMATCH` | "That sign-in did not start from this QuantOS window, so it was ignored. Click Connect Upstox to start again." |
| `LOGIN_TIMED_OUT` | "The sign-in took longer than 5 minutes, so it was stopped. Click Connect Upstox to try again." |
| `FUNDS_WINDOW` | "Upstox does not show your cash between midnight and 5:30 am. Your holdings are shown." |
| `PARTIAL` | "{n} holdings could not be read and are not shown." (with correct plurals) |
| `ASSISTANT_OFF` | "You have not let the assistant see your broker account. To allow it, open Settings, then Broker view." |
| unreachable, slow, busy | Mirror `live/messages.py` |

### 7.8 Logging

Log events and counts only, for example "broker view refreshed: 12 holdings, 1 position, funds skipped (window)".
Never log the key, a request header, the authorize address, the callback query, a reply body, or an exception's text
from the transport. `live/upstox_fetch.py` keeps a `reason` for the log for the same reason.

---

## 8. Screen-to-engine contract (all under `/api/v2`, CSRF on writes as `frontend/src/lib/api.ts` already sends it)

`GET /broker/status`

```json
{
  "brokers": [{
    "id": "upstox", "label": "Upstox",
    "set_up": true, "connected": true, "waiting_for_sign_in": false,
    "key_ends_at": "2026-10-08T03:30:00+05:30",
    "callback_address": "http://127.0.0.1:47610/upstox/callback",
    "message": null
  }],
  "assistant_access": false,
  "available": true
}
```

`POST /broker/upstox/connect` → 200 `{"opened": true, "login_address": "https://api.upstox.com/v2/login/authorization/dialog?..."}`,
422 `BROKER_NOT_SET_UP`, or 409 `CALLBACK_BUSY`.  
`DELETE /broker/upstox/connect` → cancels a waiting sign-in (idempotent).  
`GET /broker/snapshot`:

```json
{
  "broker": "upstox", "connected": true, "view_only": true,
  "fetched_at": "2026-10-07T10:42:05+05:30", "freshness": "UP_TO_DATE",
  "message": null,
  "label": "From your Upstox account. View only.",
  "totals": {"value": 85000.0, "invested": 80000.0, "pnl": 5000.0, "pnl_pct": 6.25, "today": 320.0},
  "cash": {"available": 12000.5, "in_use": 3000.0, "note": null},
  "holdings": [{"symbol": "TCS", "exchange": "NSE", "isin": "INE467B01029", "quantity": 10, "t1_quantity": 0,
                "average_price": 3400.0, "last_price": 3500.5, "close_price": 3480.0,
                "value": 35005.0, "invested": 34000.0, "pnl": 1005.0, "pnl_pct": 2.96, "today": 205.0, "weight_pct": 41.18}],
  "positions": [{"symbol": "INFY", "exchange": "NSE", "product": "Intraday", "quantity": -5,
                 "average_price": 1500.0, "last_price": 1490.0, "pnl": 50.0, "realised": 0.0, "unrealised": 50.0}],
  "warnings": ["TCS is 41% of your holdings (above 25%)."],
  "skipped": {"holdings": 0, "positions": 0}
}
```

`POST /broker/refresh` → the snapshot (throttled as in 7.5).  
`DELETE /broker/connection` → ends the Upstox session when the key is still good (best effort), forgets the key,
deletes the stored snapshot, and returns the status.  
`PUT /broker/assistant-access` with `{"allowed": true}` → the status.

Every `_pct` value is in percent points (5.0 means 5%), matching `copilot_wiring.py:31`. No path contains `order`,
`buy`, `sell`, `trade`, `place` or `execute`. No response contains a key, an email, a name, a user id or a client code.

---

## 9. The Copilot tool `broker_account`

- `ToolText`:
  - label "My broker account";
  - help "Reads what your broker shows: holdings, open positions and cash. It can only look, never trade.";
  - description, for the model: "The person's real broker account, view only, as last fetched: holdings, open positions,
    available cash, totals and the fetch time. Always say when it was fetched. Nothing can be bought, sold or changed
    through QuantOS; never suggest otherwise."
- If the switch is off, raise `UserFacingError(messages.ASSISTANT_OFF)`. If not connected and nothing is stored,
  `NOT_SET_UP`. If there is a stored snapshot but the key has ended, return the snapshot with its age and say so.
- Data passed to the model: `source` (one sentence with the fetch time and age), `totals`, `cash_available`, up to 30
  holdings (symbol, quantity, average_price, last_price, pnl, pnl_pct, weight_pct), up to 20 positions (symbol,
  product, quantity, pnl), `warnings`, and a `note` repeating that nothing can be traded. Nothing else.
- Every string is a validated symbol or one of our own sentences, so `untrusted` stays `False`. If you ever pass a
  broker-supplied free-text field, set `untrusted=True`.
- The tool appears in `GET /copilot/tools` automatically, and the same switch governs saved agents.

---

## 10. Tests to write first (no network; fakes for every transport, vault, clock and browser)

| File | It must prove |
|---|---|
| `tests/test_broker_view_endpoints.py` | Read the package with `ast`. Every string constant containing `://` is one of the `endpoints.py` constants. No f-string contains `://`. No URL constant outside `endpoints.py`. `urllib.request` is imported only in `session_http.py`, which has exactly two `Request(...)` calls: POST to `UPSTOX_TOKEN_URL` and DELETE to `UPSTOX_LOGOUT_URL`. No `requests`, `httpx`, `aiohttp` or `http.client`. `ALLOWED_CALLS` equals the five pairs exactly. No allowlisted address contains `/order`, `/gtt`, `convert`, `payment`, `authorise` or `/mf` |
| `tests/test_broker_view_parse.py` | Invented replies in the documented shapes give exact `Decimal` values. NaN, negative prices, bools and fractional quantities are skipped and counted. `status != "success"` and non-JSON are failures. Dropped fields really are dropped. The funds shape is read from both `data.equity` and `data` |
| `tests/test_broker_view_login.py` | A missing, wrong, reused or expired state is refused before any exchange. The exchange sends exactly the five fields. Only `access_token` survives. A sentinel key `SENTINEL-KEY-DO-NOT-LEAK` never appears in `caplog`, exceptions or messages. A reply without `access_token` is a failure |
| `tests/test_broker_view_loopback.py` | It binds to `127.0.0.1` only, with exclusive use. Other paths give 404 and other methods 405. The page echoes no query value. Nothing is logged. It shuts down after success, after the timeout, and on cancel. A busy port gives `PORT_BUSY` |
| `tests/test_broker_view_service.py` | The 30 s throttle. An expired key means no network call and the key is forgotten. A 401 forgets the key and keeps the snapshot. `UDAPI1221` keeps the key. The funds window skips the funds call (with a clock in IST). A partial reply is labelled. Disconnect forgets the key and the snapshot, and calls `end_session` once. `os.environ` is unchanged throughout |
| `tests/test_broker_view_vault.py` | `ScopedCredentialStore` names are not in `status()`, `apply_to_environment()` never sets them, and names outside its set are refused |
| `tests/test_broker_view_routes.py` | FastAPI `TestClient` for every route in section 8. CSRF is enforced on writes, mirroring the existing v2 tests. Route paths avoid the banned words. Across a full connect → refresh → disconnect cycle, the sentinel key never appears in any response body or log record |
| `tests/test_copilot_broker_tool.py` | Off means the `ASSISTANT_OFF` message, and **no broker data reaches the prompt** (capture it with the fake LLM). On means the summary's keys are a subset of the allowed set, there are no identifiers, `for_prompt()` has no sentinel, and the fetch time is present. `tests/test_copilot_tools.py` still passes unchanged |
| `tests/test_no_terminal_copy.py` (edit) | Scans `broker_view` messages. "Settings, then Broker view" resolves to a real tab |
| `frontend/src/components/BrokerViewSettings.test.tsx` | All three states. The switch starts off. The copy button carries the exact address. No Buy or Sell wording |
| `frontend/src/components/BrokerAccountCard.test.tsx` | The fetch time is always shown. The not-connected message names the click. Skipped rows are announced. No Buy, Sell, Place, Exit or Convert button |

---

## 11. Acceptance criteria

1. **Given** no Upstox app key is saved, **when** the person opens Settings → Broker view, **then** they see the three
   steps, the exact return address with a Copy button, and a disabled Connect with "Save your Upstox app key and secret
   first."
2. **Given** a key and secret are saved, **when** Connect Upstox is clicked, **then** the default browser opens
   Upstox's sign-in, the screen shows the waiting state, and within 5 s of the sign-in the screen shows Connected and
   the Portfolio card shows holdings.
3. **Given** a return with a wrong, missing, reused or expired state, **then** no exchange is attempted, the browser
   page says the sign-in was ignored, and nothing is saved.
4. **Given** 5 minutes pass with no return, **then** the listener closes and the screen shows `LOGIN_TIMED_OUT`.
5. **Given** a saved key whose expiry has passed, **when** Portfolio opens, **then** nothing is sent to Upstox, the
   last snapshot shows with its time, and the message names Connect Upstox.
6. **Given** Upstox answers 401 to holdings, **then** the key is forgotten, the last snapshot stays, and `KEY_REJECTED`
   is shown. **Given** `UDAPI1221`, **then** the key stays and `STATIC_IP_REQUIRED` is shown.
7. **Given** it is between 00:00 and 05:30 IST, **when** a refresh runs, **then** funds are not requested and the cash
   note is shown, with holdings intact.
8. **Given** one malformed holding row, **then** it is not shown, and the card says 1 holding could not be read.
9. **Given** the assistant switch is off, **when** the person asks the Copilot about their account, **then** the
   answer is `ASSISTANT_OFF` and no broker figure is in any prompt.
10. **Given** the switch is on, **then** the answer quotes the fetch time, and the prompt holds no key, name, email,
    user id or client code.
11. **Given** a sentinel key, **then** during connect, refresh and disconnect it never appears outside the vault: not
    in routes, logs, errors, `os.environ`, files or prompts.
12. **Given** Disconnect, **then** the key is gone, the snapshot is deleted, the session end was sent once if the key
    was still good, and the screen is back to "not connected".
13. `broker_view` contains no address outside the allowlist and no write outside the two sign-in calls (test).
14. With no network and no credentials (`SYNTHETIC_MODE`, CI), every new test passes, the app starts, and Broker view
    says "not set up".
15. No new screen has a trading button or trading wording (frontend tests).

---

## 12. Check it with the founder's real account (reading only)

The founder does the clicking. You never type their keys or sign in for them, and their numbers never go into the
repository.

1. On Upstox's app page, the founder sets 'Redirect URL' to the return address and confirms 'Static IP' is empty.
   Record only "static IP empty: yes/no". If it is not empty, record that the broker's lock is off for this app; ours
   still holds.
   - Since 1 April 2026 Upstox allows one active app per user. If that app's redirect address serves another tool,
     changing it may break that tool. Ask first.
   - The repository has no other Upstox sign-in flow (searched 2026-10-07).
2. Connect, then compare the card's total value and invested amount with the Upstox app's own holdings screen. Record
   "matched within ₹1", or the difference and its cause. Do this once more on a day with T+1 shares, and settle 7.4's
   T+1 rule by which way matches.
3. Ask the Copilot "what's in my broker account?" with the switch off, then on. Record the behaviour, not the answer.
4. Disconnect. Confirm Settings shows not connected, and that `cmdkey /list` shows no `QuantOS:BrokerView:` entry.
   Confirm the founder's Upstox mobile app is still signed in. If the session-end call signed it out, drop that call
   and record why.
5. **Never send an order, or anything that looks like one, to test anything.**

---

## 13. Gates, commits and release

- Python: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src launcher.py scripts`, and
  `uv run pytest tests/ -q`, forwards and in reverse file order (as `.github/workflows/ci.yml` does).
- Screens, in `frontend/`: `npm run typecheck`, `npm test`, `npm run build`. The build rewrites
  `src/quant_system/server/static/app/**`; commit it with the change, as earlier screen changes did.
- Secrets: `uv run detect-secrets scan <each changed file>`. Every result must be empty.
- Run `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` before handoff.
- Stage explicit paths only. Never `git add -A` or `git add .`.
- Commits are conventional and written for a person, for example
  `feat(broker): see your Upstox holdings and cash in QuantOS, view only`.
- Commit and push only when the founder says so. After merging, run `python scripts/release_status.py`. A `feat`
  counts toward a release; if one is due, follow the Release rule in `AGENTS.md`.
- At the end, move your record to `work/completed/`. Add a handoff if Phase 2 is next.

---

## 14. Do not do

- Do not add any address to `ALLOWED_CALLS` without a decision record and the founder's word.
- Do not reuse `UPSTOX_ACCESS_TOKEN` for the view key, or copy the view key into `os.environ`.
- Do not add a scheduler that signs in, a cloud relay, a webhook, or a second Upstox app.
- Do not show a broker figure without its fetch time, or call any profit "skill" or "edge" (GOAL tripwire 4).
- Do not edit another agent's record, the Copilot contract file, `data/upstox*.py`, or `live/*.py`. Import from them.
- Do not run repository-wide formatters in the shared checkout while another agent is active.

---

## 15. Open questions for the founder (proposals in brackets; build with them unless told otherwise)

1. Should the assistant switch start off? [Yes, off; one click turns it on.]
2. Should the last snapshot stay on this computer after the sign-in ends, so QuantOS still knows the last position,
   until Disconnect? [Yes.]
3. What comes next after Phase 1: Zerodha, or the statement import that works with every broker? [Zerodha.]
4. A "Connect" button with no Upstox app setup at all would need QuantOS registered with each broker as a business
   partner (multi-client app; Upstox's extended key). That is a business decision, not a free option. [Not now.]

---

## Appendix A: the decision record to create (`agent_context/decisions/20261007-broker-view-only.md`)

```markdown
# Broker view: a view-only connection to the person's broker

DATE: 2026-10-07
GOAL_LINE: G6, with G1, G2 and G4
FOUNDER INSTRUCTION: a read-only connection so the platform and its AI know where the account stands, without access
to it, at no cost (chat, 2026-10-07)
BRIEF: agent_context/handoffs/20261007-broker-view-only-build-brief.md

## What was decided
1. Upstox first. The person's own free developer app, signed in daily on Upstox's own page, returning to a one-shot
   listener on 127.0.0.1:47610. Zerodha Kite Personal next.
2. View-only is three locks: the broker refuses orders from an app with no static IP; our package has a closed
   allowlist (GET-only reads, plus a session transport that takes no URL); the AI sees a summary only, behind a switch
   that starts off.
3. The view key lives in Windows Credential Manager under its own prefix. It is never copied into the environment,
   never logged, never returned, never prompted.
4. Holdings, positions and cash only. No order book, trade book, mutual funds or P&L reports in Phase 1.

## Why
The person needs to know where their account stands, and the evidence rule needs every figure to say where it came
from and when. Reading is free at Upstox and Zerodha, and needs no static IP. Only orders need one since 1 April 2026.
This is not order routing (T4) and writes nothing to the account. The only non-GET calls are the sign-in exchange and
ending the session, and both go to the broker's sign-in service.

## Rejected alternatives
| Alternative | Why not |
|---|---|
| Upstox one-year analytics key | Read-only, but holdings need a whitelisted static IP: a paid add-on, and laptops change networks |
| Upstox extended key | Only for registered business (multi-client) apps |
| Account Aggregator | Needs a regulated financial-information user |
| Angel One client code + MPIN + TOTP | The app would hold a full sign-in, the opposite of view-only |
| Cloud webhook (Upstox token request) | Costs money, and the key would leave the laptop |
| Reuse UPSTOX_ACCESS_TOKEN | It is copied into os.environ and shared with other features; the view key should be held by as little code as possible |
| Callback on the app's own port | The port is chosen at start-up (from 8080); a broker redirect must match exactly |

## Known limits
- The person signs in once a day. The broker ends the key at 3:30 am (Upstox) or 6 am (Zerodha).
- Each person creates their own broker app once, on the broker's site, guided by the screen.
- The broker's lock is the broker's published rule. We do not test it, because testing it means sending an order.
- The T+1 quantity meaning is settled against a real account, not assumed.
```

---

## Appendix B: sources (checked 2026-10-07)

- [U-authorize] https://upstox.com/developer/api-documentation/authorize/
- [U-token] https://upstox.com/developer/api-documentation/get-token/
- [U-logout] https://upstox.com/developer/api-documentation/logout/
- [U-holdings] https://upstox.com/developer/api-documentation/get-holdings/
- [U-positions] https://upstox.com/developer/api-documentation/get-positions/
- [U-funds] https://upstox.com/developer/api-documentation/get-user-fund-margin/
- [U-analytics] https://upstox.com/developer/api-documentation/analytics-token/
- [U-mandate] https://community.upstox.com/t/important-new-sebi-exchange-mandates-for-api-trading-effective-1st-april-2026/14822
- [U-staticip] https://community.upstox.com/t/clarification-on-static-ip-requirement-for-different-api-types/10421
- [U-pricing] https://community.upstox.com/t/developer-api-pricing/3796
- [U-localhost] https://community.upstox.com/t/issue-with-redirect-url-local/8822
- [U-extended] https://community.upstox.com/t/extended-token-for-read-only-access/10702
- [K-user] https://kite.trade/docs/connect/v3/user/
- [K-portfolio] https://kite.trade/docs/connect/v3/portfolio/
- [K-personal] https://kite.trade/forum/discussion/comment/49195 and https://tradingqna.com/t/kite-connect-personal-apis-are-now-made-free-for-personal-use/181620
- [K-staticip] https://kite.trade/forum/discussion/15359/query-regarding-static-ip-requirement-for-kite-connect-api-data-only-usage
- [CAS] https://www.amfiindia.com/investor-corner/investor-center/cas.html

---

## Handoff fields

- **Completed:** research, design and this brief.
- **In progress:** nothing.
- **Files and ownership:** this file, and the design record named at the top. Neither is committed.
- **Verification:** none needed for a document. No code exists yet.
- **Known risks:**
  - Upstox may change paths or rules; re-check section 2 first.
  - The funds reply shape and the T+1 semantics need the real account.
  - Port 47610 may be in use on some machines.
- **Exact stop point:** the brief is written.
- **Next safe action:** section 1, step 1.
