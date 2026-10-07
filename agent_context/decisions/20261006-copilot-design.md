# The Copilot, second opinions, agents and live prices: design and what was rejected

DATE: 2026-10-06
GOAL_LINE: G6 (real benefit to retail users), serving G2, G4 and G5
OWNER_RECORD: `agent_context/work/active/20261006-claude-copilot-agent-and-live-quotes.md`
CONTRACT: `agent_context/decisions/20261006-copilot-api-contract.md` (the JSON between the screens and the engine)

## What was decided

1. **A tool-using assistant that can only read.** `src/quant_system/copilot/agent.py` runs a bounded loop (steps,
   time and repeated calls are capped). Each turn the model replies with one JSON object, either a tool call or a
   final answer. The tools are an allowlist in `copilot/tools*.py`. None can place an order or change a setting; a
   test fails if a tool name contains `order`, `buy`, `sell`, `place`, `delete`, `remove`, `save`, `set_`, `write` or
   `execute`, and another fails if a Copilot route path contains `order`, `buy`, `sell`, `trade`, `place` or
   `execute`. The assistant can only *propose* a screen to open or a second opinion to start, and a proposal can come
   only from a tool result, never from model text. The person clicks the button.
2. **It works with no AI key** (goal G4). `copilot/rules.py` answers the common questions (halal screening, price
   facts, headlines, live prices, portfolio, watchlist, paper books, costs) straight from the same tools. Anything
   else gets the menu of what it can do, never an invented answer.
3. **Independent second opinions** (`copilot/verify*.py`). Each chosen AI model reads the same fact pack in its own
   call and never sees another model's output. Three questions per model: *blind* (the one that counts), *informed*
   (adds the platform's own pick, to measure anchoring) and *recheck* (the blind question with the facts reordered, to
   measure stability). The result reports agreement, dissent with reasons, instability and anchoring, and always carries
   the disclosure that AI agreement is not evidence of an edge.
4. **A halal verdict comes only from the deterministic screener.** The fact pack carries the screener result verbatim
   with its `UNVERIFIED_SAMPLE` status; models are told not to rule on it, and any statement of theirs about halal
   status is removed and counted.
5. **Outside text is data.** Headlines, company names and any model reply are fenced in `<untrusted_data>` when they
   re-enter a prompt, and the news reader refuses documents that declare a DOCTYPE or an entity.
6. **Agents are saved data, not code.** An agent is a name, instructions, a list of read-only tools it may use and up
   to eight plain-language steps. Its instructions can change tone and focus; the prompt says they never override the
   honesty rules, and the rules come first. A run is limited to the agent's tools in both the AI and no-key paths.
7. **Live prices** (`src/quant_system/live/`) are read-only and always carry a freshness label: `LIVE`, `DELAYED`,
   `LAST_CLOSE` or `UNAVAILABLE`. A stale quote is never labelled live, an expired or missing key gets a message that
   names the next click, and the key never appears in a response, log or error.

## Why

- Traders and investors need to *see how* a conclusion was reached and to be told when it is weak. Independence and
  disclosure matter more than a confident-sounding answer. QuantOS's own research found no strategy edge that
  survives costs (`CURRENT.md`), so an AI panel agreeing is an opinion, never an edge (GOAL tripwire 4).
- Eight AI providers with three wire formats make native function calling three implementations that drift. One JSON
  text protocol works on all of them and is checked in our own code.

## Rejected alternatives

| Alternative | Why not |
|---|---|
| Native function calling per provider | Three formats, three places to drift, and a provider change breaks a tool. The text protocol is validated by us. |
| Show an AI consensus as a score, stars or colour | Looks like advice and an edge. The result shows readings in words, dissent and the disclosure instead. |
| Let models see each other's answers and "debate" | Destroys independence, which is the point. |
| Let a model write the halal verdict | The screener is deterministic and auditable; a model is neither. |
| A tool that places or prepares orders | Live-money routing is excluded (T4). Proposals are navigation only. |
| Paid sentiment APIs | A new dependency and a new key for the person to manage. A public RSS feed needs none; the rough tone is labelled rough. |
| Keep chats and second opinions on disk | Privacy and size. Results live in memory for the open screen and expire. |
| Run second opinions inside the request | A panel can take minutes. A background job with progress keeps the screen honest and usable. |

## Known limits, stated rather than hidden

- The advice and halal-ruling filters are word lists. They catch the common phrasing, not every paraphrase or other
  language; the system prompt and the screen's wording carry the rest.
- The headline tone is a keyword count. The AI readings are the better signal and are themselves opinions.
- `fundamentals` and the halal screening data are the bundled hand-entered sample (39 companies, not audited, not
  live). Every result says so. Real filings data is a founder decision (`reports/halal_docs_review/REVIEW.md`).
- Models from one provider are not independent of each other; the result says so when only one provider answered.
- `live/upstox_fetch.py` calls three private helpers in `data/upstox_parsing.py` (a file claimed elsewhere). A rename
  there breaks live prices; a public `select_quote_entry` would remove the coupling.
- After-hours and weekend price labelling was verified only against invented replies; the market-hours smoke was a
  single request while the market was open.
- Exchange holidays are not known, so a stale quote on a holiday weekday is labelled `DELAYED`, never `LIVE`.
