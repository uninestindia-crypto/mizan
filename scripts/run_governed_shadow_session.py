"""Attempt a governed shadow session driven by a real model from the real evidence store.

The governed execution path is built — adapter, point-in-time bar history, maturity horizon — but
every piece of it has so far been exercised over fixture acquisitions. This runner drives it from
artefacts that a real governed trial actually published, so the difference between "tested" and
"demonstrated" stops being a matter of assertion.

It reconstructs a :class:`PromotedModelBundleV1` from evidence rather than from a constructor call:

* ``fitted_state`` and ``preprocessing`` come out of the published model manifest, so the
  intercept, coefficients and scaler are the ones the trial fitted;
* ``score_threshold`` comes off the trial start record, so execution uses the decision rule the
  model was validated under rather than a default;
* the **verdict comes from the evidence too**, and is not overridden.

That last point is the whole design. It would be trivial to pass ``PromotionState.PAPER`` here and
watch a session run. It would also be a fabricated promotion, which is precisely the class of thing
`.launch/reports/quarantine/README.md` exists to document. If the model in the store is not
promotable, this script stops and says so.

Exit codes:
    0  a governed shadow session ran
    2  no usable model evidence was found
    3  the promotion gate refused the model — the expected outcome for a RESEARCH_ONLY trial
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from quant_system.evidence import (
    EvidenceNotFound,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.execution.governed_strategy import (
    ExecutionSurface,
    GovernedExecutionError,
    GovernedModelStrategy,
    ModelEvidenceIdentityV1,
    PromotedModelBundleV1,
)
from quant_system.modeling import ModelCardV1, PromotionState
from quant_system.modeling.preprocessing import StandardizationStateV1
from quant_system.modeling.ridge import RidgeFittedStateV1

EXIT_OK: Final = 0
EXIT_NO_EVIDENCE: Final = 2
EXIT_REFUSED_BY_GATE: Final = 3


def _log(label: str, message: str) -> None:
    print(f"{label:<34}: {message}", flush=True)


def _load_models(store: EvidenceStore) -> list[dict[str, Any]]:
    """Load model metadata only through integrity-verified evidence reads."""
    return [
        dict(evidence.manifest.metadata)
        for evidence in store.list_verified(EvidenceResourceType.MODEL)
    ]


def _threshold_from_record(record: Mapping[str, Any]) -> str | None:
    parameters = record.get("parameters")
    if not isinstance(parameters, dict):
        return None
    threshold = parameters.get("score_threshold")
    return threshold if isinstance(threshold, str) else None


def _score_threshold_for(store: EvidenceStore, trial_id: str) -> str | None:
    """Read the threshold the trial was actually validated at, from its start record."""
    try:
        evidence = store.open_verified(EvidenceResourceType.TRIAL, trial_id)
    except EvidenceNotFound:
        return None
    for record in evidence.records:
        # The start record nests the fitted hyper-parameters under "parameters"; the threshold is
        # one of them, alongside l2_penalty and numpy_seed.
        threshold = _threshold_from_record(record)
        if threshold is not None:
            return threshold
    return None


def _published_symbol(record: Mapping[str, Any], model_id: str) -> str:
    symbol = record.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise GovernedExecutionError(
            f"model {model_id!r} has a published decision without a valid symbol"
        )
    return symbol


def _model_symbol_for(store: EvidenceStore, model_id: str) -> str:
    """Return the one instrument present in a model's verified published decisions.

    The governed v1 dataset is single-instrument. Accepting a caller-supplied symbol here would
    recreate Major 4 at the evidence boundary: the loader could truthfully reconstruct one model's
    coefficients while falsely declaring that they belonged to another instrument.
    """
    evidence = store.open_verified(EvidenceResourceType.MODEL, model_id)
    symbols = {_published_symbol(record, model_id) for record in evidence.records}
    if len(symbols) != 1:
        raise GovernedExecutionError(
            f"model {model_id!r} must contain exactly one published instrument, found "
            f"{sorted(symbols)!r}"
        )
    return next(iter(symbols))


def _fitted_from(metadata: dict[str, Any]) -> RidgeFittedStateV1:
    state = metadata["fitted_state"]
    return RidgeFittedStateV1(
        intercept=state["intercept"],
        coefficients=tuple(state["coefficients"]),
        l2_penalty=state["l2_penalty"],
        preprocessing_state_hash=state["preprocessing_state_hash"],
        training_target_hash=state["training_target_hash"],
    )


def _standardization_from(metadata: dict[str, Any]) -> StandardizationStateV1:
    state = metadata["preprocessing"]
    return StandardizationStateV1(
        feature_names=tuple(state["feature_names"]),
        means=tuple(state["means"]),
        scales=tuple(state["scales"]),
        zero_variance_features=tuple(state["zero_variance_features"]),
        training_feature_rows_hash=state["training_feature_rows_hash"],
    )


def _card_from(metadata: dict[str, Any]) -> ModelCardV1:
    """Build the card from published evidence, carrying the verdict the evidence records.

    The verdict is read, never chosen. A promoted model would have to have been promoted by
    ``evaluate_promotion`` against its gate policy; this script cannot and must not supply one.
    """
    return ModelCardV1(
        model_id=metadata["model_id"],
        candidate_id=metadata["candidate_id"],
        verdict=PromotionState(metadata["verdict"]),
        created_at=datetime.now(UTC),
        monitoring_limits={"deflated_sharpe_ratio": str(metadata["deflated_sharpe_ratio"])},
        halt_and_rollback_policy="halt on monitoring breach; roll back to the previous active model",
        limitations=(
            "research evidence only",
            f"multiplicity_count={metadata['multiplicity_count']}",
        ),
    )


def _report_refusal(metadata: dict[str, Any], error: GovernedExecutionError) -> None:
    print("", flush=True)
    print("REFUSED BY THE PROMOTION GATE", flush=True)
    print(f"  model_id            : {metadata['model_id']}", flush=True)
    print(f"  trial_id            : {metadata['trial_id']}", flush=True)
    print(f"  verdict in evidence : {metadata['verdict']}", flush=True)
    print(f"  deflated_sharpe     : {metadata['deflated_sharpe_ratio']}", flush=True)
    print(f"  multiplicity_count  : {metadata['multiplicity_count']}", flush=True)
    print(f"  refusal             : {error}", flush=True)
    print("", flush=True)
    print(
        "This is the gate working, not a wiring defect. No session ran, and no promotion was\n"
        "invented to make one run.",
        flush=True,
    )


# craft-allow: long-function — the fail-closed CLI transcript is deliberately linear and ordered.
def _run(args: argparse.Namespace) -> int:
    root: Path = args.evidence_root
    if not (root / "models").is_dir():
        _log("evidence", f"no models directory under {root}")
        return EXIT_NO_EVIDENCE
    store = EvidenceStore(EvidenceStoreConfig(root=root))
    models = _load_models(store)
    if not models:
        _log("evidence", f"no published models under {root}")
        return EXIT_NO_EVIDENCE

    if args.model_id:
        chosen = [m for m in models if m["model_id"] == args.model_id]
        if not chosen:
            _log("evidence", f"model {args.model_id} not found")
            return EXIT_NO_EVIDENCE
        metadata = chosen[0]
    else:
        # Best published deflated Sharpe. Choosing the strongest candidate makes the refusal
        # below the strongest possible statement: if this one cannot execute, none can.
        metadata = max(models, key=lambda m: float(m["deflated_sharpe_ratio"]))

    _log("evidence store", str(root))
    _log("published models", str(len(models)))
    _log("selected model", f"{metadata['model_id']} (trial {metadata['trial_id']})")
    _log("verdict in evidence", str(metadata["verdict"]))
    _log("published DSR", str(metadata["deflated_sharpe_ratio"]))

    threshold = _score_threshold_for(store, metadata["trial_id"])
    if threshold is None:
        _log("trial start", "score_threshold not found; cannot bind the validated decision rule")
        return EXIT_NO_EVIDENCE
    _log("score_threshold", f"{threshold} (from the trial start, not a default)")

    try:
        symbol = _model_symbol_for(store, metadata["model_id"])
    except GovernedExecutionError as error:
        _log("model symbol", str(error))
        return EXIT_NO_EVIDENCE
    _log("model symbol", f"{symbol} (from verified published decisions)")

    fitted = _fitted_from(metadata)
    standardization = _standardization_from(metadata)
    _log("fitted state", f"intercept={fitted.intercept} hash={fitted.fitted_state_hash[:16]}...")
    _log("preprocessing", f"state_hash={standardization.state_hash[:16]}...")
    _log(
        "binding",
        "OK" if fitted.preprocessing_state_hash == standardization.state_hash else "MISMATCH",
    )

    try:
        # Identity comes from the same manifest the artefacts came from, so a card cannot be
        # paired with another model's coefficients — the Red Team break this closes.
        identity = ModelEvidenceIdentityV1.from_manifest_metadata(
            metadata, score_threshold=threshold, symbol=symbol
        )
        bundle = PromotedModelBundleV1(
            candidate_id=metadata["candidate_id"],
            model_card=_card_from(metadata),
            fitted=fitted,
            standardization=standardization,
            score_threshold=threshold,
            evidence=identity,
        )
        strategy = GovernedModelStrategy(bundle, ExecutionSurface(args.surface))
    except GovernedExecutionError as error:
        _report_refusal(metadata, error)
        return EXIT_REFUSED_BY_GATE

    _log("bundle", f"accepted for surface {args.surface}")
    _log("strategy", strategy.name)
    print("", flush=True)
    print(
        "A promoted model was accepted. Running a live session additionally requires market hours\n"
        "and a live feed connection; this script stops here rather than implying it ran one.",
        flush=True,
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Attempt a governed shadow session from real evidence."
    )
    parser.add_argument("--evidence-root", type=Path, default=Path("tmp/real-training-evidence"))
    parser.add_argument("--model-id", default=None, help="defaults to the best published DSR")
    parser.add_argument(
        "--surface",
        default=ExecutionSurface.SHADOW.value,
        choices=[surface.value for surface in ExecutionSurface],
    )
    return _run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
