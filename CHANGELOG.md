# Changelog

All notable changes to **Mizan Quant OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.2.0] - 2026-10-09

### Added
- Shariah results now come from each company's own filing wherever QuantOS holds one, with the filing behind every figure and a plain "out of date" label when the filing is old. You can read newer filings from inside the app
- Fundamentals: a new screen where you set the filters and sorting yourself and compare up to four companies side by side. Each Stock page shows the company's results from its own filings with the formula and the filing behind every figure, and your Portfolio has a Fundamentals tab. Nothing is ranked or called good or bad
- Several accounts in your Portfolio: see them together or one at a time, add, edit and remove accounts, and Add to portfolio now asks which account. Each purchase shows how long it has been held, as a fact, with no tax amounts
- A top bar that tells you where you are and what needs attention: the screen and its parent, a real search field, whether the market is open, how fresh prices are, whether live prices are on and when an update is waiting
- Update and restart: Settings, About can download the new version, check it against the fingerprint published with the release, install it and open QuantOS again. Windows may ask you to confirm
- AI apps: install and sign in to Claude Code, Codex and Gemini from one plain card, with no terminal. Choose in Settings which AI answers the Copilot, and every chat is kept on this computer so you can search and carry one on

### Fixed
- A stock whose two Shariah standards disagree now reads the same result on its badge, its card and the screener tab
- The market chip says Market open, Market closed or a holiday when it knows the NSE holiday list, and says Market hours otherwise
- Add to portfolio on a stock page no longer files into the first account for people who keep several
- "Coding agents" is now "AI apps", and developer words no longer appear in anything you read

### Improved
- Company results for 412 NSE companies ship with the app, so Fundamentals and Shariah screens work on a brand-new laptop with no internet. They are out of date until you read newer filings, and say so
- Back and forward buttons sit in the new top bar

### Preserved Guards
- Keys stay strictly encrypted in local Windows Credential Manager and are never sent to external servers
- Zero unauthorized live-broker order execution — all autonomous decisions strictly sandboxed and verified
- Halal results come only from deterministic screening rules applied to a company's own figures, never from an AI model
- Company results are facts from filings, not advice, and old data is always labelled
- Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved

---

## [3.1.0] - 2026-10-08

### Added
- **Mizan Quant OS Brand Unification**: Unified institutional quantitative trading, factor research, and Mizan Shariah wealth compliance in one operating system.
- **Quant SLM Engine**: Local Small Language Model for ultra-fast, accurate market intelligence, combining deep multi-factor alpha signals, technical indicators, and embedding-gemma-2 / XRIV features.
- **Microsoft Qlib Integration**: High-performance quantitative alpha factor library, multi-factor models, and automated upstream synchronization pipeline (`.github/workflows/qlib-upstream-monitor.yml`).
- **Factory-New Laptop Offline Installer**: Standalone, drive-isolated Inno Setup distribution (`MizanQuantOS_v3.0.0_Setup.exe`) with bundled runtime and zero C-drive leakage.
- **Upstox Live Market Feeds**: Low-latency price feeds, quote streams, and portfolio synchronization.
- **Cryptographic Release Artifacts**: Generated Software Bill of Materials (`quantos-sbom.json`) and SHA-256 release checksums (`SHA256SUMS-v3.0.0.txt`).

### Fixed
- Enforced strict drive-isolated local execution with zero C: drive path leakage.
- Corporate actions provider caching with automatic historical symbol alias mapping (e.g., `HEG` -> `HEGAM`).
- Fixed walk-forward validation matrix bounds and purged look-ahead data leakage.

### Improved
- Institutional multi-factor backtesting performance and real-time risk governor checks.
- Comprehensive packaging with cryptographic SBOM and SHA-256 verification manifests.

### Preserved Guards
- Keys stay strictly encrypted in local Windows Credential Manager and are never sent to external servers.
- Zero unauthorized live-broker order execution — all autonomous decisions strictly sandboxed and verified.
- Halal screening rules remain determined by deterministic algorithmic criteria (DJIM/AAOIFI), never unverified AI hallucination.
- Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved.

---

## [2.5.0] - 2026-10-07

### Added
- **Copilot Assistant**: Instant query button (or Ctrl+J) answering from QuantOS's own data without requiring an AI key.
- **Second Opinions**: Multiple AI models read the same facts about a stock independently to surface points of agreement and disagreement.
- **Custom Agents**: Create, edit, run, and delete saved agents on the Agents screen, with four ready-made templates.
- **Live Prices**: Read-only price display from Upstox credentials with live/delayed status labeling.
- **News Headlines**: News sentiment headlines for monitored symbols.

### Fixed
- Sanitization of pasted API keys with whitespace or line breaks.
- Copilot button and side panel responsive fit across all monitor and window sizes.
- Accessible modal focus traps and screen reader hints.

### Improved
- Home screen End of Day status indicator when markets are closed.
- Dark mode contrast refinements for critical action buttons.

---

## [2.4.0] - 2026-10-05

### Added
- **Batch Key Import**: Single-step credential import from `.env` and `.env.local` files with preview and confirmation.
- **Paper Order Ticket Inbox**: Copy-ready order tickets and out-of-date notifications.
- **Order Execution Tracking**: Record fill notes and execution quality against paper books.
- **Webhooks**: Optional Slack, Discord, and ntfy notifications for pending paper book orders.
- **Health Checks**: Liveness and readiness endpoints with early warnings for NSE holiday calendar expirations.

### Fixed
- Live trading dashboard running within native desktop container.
- Accurate audit timestamps in paper pilot sessions.
- High-contrast accessibility compliance across all components.

---

## [2.3.0] - 2026-10-05

### Added
- **Unified Desktop Studio**: 1-click mode toggle between Institutional Quant and Mizan Shariah Wealth Engine.
- **Mizan Shariah Screening**: Customizable criteria (DJIM, AAOIFI) and purification calculators.
- **Zakat & Charity Ledger**: Automated purification estimation for compliance.
- **NSE Symbol History**: Automated tracking and aliasing of corporate symbol renames.

### Fixed
- Setup onboarding wizard state persistence across reloads.
- Corporate action authority caching resilience against network timeouts.

---

## [2.2.0] - 2026-10-04

### Added
- **Automated Paper Books**: Self-updating paper portfolios following NSE market closes.
- **Lightning AI Provider**: Ultra-low-latency model calls via Lightning AI cloud.
- **Upstox Analytics Integration**: Extended market data tokens and Moonshot model integration.

### Fixed
- Corporate actions provider fallback resilience.
- Paper trading state synchronization across app restarts.

---

## [2.1.0] - 2026-10-04

### Added
- **In-App Update Checker**: Automated notification when new GitHub releases are published.
- **10-Year Market Data History**: Incremental updates preserving complete historical bars.
- **Multi-Model AI Hub**: Direct support for Google Gemini, DeepSeek, and Mistral keys.
- **Built-in Market Data Downloader**: Bootstrap fresh machines without existing local data.

### Fixed
- Transaction cost calculation precision across all order sizes.
- Sanitized LLM prompt parameters to prevent temperature errors.
- Plaintext API key prevention in local configuration files.

---

## [2.0.1] - 2026-10-03

### Added
- Windows taskbar identity and system tray integration.
- Multi-agent CLI bridge and 1-click credential hub.

### Fixed
- Clean process termination on Windows session shutdown.

---

## [2.0.0] - 2026-10-03

### Added
- **QuantOS 2.0 Retail Platform**: Full consumer-grade retail interface with Strategy Lab and Market Index.
- **Native Desktop Runner**: WebView2 container with zero terminal popups.
- **Versioned API v2**: Local loopback trust boundary.
