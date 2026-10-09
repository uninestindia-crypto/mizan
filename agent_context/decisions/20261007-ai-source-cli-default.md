# Decision: the Copilot's AI defaults to the signed-in AI app; a saved key is optional

DATE: 2026-10-07
GOAL_LINE: G6 (real benefit to retail users), G3 (factory-new laptop), G4 (works without credentials in the repo)
FOUNDER INSTRUCTION: "why you set api key ai primary default for every ai feature allow user to select from
setting and default will be cli based ai"

## Decision

1. Settings has a new choice, kept in the app's saved settings: `ai_source` (`cli` by default, or `api`), an
   optional favourite app `ai_cli` (`claude`, `codex`, `gemini`), an optional favourite key provider `ai_api`, and
   `ai_fallback` (default on).
2. `cli` means the AI app already signed in on this computer (Claude Code, Codex, Gemini CLI). A person needs no
   key. `api` means a saved key first. Each kind backs the other up unless `ai_fallback` is off, so one AI that is
   down or signed out does not silence the chat. The reply always names which AI answered.
3. Every AI feature uses the same choice: chat, saved assistants, second opinions (which can name an app as
   `cli:claude` or a key provider by its name), and "Test this AI" in Settings.
4. Messages that send a person to set up an AI now point to Settings, then AI assistants, not only to keys.

## How an AI app is run (fail closed)

An AI app is a program that can act on the computer, so `copilot/cli_chat.py` runs it only like this:

- Claude Code: `-p --output-format json --tools "" --strict-mcp-config --max-turns 1` (no built-in tool, none of the
  person's add-on tools). Confirmed against Claude Code 2.1.292: a real run returned `OK` and the model name.
- Codex: `exec --sandbox read-only --skip-git-repo-check -`. Gemini CLI: `-p "<fixed instruction>"`.
- The question goes in on standard input, never on the command line. The command line is fixed in code.
- It runs in an empty temporary folder, with a cleaned environment (no saved key, token or secret).
- An app that rejects a safety switch (an old version) is refused with a plain sentence and is never run again
  without the switch. A signed-out app, a missing app and a timeout each have their own plain sentence.
- Output is capped; the wait is at least 120 seconds because these apps are slow to start.

## Residual risks, stated rather than hidden

- Codex's read-only mode and Gemini CLI can still read files. They run in an empty folder, and what they read
  could only appear in a reply the person sees, but a prompt-injected headline could ask them to. Claude Code, the
  first choice, has no tools at all.
- The Windows path (apps installed as `.cmd` shims, empty-argument quoting) is covered by unit tests with a
  stand-in program and by one real Linux run, not by a real Windows run.
- Gemini CLI cannot report whether it is signed in. Settings shows "not checked yet" until "Test this AI" is used.

## Rejected

- Keys first, apps as a backup (the old behaviour): the founder said the default must be the app.
- Retrying without a safety switch when an app rejects it: that is exactly the case that must fail closed.
- Reading the app's own sign-in files: not ours to read, and not needed.
