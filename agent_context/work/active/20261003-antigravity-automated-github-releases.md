# Active work: Automated GitHub Releases with Version Upgrading

STATUS: ACTIVE  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-03T10:14:00Z  
STARTING_REVISION: 4a47bac904a38b8c9485a3796d658b680428511b  
WORKTREE_OR_BRANCH: `D:\Quant OS Project\quant_system` on `main` (shared checkout with disjoint claims)

## Objective

1. Resolve the GitHub release problem by configuring and validating GitHub CLI authentication on the correct organization/user account (`uninestindia-crypto`).
2. Provide a fully automated GitHub release pipeline:
   - A GitHub Actions workflow (`.github/workflows/release.yml`) triggered on tag pushes (`v*`) or manual `workflow_dispatch` that builds release packages, runs verification gates, and publishes GitHub releases with assets.
   - A local automated release utility (`scripts/publish-github-release.ps1`) that increments semantic version numbers in `src/quant_system/__init__.py` and `pyproject.toml`, builds the release bundle (Inno Setup installer, zip archive, SBOM, release manifest), commits with a clean message, creates an annotated git tag, pushes to origin, and publishes the GitHub release via `gh release create`.
3. Upgrade version from 1.0.0 to 1.0.1 and publish the first automated GitHub release with all verified installer assets.

## Owned paths

- `agent_context/work/active/20261003-antigravity-automated-github-releases.md`
- `.github/workflows/release.yml`
- `scripts/publish-github-release.ps1`
- `src/quant_system/__init__.py` (version bump only)
- `pyproject.toml` (version bump only)

## Non-goals

- Touching existing uncommitted edits belonging to other sessions (`scripts/ensure_dashboard.ps1`, etc.).
- Modifying core financial models, risk rules, or backtest logic.
- Staging or committing untracked files owned by other agents.

## Plan

1. Verify GitHub CLI authentication and remote repository connectivity. [COMPLETED]
2. File active work claim record. [COMPLETED]
3. Create `.github/workflows/release.yml` for tag-driven CI release publishing.
4. Create `scripts/publish-github-release.ps1` for local version-bumping, artifact verification/compilation, and GitHub release publishing.
5. Upgrade version to 1.0.1 across `src/quant_system/__init__.py` and `pyproject.toml`.
6. Run build and packaging pipeline to produce 1.0.1 installer and portable release assets.
7. Stage only owned files, commit, tag `v1.0.1`, push to `origin/main` and `v1.0.1`.
8. Publish the GitHub release with release notes and assets.
9. Verify release on GitHub and complete documentation.

## Current step

Implementing automated release scripts and workflow.

## Decision rationale

- Dual automation approach: GitHub Actions workflow (`.github/workflows/release.yml`) handles cloud releases when CI runners and billing are healthy, while `scripts/publish-github-release.ps1` provides an immediate, battle-tested local release publisher using the local Inno Setup and PyInstaller environment. This ensures releases can be published reliably even if GitHub Actions runner minutes/billing run out.
- Semantic version bumping: `1.0.0` -> `1.0.1` updates both `pyproject.toml` and `src/quant_system/__init__.py`. PE version resources and Inno Setup installer filenames automatically inherit this version.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `gh auth switch --user uninestindia-crypto` | PASS | Switched active user to `uninestindia-crypto` |
| `gh repo view uninestindia-crypto/quant-system` | PASS | Repository verified and accessible |

## Files changed

- `agent_context/work/active/20261003-antigravity-automated-github-releases.md`: active work record

## Blockers and conflicts

None.

## Stop point

Work record created. Proceeding to implement scripts and release automation.

## Next safe action

Create `.github/workflows/release.yml` and `scripts/publish-github-release.ps1`.
