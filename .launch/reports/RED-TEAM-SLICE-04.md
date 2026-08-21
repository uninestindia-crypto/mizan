# Red Team Report - Slice 4

STATUS: **BLOCKED**
DATE: 2026-08-21
ATTACKED REVISION: `b24b4eb2eefc689b29ed4eb8ea0e64d48dfd98f4`
WORKSPACE: `D:\quant_system_workspaces\verification_clones\redteam-slice4-final-b24b4eb-20260821-054720`
ENVIRONMENT: frozen `.venv`, CPython 3.13.15, 47 packages

## Verdict

**BLOCKED. Four Blockers and seven Majors are unresolved.**

The candidate gate is genuinely green. The focused Slice 4 selection plus the evidence-store suite
reproduce 133 passing tests in this clone, and
`git diff 6a17d5e..b24b4eb -- src/quant_system/modeling src/quant_system/evidence
src/quant_system/analytics/multiplicity.py` is empty, so the eleven mutation kills in
`.launch/reports/MUTATION-SLICE-04.md` do bind the code measured here. Every finding below is
against that green tree.

Five of the six previously repaired Blockers hold on their stated scope. One holds only partially.
Three of the new Blockers are variants the repairs did not reach.

## Adjudication of the six repairs made at `6a17d5e`

| # | Repaired Blocker | Verdict | Note |
|---|---|---|---|
| 1 | Python `bool` entering exact-`int` trial fields | **HOLDS** (scope gap) | `RidgeTrialStartV1` rejects `bool` and `np.int64` on all three fields. Sibling classes `FoldSpecV1`, `StrategyMetricsV1` and `EvidenceDraft.schema_version` were not covered - see Blocker 3 and Minor 3. |
| 2 | Interrupted model/outcome publication had no recovery | **PARTIALLY HOLDS** | Replay of an open start after a failed model or outcome commit works. It does not cover a crash *after* the outcome was published (Minor 1), and the FAILED-outcome guarantee itself breaks under lease contention (Major 4). |
| 3 | Deflated Sharpe ignored sampling uncertainty and moments | **HOLDS** | DSR moves with `T`, skewness, kurtosis and `N` in the correct directions. Separate defects exist in which count is used (Major 2) and in the degenerate zero-volatility case (Major 6). |
| 4 | Dataset order and fold order contradicted each other | **HOLDS** (scope gap) | Both derived datasets sort on `(candidate_id, decision_at, instrument)`. "Instrument" means `provider_instrument_id` for features and `symbol` for labels, and the evaluator joins on `symbol` - see Major 3. |
| 5 | Simultaneous instruments compounded as separate periods | **HOLDS** | `metrics._portfolio_period_returns` produces one equal-weight return per decision time; concentration is `max(1/active_count)`. |
| 6 | `SUCCEEDED` did not resolve verified model evidence | **HOLDS** | Deleting the model, or publishing an alias resource id, both raise `MULTIPLICITY_INVALID`. The content of the resolved model is never re-derived - see Blocker 2. |

---

## Blockers

### Blocker 1 - training labels that mature inside the validation window are accepted

```
FINDING   Fold revalidation never checks that a retained training label matures before the
          validation window opens; a fold with zero purge and zero embargo is accepted
FAMILY    Assumption archaeology / data integrity (look-ahead leakage)
REPRO     scratch probe p04_leak2.py against the governed fixture:
            j = governed_training_journey()        # purges 1 row, embargoes 1 row
            move both removed rows into train_rows, set
              spec.purge_start = spec.purge_end = validation_start,
              purged_record_keys = (), embargoed_record_keys = (),
              recompute train_hash / train_row_count / train_class_balance / train_end
            evaluate_governed_ridge_fold(start, registry, features, labels, leaky_fold)
OBSERVED  LEAKY FOLD ACCEPTED (zero purge, zero embargo)
            train rows: 20 validation rows: 8
            train rows whose label matures at/after validation_start:
              ['cand_ridge_v1|INFY|2025-02-26T10:00:00.000000Z']
              exit_at 2025-02-28 09:15 IST, validation_start 2025-02-27 15:30 IST
            spec.purge_start == purge_end == validation_start: True
            ridge sharpe: 6.434418102803 dsr: 0.854984141908
          src/quant_system/modeling/validation.py:250-305 constrains purged rows
          (exit_at >= validation_start, line 284) and embargoed rows (line 289), and checks that
          every pre-validation row is accounted for as train | purged | embargoed (line 274).
          It never constrains train_rows. spec.embargo_sessions is validated only as a number
          (line 241), never against which rows were actually removed, so a fold may declare a
          two-session embargo and remove nothing.
EXPECTED  Fail closed with PARTITION_INVALID. Purging exists precisely to stop a training label
          whose outcome window overlaps the validation period from entering the fit.
BLAST     Every governed model. evaluate_governed_ridge_fold is the trust boundary that re-derives
          fold integrity from the label dataset; the caller supplies both the fold and the
          fold_spec_hashes that pin it, so nothing else can catch this. The published evidence
          records purge_start == purge_end == validation_start and looks normal. Magnitude is
          bounded by the label horizon (one row per instrument here), but the check is absent, not
          merely weak, and Slice 5 opens a holdout on the same machinery.
SEVERITY  Blocker
```

### Blocker 2 - published model evidence can be rewritten with false metrics undetected

```
FINDING   Published model evidence can be rewritten in place with false metrics and is accepted as
          content-verified; metrics_hash and prediction_hash are never re-derived on read
FAMILY    Data integrity / security surface
REPRO     scratch probe p15_tamper.py: publish one governed trial, then rewrite
          models/<model_id>/manifest.json metadata so the RIDGE report claims sharpe_ratio "99",
          total_return "12.5", deflated_sharpe_ratio "0.999999999999"; leave the decisions blob and
          metrics_hash untouched; recompute evaluation_hash using exactly the recipe in
          persisted_trials._parse_model_link; rename the resource to model_<new_hash[:24]>;
          recompute manifest_hash and COMMITTED; rebind the terminal outcome result_hash and
          outcome_hash the same way.
OBSERVED  registry STILL LOADS. multiplicity: 1
            outcome: [('trial_tamper','SUCCEEDED','283a4a789b53')]  # pragma: allowlist secret - deterministic Red Team reproduction output, not a credential.
          rebuild_index: IntegrityScanReport(
            valid_resource_ids=('model_283a4a789b5339260e960147','trial_tamper',
                                'trial_tamper_outcome'), invalid_resource_ids=())
          verified model now reports RIDGE sharpe = 99 total_return = 12.5 DSR = 0.999999999999
          its metrics_hash is still the ORIGINAL one: 320375e5c2dcdaedf8d5bc26d2d7ca72...
          recomputed metrics_hash for the claimed metrics: 82e45bf5b072013c2f062c29c27b9aed...
          metrics_hash actually binds the metrics? False
          Honest values were sharpe 6.434418102803, total_return 0.088304331575, DSR 0.854984141908.
          src/quant_system/modeling/persisted_trials.py:294-328 copies metrics, metrics_hash and
          prediction_hash verbatim out of the manifest metadata. metrics._metrics_hash and
          metrics._prediction_hash exist and are never called on any read path; a repository-wide
          grep for both names shows write-side call sites only.
EXPECTED  _parse_model_link should re-derive metrics_hash from metrics, prediction_hash from the
          decision records, and the metrics themselves from the decisions, rejecting any mismatch.
          Contract lines 46-48 and 61-64 claim "content-verified model evaluation" and "Each report
          binds prediction and metric hashes".
BLAST     Anyone consuming Slice 4 evidence, including the Verifier and Slice 5. The store's own
          integrity scan reports zero invalid resources. Completely silent: a bad model looks good
          with a governed RESEARCH_ONLY stamp. There is no external anchor - no signature, no hash
          chain, no monotonic high-water mark - anywhere in src/quant_system/evidence/.
SEVERITY  Blocker
```

### Blocker 3 - publish happens before readback verification, permanently bricking the catalog

```
FINDING   EvidenceStore._publish moves a resource into its final immutable path before verifying
          readback; a readback failure leaves a permanently unreadable resource that bricks
          list_verified for its whole type and blocks every future governed trial forever
FAMILY    Failure injection / state machine / input boundaries
REPRO     A. scratch probe p13_publish_then_verify.py
             EvidenceDraft(resource_type=TRIAL, resource_id="trial_probe",
                           schema_id="quantos.ridge_trial_start", schema_version=1,
                           metadata={"note": "x"*1_200_000},   # > max_manifest_bytes (1 MiB)
                           records=({"trial_id":"trial_probe"},), total_order=("trial_id",))
             store.commit(draft, operation_id="op-bigmeta")
          B. scratch probes p11_misc.py / p12_misc2.py
             EvidenceDraft(..., schema_version=True)           # bool satisfies `!= 1`
          C. scratch probe p17_publish_undercount.py: publish a model whose metadata
             multiplicity_count disagrees with its trial ordinal - all three commits succeed.
OBSERVED  A. commit raised: EvidenceIntegrityError manifest exceeds its declared size
             resource published to final immutable path: True
             list_verified(TRIAL): EvidenceIntegrityError manifest exceeds its declared size
             rebuild_index: invalid_resource_ids=('trial_probe',)
          B. commit raised: EvidenceIntegrityError version must be an integer
             registry after: PERMANENTLY UNREADABLE -> EvidenceIntegrityError version must be an integer
             next trial: EvidenceIntegrityError version must be an integer
             republish with correct schema_version: EvidenceIntegrityError version must be an integer
          C. published under-counted evaluation
             registry rejected the under-count: MULTIPLICITY_INVALID: persisted model evidence does
             not bind one canonical trial evaluation      # every later catalog read now fails
          src/quant_system/evidence/store.py:328 runs os.replace(staged_resource, final_resource)
          and only then calls open_verified at line 330. prepare_draft bounds record size
          (max_bundle_bytes) but never bounds metadata against max_manifest_bytes.
          src/quant_system/evidence/models.py:74 uses `self.schema_version != 1`, which True
          satisfies; _required_int at line 382 correctly rejects bool - but only on readback.
EXPECTED  Verify manifest, marker and blobs from the staging directory, then publish. A commit that
          raises must leave no resource behind, and no single bad resource may make list_verified
          unusable for an entire resource type.
BLAST     Unrecoverable state. load_persisted_trial_registry calls store.list_verified(TRIAL) and
          list_verified(MODEL), so one poisoned resource permanently blocks every subsequent
          run_persisted_ridge_trial in that store. The resource cannot be republished
          (_existing_result calls open_verified) and, under the immutability contract, cannot be
          removed. schema_version=True is strict-mypy-clean because bool subclasses int.
SEVERITY  Blocker
```

### Blocker 4 - a legal trial_id ending in `_outcome` permanently deadlocks the store

```
FINDING   A legal trial_id ending in `_outcome` collides with another trial's outcome resource id
          and permanently deadlocks the evidence store
FAMILY    Input boundaries / state machine
REPRO     scratch probe p06_outcome_collision.py
            run_persisted_ridge_trial(..., trial_id="trial_alpha_outcome", ordinal=1)   # legal id
            run_persisted_ridge_trial(..., trial_id="trial_alpha",         ordinal=2)
OBSERVED  attempt 1 published: trial_alpha_outcome / trial_alpha_outcome_outcome
          attempt 2 FAILED: EvidenceConflict immutable resource ID already has different content:
            trial_alpha_outcome
          trials dir now: ['trial_alpha','trial_alpha_outcome','trial_alpha_outcome_outcome']
          models dir now: ['model_180f470a4f50916868d02e99','model_7521a23ba860e1dfc7d131fe']
          registry starts:   [('trial_alpha_outcome',1), ('trial_alpha',2)]
          registry outcomes: [('trial_alpha_outcome', SUCCEEDED)]     # trial_alpha is open forever
          recovery attempt at ordinal 2: MULTIPLICITY_INVALID: trial ordinal must be 3
          recovery attempt at ordinal 3: MULTIPLICITY_INVALID: every persisted prior trial needs
            one terminal outcome before another start
          replay of trial_alpha: EvidenceConflict immutable resource ID already has different content
          `trial_ridge_001_outcome` matches _TRIAL_ID_PATTERN (trials.py:24) and
          outcome_resource_id is f"{trial_id}_outcome" (trials.py:78-79) with no reserved-suffix
          rule. The failing commit is the terminal-outcome commit at
          training_evidence.py:190-193, which sits OUTSIDE the try/except at lines 155-184, so the
          FAILED fallback never runs.
EXPECTED  Reject a trial_id that would collide with a derived outcome resource id, or namespace
          outcomes separately. Any terminal-outcome commit failure must leave the store usable.
BLAST     Unrecoverable state. Trial 2 has a published START and a published MODEL and can never
          receive any terminal outcome; every subsequent trial in that store is refused. The whole
          multiplicity authority is bricked with a perfectly legal identifier.
SEVERITY  Blocker
```

---

## Majors

### Major 1 - multiplicity rolls back silently when trailing trials are deleted

```
FINDING   Multiplicity is silently rolled back by deleting the trailing trial directories; the
          integrity scan still reports the store clean
FAMILY    Data integrity / assumption archaeology
REPRO     scratch probe p05b_delete_tail.py: run five governed trials, then
            rmtree trials/trial_ridge_00{2..5}, trials/trial_ridge_00{2..5}_outcome,
            models/<their model ids>
          then run one more trial at ordinal 2.
OBSERVED  attempts 1..5 published DSR 0.854984141908, 0.707209929186, 0.585763275399,
            0.507981824488, 0.452803033721 for an identical sharpe of 6.434418102803
          honest registry multiplicity: 5
          multiplicity AFTER deleting attempts 2-5: 1
          integrity scan reports invalid: ()
          orphan blobs left behind: 15
          re-run of the l2=5 attempt now reports multiplicity 2 and dsr 0.707209929186
            (honest value was 0.452803033721)
          Deleting a middle trial does fail closed on the contiguity check (trials.py:286-290), so
          only tail deletion is undetected - exactly the shape a researcher discarding unwanted
          attempts produces.
EXPECTED  A monotonic ordinal high-water anchor, an append-only chain, or an orphan-blob scan, so
          that a rolled-back catalog is detectable. store.rebuild_index() is the only integrity
          tool in the repository and it merely enumerates directories.
BLAST     Defeats the central Slice 4 claim that "the verified immutable trial catalog is the sole
          authority ... rather than caller memory". Silent, unlimited p-hacking with a 56 percent
          inflation of the headline deflated Sharpe in this reproduction.
SEVERITY  Major
```

### Major 2 - the published deflated Sharpe is frozen at the trial's own ordinal

```
FINDING   The published deflated Sharpe is frozen at the trial's own ordinal and is never
          re-deflated against the final attempt count
FAMILY    Money and counting / assumption archaeology
REPRO     scratch probe p16_last.py section (A): eight governed trials in one store, then read each
          published model's metadata.
OBSERVED  attempt 1: sharpe=6.434418102803 published DSR=0.854984141908 multiplicity_count=1
          attempt 2:                        published DSR=0.707209929186 multiplicity_count=2
          ...
          attempt 8: sharpe=6.434418102803 published DSR=0.351439355525 multiplicity_count=8
          true campaign multiplicity now: 8
          persisted_trials._parse_model_link line 266 actively REQUIRES
          multiplicity_count == start.multiplicity_ordinal, so the early number is pinned by
          contract. No API in quant_system.modeling recomputes a published DSR.
EXPECTED  Contract line 74 says "Deflated Sharpe uses the complete immutable attempt count". After
          eight attempts the complete count is 8 for every one of them. Either the evidence needs a
          re-deflation step, or the field must be named and documented as "deflated at ordinal N of
          an open campaign".
BLAST     A reader selecting the best-looking published model in an eight-attempt sweep reads
          0.854984141908 when the honest deflation is 0.351439355525 - a 2.4x overstatement of the
          slice's headline governed statistic. .launch/SLICE-04-EVIDENCE.md:74 quotes exactly this
          frozen number. Silent.
SEVERITY  Major
```

### Major 3 - two instruments sharing one symbol silently collapse to one feature row

```
FINDING   Two provider_instrument_ids sharing one symbol silently collapse to one feature row; the
          model is fitted on the wrong features and still publishes RESEARCH_ONLY
FAMILY    Data integrity (silent mis-join)
REPRO     scratch probe p08_symbol_join.py: duplicate every feature row with a second
          provider_instrument_id "ZZZ_EQ|INE009A01021", same symbol and decision_at, constant
          features "0.5"; rebuild the dataset identity; run the evaluator.
OBSERVED  poisoned feature dataset ACCEPTED by require_feature_dataset_identity;
            70 rows, 1 distinct symbol, 2 distinct instruments
          honest   coefficients: ('-0.433071069497','-0.316898169406','-0.141531745455',
                                  '0.083626184289','0.030988964734','-0.19501885852')
          poisoned coefficients: ('0','0','0','0','0','0')
          honest   ridge sharpe: 6.434418102803
          poisoned ridge sharpe: 3.27853733499
          zero-variance features named: all six
          No error, no warning; the evaluation publishes normally.
          FeatureRowV1.record_key and _derived_row_order_key use provider_instrument_id
          (rows.py:160, 432-436) but validation.py:97-99 builds
          {(row.candidate_id, row.symbol, row.decision_at): row} - the last row in sorted order
          silently wins. EQUITY_DUAL_MOMENTUM reads the same mis-joined rows
          (validation.py:119-125).
EXPECTED  Fail closed with DATASET_INTEGRITY_INVALID. Contract lines 14-16: "Feature, label, fold,
          candidate, source dataset, calendar, universe, instrument, and decision-time identities
          must agree" and "fail closed with typed codes".
BLAST     Not reachable through today's single-instrument build_feature_dataset, but the repairs
          for Blockers 4 and 5 exist specifically to support several instruments at one decision
          time, and this is the path they open. Silently produces a governed model fitted on the
          wrong instrument's features.
SEVERITY  Major
```

### Major 4 - the FAILED-outcome guarantee breaks under lease contention

```
FINDING   When the FAILED-outcome fallback commit itself fails, no terminal outcome is written, the
          original diagnosis is destroyed, and the store blocks every subsequent trial
FAMILY    Concurrency / failure injection / operability
REPRO     scratch probes p10_lease_midflight.py and p12_misc2.py section (d): another governed
          operation acquires locks/governed-operation.lock while the trial is fitting. The fit runs
          outside the lease by design; store.commit acquires and releases per commit.
OBSERVED  p10: trial raised: EvidenceBusy evidence mutation is owned by op-other-agent (pid 11836)
               trials on disk: ['trial_midflight_1']   models on disk: []
               starts: [('trial_midflight_1',1)]  outcomes: []
               next trial at ordinal 2: MULTIPLICITY_INVALID: every persisted prior trial needs one
                 terminal outcome before another start
               REPLAY of the open start: OK, dsr 0.854984141908
          p12: evaluation raises MODEL_FIT_FAILED while the lease is held elsewhere ->
               caller sees: EvidenceBusy : evidence mutation is owned by op-other (pid 5284)
               original MODEL_FIT_FAILED reachable from __context__: FileExistsError(17,'File exists')
          LeaseManager.acquire (lease.py:94-100) raises immediately on FileExistsError with no
          wait, retry or backoff.
EXPECTED  Contract lines 43-44 and evidence sheet lines 33-34: "A caught evaluation or publication
          failure still receives a typed immutable FAILED outcome, so the next ordinal remains
          usable." Neither holds. The surfaced error also does not say what to do next; nothing
          tells the operator the store is blocked pending a byte-identical replay.
BLAST     Every multi-agent workflow in this repository. One shared governed-operation.lock
          serialises all evidence publication, so two agents publishing concurrently is the
          documented normal case. The real failure code is silently replaced by a lock message.
SEVERITY  Major
```

### Major 5 - a large but legal L2 penalty aborts the fit with a false NON_FINITE_VALUE

```
FINDING   A large but contract-legal L2 penalty makes the governed fit abort with a false
          NON_FINITE_VALUE, because the internal float formatter emits non-canonical "-0"
FAMILY    Input boundaries / assumption archaeology / operability
REPRO     scratch probe p02_bigl2.py
            for pen in ("1","1000",...,"1000000000000000"):
                governed_training_journey(l2_penalty=pen); evaluate_governed_ridge_fold(...)
          and p01_negzero.py / p12_misc2.py section (f).
OBSERVED  l2=           1000000000000  OK  coeffs=('-0.000000000014', ...)
          l2=        1000000000000000  RAISED ModelingError: NON_FINITE_VALUE: fitted ridge state
                                              must use finite canonical decimal text
          l2=   100000000000000000000  RAISED ModelingError (same)
          _float_decimal(-1e-15) -> '-0';  _float_decimal(-4.9e-13) -> '-0'
          decimal_text(Decimal('-0')) == '0', so RidgeFittedStateV1 rejects its own output.
          The same defect hits predictions, which are not validated at production time:
            FoldDecisionV1(score='-0') -> ValueError: score must be finite canonical decimal text
          src/quant_system/modeling/ridge.py:169
            return format(float(value), ".12f").rstrip("0").rstrip(".") or "0"
          "-0.000000000000" becomes "-0", which is truthy, so the `or "0"` guard never fires.
EXPECTED  Emit "0". The coefficient is perfectly finite; the message blames the data and the caller
          has no way to learn the real cause is a formatter. A hyperparameter sweep - the obvious
          next use of this slice - walks straight into it, and each attempt permanently consumes a
          multiplicity ordinal with failure code NON_FINITE_VALUE.
BLAST     Any caller sweeping regularization strength, and any validation row whose ridge score
          lands in (-5e-13, 0), which raises a raw ValueError out of the governed evaluator.
SEVERITY  Major
```

### Major 6 - a candidate that never trades publishes deflated_sharpe_ratio = 0.5

```
FINDING   A candidate that never takes a position publishes deflated_sharpe_ratio = 0.5
FAMILY    Money and counting / assumption archaeology
REPRO     scratch probe p07_notrade_dsr.py: same fixture with score_threshold "1000000".
OBSERVED  threshold=   1000000: predicted UP count=0 sharpe=0 vol=0 exposure=0 trades=0
                                total_return=0 DSR=0.5
          threshold=         0: sharpe=6.434418102803 ... DSR=0.854984141908
          metrics.py:245 sets sharpe = mean/volatility*sqrt(252) if volatility > 0 else Decimal(0),
          and validation.py:367-368 returns a fabricated (0.0, 3.0) skew/kurtosis when the sample
          variance is zero. Those synthetic values flow into
          OverfittingDiagnostics.deflated_sharpe_ratio, which computes PSR(0) = 0.5.
EXPECTED  An undefined Sharpe is not zero, and PSR of a fabricated zero is not a 50 percent
          probability of a real edge. The metric contract has no "not applicable" state.
BLAST     A degenerate no-exposure candidate is published as immutable evidence claiming 0.5, which
          ranks it ABOVE every genuinely losing model. Silent. The DSR is the headline governed
          statistic of the slice.
SEVERITY  Major
```

### Major 7 - the fold's declared label horizon is never checked against the contract constant

```
FINDING   label_horizon_sessions in a fold spec is never checked against LABEL_HORIZON_SESSIONS_V1
FAMILY    Assumption archaeology
REPRO     validation.py:240-241 only asserts label_horizon_sessions >= 1 and
          embargo_sessions >= label_horizon_sessions. rows.py:24 fixes
          LABEL_HORIZON_SESSIONS_V1 = 2 and partitions.py:74 writes it, but the evaluator never
          compares. A caller-built FoldSpecV1(label_horizon_sessions=1, embargo_sessions=1) passes
          against labels that actually use a two-session horizon.
OBSERVED  Combined with Blocker 1, a fold can declare a one-session horizon, justify a one-session
          embargo, and remove no rows at all, while its published spec looks contract-compliant.
EXPECTED  Fail closed unless label_horizon_sessions == LABEL_HORIZON_SESSIONS_V1.
BLAST     Same class as Blocker 1: the declared timing contract in the published fold spec is
          decorative rather than enforced, and the fold spec hash is what the trial start pins.
SEVERITY  Major
```

---

## Minors

```
FINDING   Minor 1 - a crash after the terminal outcome was published makes replay impossible and
          the completed result unreachable through the API
FAMILY    Failure injection / operability
REPRO     scratch probe p11_misc.py section (b): patch _publish to raise immediately after the
          quantos.trial_outcome resource is moved into place, then replay the exact start.
OBSERVED  simulated crash: process killed immediately after the outcome resource was published
          trials on disk: ['trial_crash_1','trial_crash_1_outcome']
          REPLAY: ModelingError TRIAL_ALREADY_RECORDED: terminal trial cannot be resumed
EXPECTED  The trial succeeded. The caller cannot distinguish this from a failure, and the message
          does not say "this trial is already complete; read models/<id>". Contract lines 43-45
          name replay as "the supported recovery transition"; it does not cover this interruption.
SEVERITY  Minor
```

```
FINDING   Minor 2 - evaluate_governed_ridge_fold accepts a caller-invented TrialRegistryV1
FAMILY    Assumption archaeology
REPRO     scratch probes p16_last.py (B) and p17_publish_undercount.py.
OBSERVED  With three trials already in the catalog, a fabricated one-start registry produces
          "DSR 0.854984141908 multiplicity 1". Publishing it is caught on the next catalog read,
          but the three commits all succeed first and the catalog is then permanently unreadable
          (Blocker 3C).
EXPECTED  Contract lines 35-36: "a caller-supplied in-memory registry is not accepted as
          authority." The exported evaluation API accepts it and emits the number; only publication
          is bound, and that binding fails destructively rather than at write time.
SEVERITY  Minor
```

```
FINDING   Minor 3 - booleans are accepted in exact-integer fields of FoldSpecV1 and
          StrategyMetricsV1
FAMILY    Input boundaries
REPRO     scratch probe p14_repairs.py.
OBSERVED  FoldSpecV1(ordinal=True, embargo_sessions=True, label_horizon_sessions=True): ACCEPTED;
            canonical dict ordinal=True             # JSON true enters the fold spec hash
          StrategyMetricsV1 bool counts: ACCEPTED; canonical attributable_count = True
          RidgeTrialStartV1 correctly rejects bool and np.int64 on all three guarded fields.
EXPECTED  The same `type(x) is int` guard the repair added at trials.py:338-346.
SEVERITY  Minor
```

```
FINDING   Minor 4 - metric_decimal can publish a Sharpe of 14.85 next to a volatility of 0
FAMILY    Money and counting / rounding
REPRO     scratch probe p16_last.py section (D): eight decisions alternating a canonical net return
          of 1e-50 and "0".
OBSERVED  sharpe: 14.849242404917  vol: 0
          Internal arithmetic runs at prec=60; _METRIC_QUANTUM is 1e-12, so the volatility rounds
          to "0" while the ratio survives. The published Sharpe is then unverifiable from the
          published mean and volatility.
EXPECTED  Publish enough precision to reconstruct the ratio, or fail closed.
SEVERITY  Minor
```

```
FINDING   Minor 5 - trial dataset_id is unbounded and accepts RTL, zero-width and emoji characters
FAMILY    Input boundaries / data integrity
REPRO     scratch probe p16_last.py section (C).
OBSERVED  dataset_id 10k chars: ACCEPTED     dataset_id RTL+emoji: ACCEPTED
          dataset_id zero-width: ACCEPTED    architecture 129 chars: rejected
          NFC normalization in canonical_sha256 does not strip U+200B or U+202E, so
          "dset_a\u200bb" and "dset_ab" are distinct identities that render identically.
EXPECTED  The bounded charset already applied to trial_id, candidate_id and architecture. Through
          the persisted path the value must equal a derived dset_<24 hex> id, so this is reachable
          only by direct construction of RidgeTrialStartV1.
SEVERITY  Minor
```

```
FINDING   Minor 6 - a single validation decision time escapes as a raw ValueError
FAMILY    Input boundaries / operability
REPRO     scratch probe p12_misc2.py section (e):
          OverfittingDiagnostics.deflated_sharpe_ratio(estimated_sharpe=6.4, num_trials=1,
                                                       sample_length_bars=1)
OBSERVED  bars=1: ValueError: DSR counts must be exact positive integers and need at least two bars
          validation.py:142 passes len(ridge_period_returns) straight through, so a one-period fold
          escapes untyped and training_evidence.py:171 maps it to the generic
          TRIAL_EXECUTION_FAILED, losing the real reason.
EXPECTED  A typed PARTITION_INVALID before the fit, per "fail closed with typed codes".
SEVERITY  Minor
```

```
FINDING   Minor 7 - the evidence sheet prints a probability under a ratio name beside real Sharpes
FAMILY    Operability
REPRO     .launch/SLICE-04-EVIDENCE.md:74 "deflated Sharpe  : 0.854984141908" appears twelve lines
          above a table of Sharpe ratios 6.434418102803 / 0 / 3.27853733499 / -4.883509213356.
OBSERVED  The DSR is a probability in [0,1] (multiplicity.py:58-59 clamps a normal CDF). Read in
          context it looks as though deflation cut the Sharpe from 6.43 to 0.855.
EXPECTED  Label it as a probability wherever it is quoted.
SEVERITY  Minor
```

---

## Attacks that failed - verified protections

- `RidgeTrialStartV1` rejects `bool` and `np.int64` for `numpy_seed`, `multiplicity_ordinal` and
  `feature_schema_version`; `l2_penalty=True` fails with `INVALID_PARAMETER`.
- Deleting a middle trial fails closed on the contiguity rule.
- Deleting the model of a `SUCCEEDED` trial fails closed with `MULTIPLICITY_INVALID`.
- Publishing the same evaluation under an alias model resource id fails closed.
- A second concurrent trial cannot claim the same ordinal; three concurrent workers against one
  root left the store consistent with exactly one published trial (`p09_concurrent.sh`).
- Replay of an open start after a failed model or outcome commit recovers correctly and
  content-deduplicates the already-published model.
- Preprocessing is fitted on training rows only; validation rows do not enter the state hash.
- Zero-variance features are named explicitly and use scale one; none are silently dropped.
- Money is `Decimal` end to end; the only floats are the documented ridge numerics and the DSR.
- Resource ids cannot traverse paths; symlinks are rejected; secret-shaped keys are rejected.
- Metadata nested at `MAX_CANONICAL_DEPTH` is caught before publication.
- `git diff 6a17d5e..b24b4eb -- src/quant_system/modeling src/quant_system/evidence
  src/quant_system/analytics/multiplicity.py` is empty, so the mutation evidence binds.

## Not probed

- Feature correctness and point-in-time discipline inside `features.py` and `labels.py`; owned by
  the certified Slice 3 and not re-attacked here.
- Arithmetic consistency of `net_return` against `gross_return` and `component_costs`. Slice 4
  consumes Slice 3's cost-bound labels by identity hash and never re-derives them; effective-dated
  NSE fees are Slice 7.
- Real crash injection: SIGKILL, power loss, disk full mid-`os.replace`, torn fsync. All
  interruption probes were in-process exception injection and `min_free_bytes` was set to 0.
- Multi-instrument behaviour end to end. `build_feature_dataset` is single-instrument, so the
  portfolio-aggregation and concentration repairs could only be attacked through hand-built
  datasets and folds.
- Scale. The largest fixture is 55 sessions and 70 feature rows. No million-row dataset, no query
  counting, no memory profile of `list_verified`, which materialises and hashes every resource of a
  type on every single trial start.
- Windows-specific lease recovery through `_windows_process_identity`: PID reuse and
  handle-permission failure paths were not exercised.
- Cross-filesystem `os.replace`; staging and final storage share one root by construction.
- Unicode round-trip through any presentation layer; this slice has no UI or API surface.
- Numerical reproducibility on a second architecture; the contract limits that claim to the same
  verified architecture and lock file.
- Whether Slice 5's holdout machinery inherits the fold-validation hole in Blocker 1; only Slice 4
  code was read.
- The full `scripts/run-slice4-gates.ps1` sweep was deliberately not re-run; it is known green and
  the budget went to attacks. Only the focused suite was rerun to establish the baseline.

## Coverage

Families run: all twelve. Probes attempted: 17 scratch programs plus one three-process concurrency
run. Targets: `src/quant_system/modeling/` (16 modules), `src/quant_system/evidence/` (8 modules),
`src/quant_system/analytics/multiplicity.py`, `.launch/SLICE-04-CONTRACT.md`,
`.launch/SLICE-04-EVIDENCE.md`, `.launch/reports/MUTATION-SLICE-04.md`, and the twelve Slice 4 and
evidence-store test modules. Baseline confirmed green in this clone before attacking:

```text
pytest tests/test_modeling_*.py tests/test_multiplicity.py tests/test_evidence_store.py -q
133 passed in 4.53s
```

No source file in this clone was modified. Every probe was written to the session scratchpad and
imported the clone through `PYTHONPATH`. The install root `D:\quant_system` was never read or
written.
