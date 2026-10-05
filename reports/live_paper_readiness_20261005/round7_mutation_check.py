# Re-runs the 13 Red Team Round 7 surviving mutants (.launch/reports/RED-TEAM-20260901-ROUND7.md, R7-08)
# against the current tree. Each mutant is applied to a SCRATCH MIRROR, never to the checkout, because
# scripts/daily_auto_sync.ps1 does `git add -A` nightly and would commit a mutant.
#
#   mirror = SP/mirror  (copy of src, scripts, tests, pyproject.toml, data/authorities,
#                        agent_context/decisions)
#   SP/suite.txt        the pytest files to run, space separated
#   SP=<dir> python round7_mutation_check.py [mutant-name-prefix ...]
#
# Result recorded in round7_mutation_results.json: before tests/test_paper_runner_wiring.py, 7 of the
# 13 survived at this revision (6 had been killed since Round 7); with it, 0 survive.
"""Apply each Round 7 survivor to a scratch mirror of the tree, one at a time, and report which the suite kills.
The repository checkout is never modified."""
import os, shutil, subprocess, sys, json
from pathlib import Path
SP = Path(os.environ["SP"]); MIRROR = SP / "mirror"; REPO = Path("/home/user/mizan")
PY = "/tmp/claude-0/venv312/bin/python"
SUITE = (SP / "suite.txt").read_text().split()
RPS = "scripts/run_paper_pilot_session.py"
LIVE = "src/quant_system/execution/mizan_live_features.py"
MUTANTS = [
 ("M1  CAS expected-hash re-bound just before the save", RPS,
  "        save_portfolio(PORTFOLIO_STATE_PATH, portfolio, portfolio_hash_at_load)",
  "        save_portfolio(PORTFOLIO_STATE_PATH, portfolio, state_hash_on_disk(PORTFOLIO_STATE_PATH))"),
 ("M2  anchor never persisted", RPS,
  "        daily_anchor_on=session_date if session_anchor_equity is not None else None,",
  "        daily_anchor_on=None,"),
 ("M10b anchor never reused on restart", RPS,
  "    persisted_anchor = anchor_to_reuse(portfolio, session_date)",
  "    persisted_anchor = None"),
 ("M17 daily baseline never anchored", RPS,
  "            if realtime and not daily_peak_anchored:",
  "            if realtime and not daily_peak_anchored and step > 100000:"),
 ("M3  rebalance coverage threshold 0.8 -> 0.26", RPS,
  "MIN_REBALANCE_COVERAGE = 0.8", "MIN_REBALANCE_COVERAGE = 0.26"),
 ("M4  exit loop never sells", RPS,
  "            for sym, pos in list(engine.positions.items()) if rebalancing and top_picks else []:",
  "            for sym, pos in []:"),
 ("M5  entry loop never buys", RPS,
  "            for sym in top_picks if rebalancing else []:",
  "            for sym in []:"),
 ("M6  tripped kill switch no longer refuses next session", RPS,
  "    if portfolio.risk_halted:", "    if portfolio.risk_halted and False:"),
 ("M7  aborted session still spends a held session", RPS,
  "        session_completed=not session_abort_reason,", "        session_completed=True,"),
 ("M9  opening quote fetch has one attempt", RPS,
  "    base_market = fetch_quotes_with_retry(universe, access_token=upstox_token)",
  "    base_market = fetch_quotes_with_retry(universe, access_token=upstox_token, attempts=1)"),
 ("M12 names ending on different sessions ranked together", LIVE,
  "    if len(distinct) > 1:", "    if len(distinct) > 1 and len(distinct) > 2:"),
 ("M14 operator not told which carried names are unquoted", RPS,
  "    if unpriced:\n        # Cost basis for these", "    if unpriced and False:\n        # Cost basis for these"),
 ("M16 a failed chunk is not a failed poll when others succeeded", RPS,
  "    if failed_chunks:\n        raise QuoteFeedError(", "    if failed_chunks and not results:\n        raise QuoteFeedError("),
]
only = sys.argv[1:] 
results = []
for name, rel, old, new in MUTANTS:
    if only and not any(name.startswith(o) for o in only): continue
    src = (REPO / rel).read_text(encoding="utf-8")
    if old not in src:
        results.append((name, "SITE-NOT-FOUND")); print(f"{name:62s} SITE NOT FOUND", flush=True); continue
    target = MIRROR / rel
    shutil.copy(REPO / rel, target)
    target.write_text(src.replace(old, new, 1), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": f"{MIRROR/'src'}:{MIRROR}"}
    p = subprocess.run([PY, "-m", "pytest", *SUITE, "-q", "--no-header", "-p", "no:cacheprovider", "-o", "addopts=", f"--basetemp={SP/'pytest-mirror'}", "-x"],
                       cwd=MIRROR, env=env, capture_output=True, text=True)
    status = "SURVIVES" if p.returncode == 0 else "killed"
    results.append((name, status)); print(f"{name:62s} {status}", flush=True)
    shutil.copy(REPO / rel, target)
json.dump(results, open(SP / "mutants.json", "w"), indent=1)
print(sum(1 for _, s in results if s == "SURVIVES"), "survive of", len(results))
