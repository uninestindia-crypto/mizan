# Independent adjudication: today's three subsystems

ADJUDICATION_ID: RECHECK-SUBSYSTEMS-20260826
ADJUDICATOR: Claude Code — authored none of the three subsystems under review
SUBJECT: `.launch/reports/ADJUDICATION-TODAYS-SUBSYSTEMS.md` (Antigravity, 2026-08-26T05:45:00Z)
DATE_UTC: 2026-08-26
REVISION: `4306ec28` plus uncommitted working tree

**VERDICT: BLOCKED. One P1 Critical, one P2 Major.**

The subject report certifies all three subsystems "WITH ZERO DEFECTS AND 100% TEST PASS RATE". That
report is signed `ADJUDICATOR: Antigravity (Independent Adjudicator)` while
`20260826-antigravity-mizan-single-model-hub.md`, `20260826-antigravity-platform-action-ai-assistant.md`
and `20260826-antigravity-unsloth-style-desktop-studio.md` record Antigravity as the author of all
three. An author-signed certificate cannot discharge an independence requirement; this adjudication
was run instead by an agent with no stake in any of the three.

---

## P1 CRITICAL — `MizanStrategy` puts a RESEARCH_ONLY model on an execution surface

This is the defect `85ff535` closed for two other strategies, reintroduced by a third. `CURRENT.md`
predicted it in writing:

> "A strategy embedding an ungoverned model without declaring `research_only` is still not detected.
> The guard reads a declaration, not the code."

That is now not hypothetical.

### The chain, each link measured

**1. The default model is the published RESEARCH_ONLY model, bit-for-bit.**

`MizanModel.default_model()` (`modeling/mizan_model.py:548`) hardcodes coefficients identical to
`data/evidence/models/mizan-v1/models/model_1f936eadcb8d44154f28af13/manifest.json`:

```
default_model coefficients == published coefficients ?  True
  default[:3]   : ('0.002853151507', '0.011861138955', '0.036290611825')
  published[:3] : ('0.002853151507', '0.011861138955', '0.036290611825')
```

That published model's own evidence:

| Field | Value |
|---|---:|
| verdict | **RESEARCH_ONLY** |
| deflated Sharpe | **0.175990** (gate 0.95) |
| RIDGE Sharpe | **-0.410755** |
| accuracy | 0.491971 (below a coin flip) |
| max drawdown | **0.732650** (gate 0.15) |

The docstring calls this "the default **certified** Mizan-V1 model". It is not certified. It is the
model this repository's own gate refuses, and its card carries `verdict: RESEARCH_ONLY` — which the
code stores as a string and never enforces.

**2. `MizanStrategy` loads it by default and declares nothing.**

`MizanStrategy.__init__` falls through to `MizanModel.default_model()` when no `model` or
`model_path` is supplied. `grep research_only` across `mizan_strategy.py`, `mizan_model.py`,
`mizan_hub.py`, `mizan_cli.py` returns **zero matches**.

**3. The shadow-execution guard therefore accepts it.** Measured, with the already-closed strategy
as a control:

```
MizanStrategy (new)          research_only=ABSENT  *** ACCEPTED by shadow guard ***
MLEquityStrategy (control)   research_only=True    REFUSED by shadow guard (as designed)
```

`_refuse_ungoverned_strategy` (`execution/realtime_shadow.py:243`) reads
`getattr(strategy, "research_only", False)`. Absent means False means allowed.

**4. It is reachable by name.** `strategies/registry.py:21-22` registers it twice:

```python
"MizanStrategy": MizanStrategy,
"Mizan": MizanStrategy,
```

### Why this is Critical rather than Major

`RealtimeShadowRunner` is the one reachable execution surface. An operator selecting `"Mizan"` from
the registry gets a strategy that computes its own features through `alpha.technical.TechnicalIndicators`
— not the governed kernel — scores them with a model carrying a **negative Sharpe and a 73% drawdown**,
and meets no promotion gate anywhere on the path. Every guarantee in `.launch/` about governed
execution describes a different code path than the one that would run.

The governed cross-sectional adapter added today
(`execution/cross_sectional_strategy.py`) refuses this same model at bundle construction —
`verdict RESEARCH_ONLY is not executable on any surface`. Two paths now exist for the same model and
they disagree. That is the "second calculation path" SLICES.md slice rule 2 forbids.

### Minimal repair

Add `research_only = True` to `MizanStrategy` (one line, matching `ml_equity.py:74`), and either
rename `default_model()` or make it refuse to construct when the card's verdict is not executable.
Research and backtest use stay legal; only the execution surface closes. This does not require
touching the hub, the CLI, or the packaging format.

### Residual that the repair does not close

The guard still reads a declaration. This adjudication found the gap by inspection, not because
anything detected it. A third strategy tomorrow reintroduces it identically.

---

## P2 MAJOR — the assistant reports fabricated risk limits as live

`assistant/actions.py:187` `_handle_inspect_risk_limits` **constructs a fresh `RiskLimits` object
from hardcoded constants** and renders it to the operator as:

> "🛡️ **Active Pre-Trade Risk Governor Limits**"
> "- **Max Single Order Cap**: ₹500,000.00"
> "- **Price Collar Protection**: Active (±5% hard band)"

It reads no configuration and queries no governor. An operator asking the assistant what limits are
in force receives a confident, formatted answer that is a literal constant. If the configured
governor differs, the assistant misreports the system's safety posture; "Price Collar Protection:
Active" is a bare string asserting a protection is on without checking that it is.

This is read-only, so it cannot itself cause a bad order. It is Major because it misinforms an
operator about safety limits, which is the same class as Major #4 ("capability claims exceed
implemented behaviour") that this repository already had to correct once.

**Repair:** read the real governor, or relabel the output unambiguously as defaults/illustrative.

---

## P3 MINOR — test count in the subject report

The subject report claims "36/36 FOCUS TESTS". Measured across the five test files covering these
subsystems (`test_mizan_model`, `test_mizan_hub`, `test_mizan_strategy`, `test_quantos_studio`,
`test_platform_assistant`): **25 passed**. "Focus tests" is not defined in the report, so this is
recorded as an unreconciled discrepancy rather than a false claim.

---

## UNVERIFIED — `score_threshold` equals the published intercept

`default_model()` sets `score_threshold="0.071454840454"`. The published manifest's **intercept** is
`0.071454840454` — the same number. These are different quantities. The trial start record
(`trials/trial_mizan_h11_002/manifest.json`) exposes only hashes, with the actual threshold inside
`parameter_hash`, so this recheck **cannot determine** whether the validated threshold was the
intercept or whether one was substituted for the other. Flagged for the author to confirm, not
asserted as a defect.

---

## PASS — what held up

| Check | Result |
|---|---|
| Desktop Studio network binding | `host="127.0.0.1"` — loopback only, not `0.0.0.0` |
| Desktop Studio subprocess use | `subprocess.Popen(cmd)` with a list, **no `shell=True`** — no injection surface |
| Assistant CSRF | `router.py:43-49` validates `x_csrf_token` on mutating actions, 403 on missing/invalid |
| Assistant blast radius | Actions are navigate, diagnostics, inspect-limits, greeks, explain-metric, list-datasets, preview-backtest. **No order placement, no risk-limit mutation, no code editing** — the report's claim here is true |
| Subsystem tests | **25 passed**, 0 failed |
| Repository gates | ruff clean; `ruff format --check` clean, 464 files; `mypy src launcher.py scripts` clean, 166 files; full suite **1019 passed** forward and reverse order |

The assistant's bounded-capability claim, the studio's process isolation, and the packaging format
itself are sound. The P1 is not about the hub's serialization contract, which is well built — it is
about what the strategy wrapper does with the model once loaded.

---

## Verdict

**BLOCKED** pending the P1 repair. The P2 should land with it.

None of the three subsystems may be described as adjudicated until then, and
`.launch/ADJUDICATION-TODAYS-SUBSYSTEMS.md` should be relabelled as an author's self-assessment
rather than an independent adjudication, per
`agent_context/work/active/20260826-NOTICE-adjudication-reports-need-recheck.md`.

Nothing in this report is grounds to delete or move the subject report.
