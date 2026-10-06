# No-Terminal Law: users run everything from the app

STATUS: Accepted  
DATE: 2026-10-06  
OWNER: Founder (instruction), recorded by Claude Code

## Context

The founder, 2026-10-06: "everything should be from platform done frontend aka panel and not terminal or backend
since trader, investor are non technical person in terms of coding and development, and make it rule it should not
be repeated."

An audit of the new app the same day found the interface already breaks that standard in three places (below).
Earlier in the conversation the founder also said they add AI keys for the **Copilot** "and not to run in terminal".

## Decision

**Every capability a user needs is operable from the app's own screens.** A user is never asked to open a terminal,
type a command, edit a file, set an environment variable, restart a service, or use a backend, API or developer tool.

Definition of "delivered": the capability has a screen, the screen explains itself in plain language, every failure it
can hit has a plain-language message that names the next click (for example "Add your Upstox token in Settings"), and
a person who has never seen code can complete it. An engine without its screen is **not delivered**.

What stays developer-only: source, tests, scripts, CLIs, the API, CI, release tooling. Nothing a user needs may depend
on them.

## Checklist for any agent, before calling a feature done

1. Can a first-time, non-technical user do it using only the app's screens? If a step needs anything else, it is not done.
2. Does any user-facing text mention a terminal, command, file edit, environment variable name, `.env`, JSON or an
   API? Rewrite it in plain words.
3. Is configuration entered in a form, with a "test" or preview, not in a file?
4. Does every error say what to click next, not what a developer would run?
5. Did you add a screen for each new capability, in the same change as the engine?

## Guard tests

- `frontend/src/lib/noTerminalRule.test.ts` fails when user-facing text in the app adds a terminal, command-line,
  environment-variable or file-edit instruction. Existing violations are listed below as **known debt** and may only
  shrink.
- `tests/test_no_terminal_copy.py` applies the same rule to the user-facing strings of `src/quant_system/copilot/` and
  `src/quant_system/live/`.

## Known debt found on 2026-10-06 (to fix, not to copy)

| Where | What it asks of the user | Fix |
|---|---|---|
| `frontend/src/components/AgentCliBridge.tsx` (Settings, AI assistants) | "Open in terminal"; an "Advanced: run your own command in a terminal" box; Gemini sign-in in a terminal window | Founder to decide: remove the section, or keep only one-click install and browser sign-in. The Copilot (API keys) replaces its purpose. |
| `frontend/src/pages/Settings.tsx` (Orders reminder) | "set QUANTOS_ORDERS_WEBHOOK_URL ... and restart QuantOS" | A form in Settings: address, format, Test, Save. |
| `frontend/src/pages/Settings.tsx` (keys callout, badges) | Mentions ".env" in plain labels | Reword to "your saved settings file" or drop it; the import card is the in-app route. |
| Backend messages shown to users, for example `data/upstox.py` "Configure a valid UPSTOX_ACCESS_TOKEN and retry" | An environment variable name | Map to "Add your Upstox token in Settings, then Accounts and keys." |

## Rejected alternatives

- **Document the terminal steps better.** Fails the founder's definition: the user should not need them at all.
- **A "developer mode" the user must find.** Same failure, one click further away.
- **Allow it where it is "just once".** Setup is exactly where non-technical users give up.
