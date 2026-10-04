# Release cadence: a GitHub release after every few major updates

STATUS: Accepted  
DATE: 2026-10-04  
OWNER: Founder and QuantOS Agents

## Context

The founder wants to update the installed software each time meaningful improvements land. Releases
are built by `scripts/release.ps1`, which the lead agent is writing separately.

## Decision

A release is DUE when `python scripts/release_status.py` reports it is due:
- Three or more user-visible commits (`feat`, `fix`, `perf`) since the last `v*` tag.
- Any security fix (`security` or `credential` in subject).
- Any breaking change (`!` or `BREAKING`).
- Or whenever the founder explicitly asks.

The agent whose commit crosses the threshold cuts the release before ending its session unless the
founder says hold. Versioning follows semver:
- Patch release for fixes only.
- Minor release for new features.
- Major release only for breaking changes.

## Process

1. Run `python scripts/release_status.py`.
2. Run `powershell scripts/release.ps1`.
3. It bumps the version everywhere with `scripts/bump_version.py`, builds, tags, and publishes.
4. The installed app then shows an update-available notice.

## Rejected alternatives

- **A release on every commit**: Noise and unsigned-installer churn.
- **Calendar-based releases**: Ships nothing or too much.
- **CI-triggered releases only**: GitHub Actions has failed on account billing in this repository.

## Consequences

- Version files must always agree; `bump_version.py --check` guards it.
- Unsigned installers still show a SmartScreen warning until a certificate exists.
- The repository is private so users need GitHub access to download.
