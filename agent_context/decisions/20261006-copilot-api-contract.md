# Copilot, agents and live prices: the screen-to-engine contract

DATE: 2026-10-06
OWNER_RECORD: `agent_context/work/active/20261006-claude-copilot-agent-and-live-quotes.md`
GOAL_LINE: G6

The engine side (`src/quant_system/copilot/`) and the screens (`frontend/src/`) are built at the same time by
different workers. This file fixes the JSON between them so neither waits for the other. All paths are under
`/api/v2`. Writes need the CSRF header exactly as `frontend/src/lib/api.ts` already sends it. Errors use the existing
error envelope and `ApiError`.

Every sentence a person can read, in any response or screen, must pass the No-Terminal Law
(`agent_context/decisions/20261006-no-terminal-law.md`): no terminal, command, file edit, environment variable, JSON,
API or developer tool, and always name the next click ("Open Settings, then Accounts and keys").

## Status

`GET /copilot/status`

```json
{
  "ai_ready": true,
  "providers": [{"id": "openai", "label": "OpenAI", "ready": true}],
  "live_prices": {"ready": false, "message": "Add an Upstox token in Settings, then Accounts and keys."}
}
```

`providers` lists every AI provider the app supports; `ready` is true when the person has saved a key for it.
`id` is the provider name and is what the screens send back. No key value is ever returned.

## Chat

`POST /copilot/chat`

```json
{"messages": [{"role": "user", "content": "is TCS halal?"}], "page": "/stock/TCS", "agent_id": null}
```

`page` is the screen path the person is on (optional). `agent_id` runs the chat as that saved agent, or a recipe id
(optional). Reply (always HTTP 200 for a normal outcome, including "no AI key" and provider failures):

```json
{
  "reply": "markdown text",
  "steps": [{"label": "Halal screening", "summary": "TCS: both standards checked", "ok": true}],
  "proposals": [{"kind": "navigate", "label": "Open TCS", "path": "/stock/TCS", "symbol": "TCS"}],
  "mode": "ai",
  "provider": "openai",
  "model": "gpt-x",
  "error": null
}
```

- `mode` is `"ai"` when a model answered and `"built_in"` when the built-in answers did (no AI key, or the AI could
  not be reached). `provider`/`model` are null in built-in mode.
- `proposals[].kind` is `"navigate"` (open `path` in the app) or `"second_opinion"` (open the Second opinion dialog for
  `symbol`). They are buttons the person clicks. The Copilot never does either by itself.
- `reply` is markdown limited to: paragraphs, `**bold**`, `-` lists, `[text](https://...)` links. Render links only
  when the URL starts with `https://`, open them in a new tab with `rel="noopener noreferrer"`, and never render
  raw HTML.

## Second opinion (several AI models, run in the background)

`GET /copilot/models` returns `{"models": [{"id": "openai", "label": "OpenAI", "ready": true}]}` (same shape as
`providers`; only `ready` ones can be picked).

`POST /copilot/verify` starts a run and returns HTTP 202 `{"job_id": "abc123"}`.

```json
{"symbol": "TCS", "providers": ["openai", "anthropic"], "pick_note": "Ranked 3rd of 40 by the model.", "recheck": true}
```

`pick_note` is optional; when present the informed question is also asked (it measures anchoring).

`GET /copilot/verify/{job_id}`:

```json
{
  "status": "running",
  "progress": {"done": 3, "total": 6},
  "result": null,
  "error": null
}
```

`status` is `running`, `done` or `failed`. When `done`, `result` is:

```json
{
  "symbol": "TCS",
  "headline": "2 of 3 models read the facts as MIXED.",
  "consensus": "MAJORITY",
  "reading": "MIXED",
  "asked": 3,
  "answered": 3,
  "counts": {"MIXED": 2, "POSITIVE": 1},
  "news_tones": {"NEUTRAL": 2, "POSITIVE": 1},
  "verdicts": [
    {
      "blind":    {"provider": "openai", "model": "m", "arm": "blind", "ok": true, "reading": "MIXED",
                   "news_tone": "NEUTRAL", "reasons": ["..."], "risks": ["..."], "missing": ["..."],
                   "removed": 0, "error": null},
      "informed": null,
      "recheck":  {"provider": "openai", "model": "m", "arm": "recheck", "ok": true, "reading": "MIXED",
                   "news_tone": "NEUTRAL", "reasons": [], "risks": [], "missing": [], "removed": 0, "error": null},
      "stable": true,
      "shift": null
    }
  ],
  "dissent": [{"provider": "anthropic", "model": "m", "reading": "POSITIVE", "reasons": ["..."], "risks": ["..."]}],
  "notes": ["plain-language caveats, show every one"],
  "halal": {"covered": true, "data_status": "UNVERIFIED_SAMPLE", "standards": [], "disclaimer": "..."},
  "facts": {"symbol": "TCS", "sections": [{"title": "Price history facts", "summary": "...", "from_outside": false}],
            "unavailable": ["Live price"]},
  "disclosure": "These are opinions from AI models ... not independent evidence ..."
}
```

`consensus` is `AGREE`, `MAJORITY`, `SPLIT`, `SINGLE` or `NONE`. `MAJORITY` means more than half of the models that
answered share one reading; a reading shared by fewer than that (for example 2, 1 and 1 of four) is `SPLIT`. `reading` is
`POSITIVE`, `MIXED`, `NEGATIVE`, `UNCLEAR` or null (null for `SPLIT` and `NONE`). When fewer models answered than were
asked, `headline` says so in words ("2 of 5 models answered, and both read the facts as POSITIVE."). Screens must show
`disclosure` and every entry of `notes` on every result, show the dissenters and
their reasons, show which models answered and which could not (and why), and must never present a reading as a
recommendation, a score or a green light. The halal block is shown as the screener's own result and labelled as
such; models never produce it.

## Agents (saved assistants) and recipes

`GET /copilot/tools` returns
`{"tools": [{"name": "stock_facts", "label": "Price facts", "help": "Shows how a stock has moved over the last month, six months and year.", "description": "..."}]}`.
The form shows `label` with a checkbox and `help` under it. `name` is only what is saved, and `description` is written
for the AI model (it names code and gives instructions): never show either to the person.

`GET /copilot/agents` returns `{"agents": [Agent], "recipes": [Recipe]}`:

```json
{"id": "a1b2c3", "name": "My check", "description": "", "instructions": "", "tools": ["stock_facts"],
 "steps": ["Show the facts about {symbol}."], "needs_symbol": true, "built_in": false,
 "created_at": "2026-10-06T10:00:00+00:00", "updated_at": "2026-10-06T10:00:00+00:00"}
```

A Recipe has the same fields plus `"built_in": true` and `"needs_ai": bool`, and no timestamps. Recipes cannot be
edited or deleted; the screen offers "Run" and "Copy and edit".

`POST /copilot/agents` and `PUT /copilot/agents/{id}` take `{"name", "description", "instructions", "tools": [...],
"steps": [...]}` and return the Agent. A rejected form returns HTTP 422 with
`{"error": {"code": "AGENT_INVALID", "message": "Check the highlighted fields.", "details":
{"problems": [{"field": "name", "message": "Give your agent a name."}]}}}`. `field` is one of `name`, `description`,
`instructions`, `tools`, `steps`. Show each message under its field, exactly as written. `DELETE /copilot/agents/{id}`
returns `{"deleted": true}`. The only fill-in a step may use is `{symbol}`.

`POST /copilot/agents/{id}/run` (id is an agent id or a recipe id) takes `{"symbol": "TCS"}` (omit when the agent does
not need one) and returns:

```json
{
  "name": "Check a stock, step by step",
  "symbol": "TCS",
  "steps": [{"number": 1, "text": "Show the facts about TCS: ...", "reply": "markdown",
             "looked_at": [{"label": "Price facts", "summary": "...", "ok": true}], "error": null}],
  "proposals": [{"kind": "second_opinion", "label": "Get a second opinion on TCS", "path": null, "symbol": "TCS"}],
  "model": null,
  "completed": true,
  "note": "plain-language note, or null"
}
```

`note` is shown under the result when present (for example that no AI key was used). A run can take a minute: show
progress, and let the person leave the screen without losing the result of the request.

## Live prices (read-only; no order is ever placed)

`GET /live/quotes?symbols=TCS,INFY` (at most 20 symbols):

```json
{
  "connected": true,
  "message": null,
  "quotes": {
    "TCS": {"last_price": 3500.5, "change_pct": 0.42, "label": "LIVE", "as_of": "2026-10-06T10:15:00+05:30",
            "source": "Upstox", "message": null}
  }
}
```

`label` is exactly one of `LIVE` (market open, quote under a minute old), `DELAYED` (market open and older; or a price
that is not from the last trading day, or whose time does not match this computer's clock: `message` says which),
`LAST_CLOSE` (market closed, and the price is dated the last trading day), `UNAVAILABLE`. For a share that has been
quiet, `as_of` is the time it last traded and `message` says so. Screens must show the label next to every price in
plain words (Live, Delayed, Last close, Not available) and must never show a price without its label. When
`connected` is false, `message` names the click that fixes it, and the screen shows that message instead of a price.
Poll no faster than every 15 seconds while the market is open, and not at all in a hidden tab.

## Other responses a screen must handle

- `POST /copilot/chat` with an `agent_id` that no longer exists returns HTTP 404
  `{"error": {"code": "NOT_FOUND", "message": "That agent no longer exists."}}`.
- `POST /copilot/agents/{id}/run` returns HTTP 429 `{"error": {"code": "TOO_BUSY", "message": "..."}}` when that agent is
  already running or three runs are already in progress. Show `message`; the person can try again in a moment.
- A request the engine cannot read returns HTTP 422 `{"error": {"code": "BAD_REQUEST", "message": "<one plain
  sentence>", "details": {}}}`. Show `message` as written. (A rejected agent *form* still uses `AGENT_INVALID` with
  `details.problems`.)
- When `mode` is `built_in`, `provider`, `model` and `error` are always null.
- Replies that came from an AI model have been checked by the engine: sentences that read like trading advice and halal
  statements the screener did not make are removed, links the tools did not return are removed, and the halal
  screener's own block (with its sample-data notice and not-a-fatwa line) is appended whenever the screener ran.

## What the screens must never do

- Show a Buy or Sell button, or any wording that tells the person to trade.
- Show an AI reading as green/red advice, a score, a star rating or a confidence percentage.
- Hide `disclosure`, `notes`, dissent, or a model that failed.
- Show the words terminal, command, `.env`, environment variable, API, JSON, token (use "key" instead), backend.
