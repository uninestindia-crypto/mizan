# Agent-context safety policy

Repository context is copied into prompts, clones, logs, CI, and backups. Store the minimum durable
information needed for engineering continuity.

## Allowed

- user intent and product decisions;
- sanitized conversation summaries;
- architecture and implementation rationale;
- file paths, commit hashes, commands, and non-sensitive output summaries;
- test, benchmark, verification, and failure evidence;
- model-governance assumptions and promotion limits;
- exact stop points and next actions.

## Forbidden

- API keys, OAuth tokens, passwords, cookies, private keys, `.env` values, or credential-bearing URLs;
- full provider request/response bodies that may contain credentials or account data;
- device IDs, Windows product IDs, government identifiers, private addresses, or unnecessary PII;
- raw user chats when a sanitized engineering summary is sufficient;
- hidden chain-of-thought or requests that another agent disclose private internal reasoning;
- production/customer financial data or account positions unless explicitly governed and required.

## Required redaction

Use labels such as `[REDACTED_DEVICE_ID]`, `[REDACTED_TOKEN]`, or `[OMITTED_PERSONAL_DATA]` when the
existence of a field matters but its value does not. If a credential enters Git history, deletion is
not remediation: revoke and rotate it.

Conversation summaries have no automatic retention guarantee. Review them when the associated
decision is superseded and retain only what is still useful for project continuity.

