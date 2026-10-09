# Active work: design brief for a view-only broker connection

STATUS: COMPLETED (audits not run: usage limit reached)  
OWNER: Claude Code (Opus 5.5), founder session  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T15:05:24Z  
STARTING_REVISION: `52df4f4513a1d65733ee6b6fec320af701126271` (`main` moved during this session from `853634d4f` to this
revision because another agent committed; nothing of theirs was touched)  
WORKTREE_OR_BRANCH: `D:\Quant OS Project\Mizan` (install root), `main`. No worktree, no branch

## Objective

GOAL_LINE: G6 (primary), with G1, G2 and G4.

The founder asked (2026-10-07, chat): can the platform get a read-only connection to the user's broker, so that the
platform and its AI know the account's state without having access to it, free of cost; if so, explain how, and write
a file that another agent (Sonnet 5.5) can build from. This record covers the research, the design and that file only.
No product code is written here.

## Owned paths

- `agent_context/work/active/20261007-1505Z-claude-broker-view-brief.md` (this record)
- `agent_context/handoffs/20261007-broker-view-only-build-brief.md` (new; the build brief)

## Non-goals

- Any product code, test, screen or dependency change.
- Any call to a broker with the founder's account. Nothing was probed.
- Editing any claimed path. `docs/product/**` is claimed by `20260928-claude-retail-redesign-build.md`, so the brief
  goes in `agent_context/handoffs/`.

## Plan

1. Startup sequence: GOAL, README, CURRENT, PROTOCOL, DISK-LAYOUT, `.launch/STATE.md`, git state, active records,
   worktrees and branches, release status. DONE.
2. Read the code the feature would touch: credentials, live prices, Upstox transport, Copilot registry, tools and
   wiring, portfolio, Settings and Portfolio screens, guard tests. DONE.
3. Check current broker facts on the web (Upstox and Zerodha cost, keys, login, static-IP rules). DONE.
4. Write the brief. DONE.
5. Run both audits, then complete this record. See below.

## Current step

Complete.

## Decision rationale

- **Possible and free:** Upstox charges nothing for API access, and Zerodha's Kite Connect Personal is free with holdings,
  positions and funds. Reading needs no static IP at either broker: since 1 April 2026 both require a static IP only for
  order place/modify/cancel (Upstox also lists multi-order and GTT).
- **Login every day:** both brokers end the key daily (Upstox 03:30 IST, Kite 06:00 IST). Upstox's one-year analytics key
  is read-only, but it can read holdings only from a registered static IP. That costs money, and a laptop changes networks.
  Measured 2026-08-31: `UDAPI1221` on `/v2/user/profile`, per `20260831-NOTICE-paper-pilot-analytics-token-resolution.md`.
  So the free path is a person-initiated daily sign-in on the broker's own page.
- **"No access" is three locks:** the broker refuses orders from an app with no static IP; our code has a closed
  allowlist with a GET-only read transport and a session transport that takes no URL; the AI gets a summary only, off
  until the person turns it on. The key is kept out of the process environment, so it is narrower than today's
  `UPSTOX_ACCESS_TOKEN`, which `CredentialStore.apply_to_environment()` copies into `os.environ`.
- **Rejected:** Account Aggregator (needs a regulated FIU), Upstox extended token (business multi-client apps only),
  Angel One TOTP/PIN login (the app would hold a full sign-in), a cloud webhook relay (cost, and the key would leave
  the laptop).
- **Fixed callback port:** `launcher.py:160` picks the first free port from 8080, but the redirect address must match
  the broker registration exactly. So the brief specifies a dedicated one-shot loopback listener on `127.0.0.1:47610`.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` | main...origin/main | Untracked corporate-action authorities and market cache belong to another agent; untouched |
| `git worktree list`; `git branch --list` | 1 extra worktree, 3 extra branches | `claude/kronos-trial11-local` (claimed by `20261006-0546Z-claude-kronos-trial11-local.md`); `claude/dazzling-brown-yn5qu3`, `cloud-paper-state-rehearsal` left alone |
| `python scripts/release_status.py` | No release due | Last release v2.5.3; 0 of 3 |
| Web research (Upstox, Kite docs and forums) | DONE | Sources listed at the end of the brief |

## Files changed

- `agent_context/handoffs/20261007-broker-view-only-build-brief.md`: new; the build brief.
- This record.

## Blockers and conflicts

None for this record. The build will edit paths claimed by `20260928-claude-retail-redesign-build.md`
(`frontend/**`, `src/quant_system/server/v2/**`). The brief tells the builder to file a NOTICE under PROTOCOL 8.4,
as other agents have done for founder-requested work.

## Stop point

The brief is written. Nothing is committed (the founder did not ask for a commit).

## Next safe action

The founder hands `agent_context/handoffs/20261007-broker-view-only-build-brief.md` to Sonnet 5.5. The builder starts
at its section "Before you write any code".

