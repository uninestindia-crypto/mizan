#!/usr/bin/env python3
"""Maintain a proof-backed Deep Product QA coverage ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 1
STATUSES = ("not_started", "in_progress", "passed", "failed", "blocked")
TERMINAL_STATUSES = {"passed", "failed", "blocked"}
PHASES = ("audit", "awaiting_approval", "repair", "complete")
CRITICALITY_WEIGHTS = {"critical": 8, "high": 5, "medium": 3, "low": 1}
CATEGORIES = (
    "accessibility",
    "api",
    "background",
    "build",
    "compatibility",
    "data",
    "experience",
    "feature",
    "installation",
    "integration",
    "journey",
    "migration",
    "performance",
    "resilience",
    "security",
    "visual",
    "other",
)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
EVIDENCE_KINDS = (
    "accessibility",
    "log",
    "performance",
    "persistence",
    "recording",
    "screenshot",
    "trace",
)
MILESTONE_NAMES = (
    "structural_discovery",
    "runtime_discovery",
    "behavior_discovery",
    "audit_report",
    "phase2_approval",
    "final_build_identity",
    "full_regression_after_final_change",
)
AUDIT_GATE_MILESTONES = {
    "structural_discovery",
    "runtime_discovery",
    "behavior_discovery",
}
RELEASE_GATE_MILESTONES = set(MILESTONE_NAMES)
MILESTONE_ALLOWED_PHASES = {
    "structural_discovery": {"audit"},
    "runtime_discovery": {"audit"},
    "behavior_discovery": {"audit"},
    "audit_report": {"audit"},
    "phase2_approval": {"awaiting_approval"},
    "final_build_identity": {"repair"},
    "full_regression_after_final_change": {"repair"},
}
MILESTONE_REQUIRED_PHRASES = {
    "audit_report": (
        "release verdict",
        "progress dashboard",
        "product topology",
        "critical journey",
        "defects by severity",
        "consumer experience",
        "blockers",
        "prioritized repair plan",
        "approval request",
    ),
    "phase2_approval": ("approv",),
    "final_build_identity": ("build", "environment"),
    "full_regression_after_final_change": ("regression", "final change"),
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"State file does not exist: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read valid JSON from {path}: {exc}") from exc


def load_state(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise SystemExit(f"State must be a JSON object: {path}")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value["updated_at"] = utcnow()
    rendered = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def percent_down(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    raw = (Decimal(numerator) * Decimal(100)) / Decimal(denominator)
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def normalized_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    value = state.get("items", [])
    return value if isinstance(value, list) else []


def calculate_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    total_weight = 0
    terminal_weight = 0
    passed_weight = 0
    status_counts: Counter[str] = Counter()
    status_weights: Counter[str] = Counter()

    for item in items:
        weight = item.get("weight", 0)
        if not isinstance(weight, int) or weight < 0:
            weight = 0
        status = str(item.get("status", "not_started"))
        total_weight += weight
        status_counts[status] += 1
        status_weights[status] += weight
        if status in TERMINAL_STATUSES:
            terminal_weight += weight
        if status == "passed":
            passed_weight += weight

    inventory_empty = total_weight <= 0
    return {
        "items": len(items),
        "total_weight": total_weight,
        "audit_completion_pct": percent_down(terminal_weight, total_weight),
        "audit_remaining_pct": 100.0 if inventory_empty else percent_down(total_weight - terminal_weight, total_weight),
        "verified_coverage_pct": percent_down(passed_weight, total_weight),
        "remaining_to_release_pct": 100.0 if inventory_empty else percent_down(total_weight - passed_weight, total_weight),
        "status_counts": {status: status_counts.get(status, 0) for status in STATUSES},
        "status_weights": {status: status_weights.get(status, 0) for status in STATUSES},
    }


def group_metrics(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        label = str(item.get(key) or "unspecified")
        groups[label].append(item)
    return {label: calculate_metrics(groups[label]) for label in sorted(groups)}


def calculate_milestone_metrics(state: dict[str, Any]) -> dict[str, Any]:
    missing = incomplete_milestones(state, set(MILESTONE_NAMES))
    completed = len(MILESTONE_NAMES) - len(missing)
    total = len(MILESTONE_NAMES)
    return {
        "completed": completed,
        "total": total,
        "completion_pct": percent_down(completed, total),
        "remaining_pct": percent_down(total - completed, total),
        "incomplete": missing,
    }


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def summary_text(state: dict[str, Any]) -> str:
    items = normalized_items(state)
    metrics = calculate_metrics(items)
    milestone_metrics = calculate_milestone_metrics(state)
    lines = [
        f"Project: {state.get('project', '')}",
        f"Phase: {state.get('phase', '')}",
        f"Inventory items: {metrics['items']}",
        f"Audit completion: {format_pct(metrics['audit_completion_pct'])}",
        f"Audit still unexecuted: {format_pct(metrics['audit_remaining_pct'])}",
        f"Verified coverage: {format_pct(metrics['verified_coverage_pct'])}",
        f"Remaining item coverage to release: {format_pct(metrics['remaining_to_release_pct'])}",
        "Status counts: " + ", ".join(f"{status}={metrics['status_counts'][status]}" for status in STATUSES),
        f"Run milestones: {milestone_metrics['completed']}/{milestone_metrics['total']} "
        f"({format_pct(milestone_metrics['completion_pct'])} complete; "
        f"{format_pct(milestone_metrics['remaining_pct'])} remaining)",
        "Milestones still open: "
        + (", ".join(milestone_metrics["incomplete"]) if milestone_metrics["incomplete"] else "none"),
    ]
    return "\n".join(lines)


def append_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    events = state.setdefault("events", [])
    if not isinstance(events, list):
        state["events"] = events = []
    event = {"at": utcnow(), **event}
    events.append(event)


def find_item(state: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in normalized_items(state):
        if item.get("id") == item_id:
            return item
    raise SystemExit(f"Coverage item not found: {item_id}")


def normalize_artifact_files(values: list[str] | None, label: str = "artifact") -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        if not value.strip():
            continue
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"{label.capitalize()} must be an existing file: {path}")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise SystemExit(f"Could not inspect {label} file {path}: {exc}") from exc
        if size <= 0:
            raise SystemExit(f"{label.capitalize()} file is empty: {path}")
        rendered = path.as_posix()
        if rendered not in normalized:
            normalized.append(rendered)
    return normalized


def milestone_content_errors(name: str, evidence: list[str]) -> list[str]:
    required = MILESTONE_REQUIRED_PHRASES.get(name, ())
    if not required:
        return []
    chunks: list[str] = []
    for value in evidence:
        try:
            with Path(value).open("rb") as handle:
                chunks.append(handle.read(2 * 1024 * 1024).decode("utf-8", errors="ignore"))
        except OSError as exc:
            return [f"could not read milestone evidence {value}: {exc}"]
    combined = "\n".join(chunks).lower()
    missing = [phrase for phrase in required if phrase not in combined]
    if missing:
        return [f"milestone {name} evidence is missing required content: {', '.join(missing)}"]
    if name == "phase2_approval" and "phase 2" not in combined and "phase2" not in combined:
        return ["phase2_approval evidence must identify Phase 2"]
    return []


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_record_digest(record: dict[str, Any]) -> str:
    canonical = {
        key: value
        for key, value in record.items()
        if key not in {"record_sha256", "updated_at"}
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def evidence_record_errors(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"evidence record does not exist: {path}"]
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"evidence record is not valid JSON: {path}: {exc}"]
    if not isinstance(record, dict):
        return [f"evidence record must be a JSON object: {path}"]
    if record.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(f"evidence_schema_version must equal {EVIDENCE_SCHEMA_VERSION}: {path}")
    expected_record_digest = evidence_record_digest(record)
    if record.get("record_sha256") != expected_record_digest:
        errors.append(f"evidence record metadata hash does not match: {path}")
    if record.get("source") != "runtime":
        errors.append(f"evidence source must be runtime: {path}")
    if record.get("kind") not in EVIDENCE_KINDS:
        errors.append(f"evidence kind is invalid: {path}")
    for field_name in ("observed_at", "build", "environment", "platform", "scenario", "expected", "actual"):
        if not str(record.get(field_name, "")).strip():
            errors.append(f"evidence field {field_name} is required: {path}")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"evidence artifacts must be a non-empty list: {path}")
        return errors
    for index, artifact in enumerate(artifacts):
        prefix = f"evidence artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object: {path}")
            continue
        artifact_path_value = artifact.get("path")
        if not isinstance(artifact_path_value, str) or not artifact_path_value.strip():
            errors.append(f"{prefix}.path is required: {path}")
            continue
        artifact_path = Path(artifact_path_value).expanduser()
        if not artifact_path.is_file():
            errors.append(f"{prefix} file does not exist: {artifact_path}")
            continue
        try:
            size = artifact_path.stat().st_size
            digest = sha256_file(artifact_path)
        except OSError as exc:
            errors.append(f"{prefix} could not be inspected: {artifact_path}: {exc}")
            continue
        if size <= 0:
            errors.append(f"{prefix} file is empty: {artifact_path}")
        if artifact.get("size_bytes") != size:
            errors.append(f"{prefix}.size_bytes does not match current file: {artifact_path}")
        if artifact.get("sha256") != digest:
            errors.append(f"{prefix}.sha256 does not match current file: {artifact_path}")
    return errors


def normalize_new_evidence(values: list[str] | None) -> list[str]:
    normalized = normalize_artifact_files(values, "evidence record")
    errors: list[str] = []
    for value in normalized:
        errors.extend(evidence_record_errors(Path(value)))
    if errors:
        raise SystemExit("Invalid runtime evidence:\n- " + "\n- ".join(errors))
    return normalized


def make_item(data: dict[str, Any]) -> dict[str, Any]:
    item_id = str(data.get("id", "")).strip()
    title = str(data.get("title", "")).strip()
    category = str(data.get("category", "")).strip()
    criticality = str(data.get("criticality", "")).strip()
    if not item_id or not ID_PATTERN.match(item_id):
        raise ValueError("id must start with a letter or digit and contain only letters, digits, dot, underscore, colon, or hyphen")
    if not title:
        raise ValueError("title is required")
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
    if criticality not in CRITICALITY_WEIGHTS:
        raise ValueError(f"criticality must be one of: {', '.join(CRITICALITY_WEIGHTS)}")

    notes_value = data.get("notes", [])
    if isinstance(notes_value, str):
        notes = [notes_value] if notes_value.strip() else []
    elif isinstance(notes_value, list):
        notes = [str(note) for note in notes_value if str(note).strip()]
    else:
        notes = []

    return {
        "id": item_id,
        "title": title,
        "category": category,
        "criticality": criticality,
        "weight": CRITICALITY_WEIGHTS[criticality],
        "platform": str(data.get("platform", "unspecified")).strip() or "unspecified",
        "surface": str(data.get("surface", "unspecified")).strip() or "unspecified",
        "role": str(data.get("role", "unspecified")).strip() or "unspecified",
        "journey": str(data.get("journey", "")).strip(),
        "expected": str(data.get("expected", "")).strip(),
        "source": str(data.get("source", "")).strip(),
        "status": "not_started",
        "evidence": [],
        "notes": notes,
        "history": [
            {
                "at": utcnow(),
                "status": "not_started",
                "evidence": [],
                "notes": "Inventory item created",
            }
        ],
    }


def default_milestones() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "completed": False,
            "evidence": [],
            "notes": [],
            "completed_at": None,
        }
        for name in MILESTONE_NAMES
    }


def incomplete_milestones(state: dict[str, Any], required: set[str]) -> list[str]:
    milestones = state.get("milestones", {})
    if not isinstance(milestones, dict):
        return sorted(required)
    return sorted(
        name
        for name in required
        if not isinstance(milestones.get(name), dict) or not milestones[name].get("completed")
    )


def require_phase(state: dict[str, Any], allowed: set[str], action: str) -> None:
    phase = state.get("phase")
    if phase not in allowed:
        raise SystemExit(f"Cannot {action} while phase is {phase}; allowed phase(s): {', '.join(sorted(allowed))}")


def require_valid_structure(state: dict[str, Any]) -> None:
    errors = structural_errors(state)
    if errors:
        raise SystemExit("Ledger structure is invalid:\n- " + "\n- ".join(errors))


def invalidate_release_milestones(state: dict[str, Any], reason: str) -> None:
    milestones = state.get("milestones", {})
    if not isinstance(milestones, dict):
        return
    for name in ("final_build_identity", "full_regression_after_final_change"):
        milestone = milestones.get(name)
        if not isinstance(milestone, dict):
            continue
        if milestone.get("completed") or milestone.get("evidence"):
            milestone["completed"] = False
            milestone["evidence"] = []
            milestone["completed_at"] = None
            milestone.setdefault("notes", []).append(f"Invalidated at {utcnow()}: {reason}")


def structural_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")
    if not str(state.get("project", "")).strip():
        errors.append("project is required")
    if state.get("phase") not in PHASES:
        errors.append(f"phase must be one of: {', '.join(PHASES)}")
    milestones = state.get("milestones")
    if not isinstance(milestones, dict):
        errors.append("milestones must be an object")
    else:
        for name in MILESTONE_NAMES:
            milestone = milestones.get(name)
            prefix = f"milestones.{name}"
            if not isinstance(milestone, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(milestone.get("completed"), bool):
                errors.append(f"{prefix}.completed must be boolean")
            milestone_evidence = milestone.get("evidence")
            if not isinstance(milestone_evidence, list) or any(
                not isinstance(value, str) or not value.strip() for value in milestone_evidence
            ):
                errors.append(f"{prefix}.evidence must be a list of non-empty strings")
                milestone_evidence = []
            for value in milestone_evidence:
                artifact = Path(value).expanduser()
                if not artifact.is_file():
                    errors.append(f"{prefix}.evidence file does not exist: {value}")
                    continue
                try:
                    if artifact.stat().st_size <= 0:
                        errors.append(f"{prefix}.evidence file is empty: {value}")
                except OSError as exc:
                    errors.append(f"{prefix}.evidence could not be inspected: {value}: {exc}")
            if milestone.get("completed") and not milestone_evidence:
                errors.append(f"{prefix} is completed but has no evidence")
            if milestone.get("completed") and milestone_evidence:
                errors.extend(milestone_content_errors(name, milestone_evidence))
            notes = milestone.get("notes")
            if not isinstance(notes, list) or any(not isinstance(value, str) or not value.strip() for value in notes):
                errors.append(f"{prefix}.notes must be a list of non-empty strings")
    if not isinstance(state.get("items"), list):
        errors.append("items must be a list")
        return errors

    seen: set[str] = set()
    for index, item in enumerate(state["items"]):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ID_PATTERN.match(item_id):
            errors.append(f"{prefix}.id is invalid")
        elif item_id in seen:
            errors.append(f"duplicate item id: {item_id}")
        else:
            seen.add(item_id)
        if not str(item.get("title", "")).strip():
            errors.append(f"{prefix}.title is required")
        if item.get("category") not in CATEGORIES:
            errors.append(f"{prefix}.category is invalid")
        criticality = item.get("criticality")
        if criticality not in CRITICALITY_WEIGHTS:
            errors.append(f"{prefix}.criticality is invalid")
        elif item.get("weight") != CRITICALITY_WEIGHTS[criticality]:
            errors.append(f"{prefix}.weight must equal the fixed weight for {criticality}")
        status = item.get("status")
        if status not in STATUSES:
            errors.append(f"{prefix}.status is invalid")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(value, str) or not value.strip() for value in evidence):
            errors.append(f"{prefix}.evidence must be a list of non-empty strings")
            evidence = []
        else:
            for value in evidence:
                evidence_path = Path(value).expanduser()
                errors.extend(f"{prefix}: {error}" for error in evidence_record_errors(evidence_path))
        if status in {"passed", "failed"} and not evidence:
            errors.append(f"{prefix} is {status} but has no evidence")
        notes = item.get("notes")
        if not isinstance(notes, list) or any(not isinstance(value, str) or not value.strip() for value in notes):
            errors.append(f"{prefix}.notes must be a list of non-empty strings")
            notes = []
        if status == "blocked" and not notes:
            errors.append(f"{prefix} is blocked but has no reason or unblocking action")
        if not isinstance(item.get("history"), list):
            errors.append(f"{prefix}.history must be a list")
    return errors


def gate_errors(state: dict[str, Any], gate: str) -> list[str]:
    errors = structural_errors(state)
    items = normalized_items(state)
    if gate in {"audit", "release"}:
        if not items:
            errors.append("inventory is empty")
        non_terminal = [str(item.get("id")) for item in items if item.get("status") not in TERMINAL_STATUSES]
        if non_terminal:
            errors.append("audit is incomplete; non-terminal items: " + ", ".join(non_terminal))
        missing_audit_milestones = incomplete_milestones(state, AUDIT_GATE_MILESTONES)
        if missing_audit_milestones:
            errors.append("audit discovery milestones are incomplete: " + ", ".join(missing_audit_milestones))
    if gate == "release":
        non_passed = [str(item.get("id")) for item in items if item.get("status") != "passed"]
        if non_passed:
            errors.append("release gate failed; non-passed items: " + ", ".join(non_passed))
        missing_release_milestones = incomplete_milestones(state, RELEASE_GATE_MILESTONES)
        if missing_release_milestones:
            errors.append("release milestones are incomplete: " + ", ".join(missing_release_milestones))
    return errors


def print_validation(errors: list[str], gate: str) -> int:
    if errors:
        print(f"{gate.capitalize()} validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"{gate.capitalize()} validation PASSED")
    return 0


def command_init(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    if path.exists():
        raise SystemExit(f"State already exists; choose a new run path instead of overwriting it: {path}")
    now = utcnow()
    state = {
        "schema_version": SCHEMA_VERSION,
        "project": args.project.strip(),
        "run_id": (args.run_id or now).strip(),
        "phase": "audit",
        "created_at": now,
        "updated_at": now,
        "items": [],
        "milestones": default_milestones(),
        "events": [{"at": now, "type": "run_initialized", "phase": "audit"}],
    }
    if not state["project"]:
        raise SystemExit("--project must not be empty")
    atomic_write(path, state)
    print(f"Coverage ledger initialized: {path}")
    print(summary_text(state))
    return 0


def command_record_evidence(args: argparse.Namespace) -> int:
    output = state_path(args.output)
    if output.exists():
        raise SystemExit(f"Evidence record already exists; choose a new path: {output}")
    artifacts = normalize_artifact_files(args.artifact, "runtime artifact")
    if not artifacts:
        raise SystemExit("At least one --artifact is required")
    record_artifacts: list[dict[str, Any]] = []
    for value in artifacts:
        path = Path(value)
        record_artifacts.append(
            {
                "path": path.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    required_text = {
        "build": args.build,
        "environment": args.environment,
        "platform": args.platform,
        "scenario": args.scenario,
        "expected": args.expected,
        "actual": args.actual,
    }
    empty = [name for name, value in required_text.items() if not str(value).strip()]
    if empty:
        raise SystemExit("Required evidence fields are empty: " + ", ".join(empty))
    record = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "source": "runtime",
        "kind": args.kind,
        "observed_at": utcnow(),
        **{name: str(value).strip() for name, value in required_text.items()},
        "command": (args.command_line or "").strip(),
        "notes": (args.notes or "").strip(),
        "artifacts": record_artifacts,
    }
    record["record_sha256"] = evidence_record_digest(record)
    atomic_write(output, record)
    errors = evidence_record_errors(output)
    if errors:
        raise SystemExit("Generated evidence record is invalid:\n- " + "\n- ".join(errors))
    print(f"Runtime evidence record written to {output}")
    return 0


def command_set_milestone(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    require_valid_structure(state)
    require_phase(state, MILESTONE_ALLOWED_PHASES[args.name], f"complete milestone {args.name}")
    evidence = normalize_artifact_files(args.evidence, "milestone evidence")
    if not evidence:
        raise SystemExit("At least one --evidence file is required")
    content_errors = milestone_content_errors(args.name, evidence)
    if content_errors:
        raise SystemExit("Invalid milestone evidence:\n- " + "\n- ".join(content_errors))
    milestone = state["milestones"][args.name]
    milestone["completed"] = True
    milestone["evidence"] = evidence
    milestone["completed_at"] = utcnow()
    if args.notes and args.notes.strip():
        milestone.setdefault("notes", []).append(args.notes.strip())
    append_event(state, {"type": "milestone_completed", "milestone": args.name})
    atomic_write(path, state)
    print(f"Milestone completed: {args.name}")
    print(summary_text(state))
    return 0


def command_add(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    require_valid_structure(state)
    require_phase(state, {"audit", "repair"}, "add inventory")
    if any(item.get("id") == args.id for item in normalized_items(state)):
        raise SystemExit(f"Coverage item already exists: {args.id}")
    try:
        item = make_item(vars(args))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    state["items"].append(item)
    if state.get("phase") == "repair":
        invalidate_release_milestones(state, f"inventory added: {item['id']}")
    append_event(state, {"type": "item_added", "item_id": item["id"]})
    atomic_write(path, state)
    print(f"Added: {item['id']}")
    print(summary_text(state))
    return 0


def command_import(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    require_valid_structure(state)
    require_phase(state, {"audit", "repair"}, "import inventory")
    source = read_json(state_path(args.input))
    if isinstance(source, dict):
        source = source.get("items")
    if not isinstance(source, list):
        raise SystemExit("Import JSON must be a list or an object containing an items list")

    existing_ids = {str(item.get("id")) for item in normalized_items(state)}
    imported: list[dict[str, Any]] = []
    batch_ids: set[str] = set()
    for index, raw in enumerate(source):
        if not isinstance(raw, dict):
            raise SystemExit(f"Import item {index} must be an object")
        try:
            item = make_item(raw)
        except ValueError as exc:
            raise SystemExit(f"Import item {index}: {exc}") from exc
        if item["id"] in existing_ids or item["id"] in batch_ids:
            raise SystemExit(f"Duplicate imported item id: {item['id']}")
        batch_ids.add(item["id"])
        imported.append(item)

    state["items"].extend(imported)
    if state.get("phase") == "repair" and imported:
        invalidate_release_milestones(state, f"{len(imported)} inventory items imported")
    append_event(state, {"type": "items_imported", "count": len(imported), "source": str(args.input)})
    atomic_write(path, state)
    print(f"Imported {len(imported)} coverage items")
    print(summary_text(state))
    return 0


def command_set_status(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    require_valid_structure(state)
    require_phase(state, {"audit", "repair"}, "change item status")
    item = find_item(state, args.id)
    previous = item.get("status")
    new_evidence = normalize_new_evidence(args.evidence)
    notes = (args.notes or "").strip()

    if args.status in {"passed", "failed"} and not new_evidence:
        raise SystemExit(f"New evidence is required whenever status is set to {args.status}")
    if args.status == "blocked" and not notes:
        raise SystemExit("--notes must explain the blocker and unblocking action")

    evidence = item.setdefault("evidence", [])
    for value in new_evidence:
        if value not in evidence:
            evidence.append(value)
    if notes:
        item.setdefault("notes", []).append(notes)
    item["status"] = args.status
    if state.get("phase") == "repair":
        invalidate_release_milestones(state, f"status changed for {args.id}")
    item.setdefault("history", []).append(
        {
            "at": utcnow(),
            "status": args.status,
            "evidence": new_evidence,
            "notes": notes,
        }
    )
    append_event(
        state,
        {
            "type": "status_changed",
            "item_id": args.id,
            "from": previous,
            "to": args.status,
        },
    )
    atomic_write(path, state)
    print(f"Updated {args.id}: {previous} -> {args.status}")
    print(summary_text(state))
    return 0


def command_set_phase(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    require_valid_structure(state)
    current = state.get("phase")
    desired = args.phase
    allowed = {
        "audit": {"awaiting_approval"},
        "awaiting_approval": {"repair"},
        "repair": {"complete"},
        "complete": set(),
    }
    if current not in allowed or desired not in allowed[current]:
        raise SystemExit(f"Invalid phase transition: {current} -> {desired}")
    if desired == "awaiting_approval":
        errors = gate_errors(state, "audit")
        if incomplete_milestones(state, {"audit_report"}):
            errors.append("audit_report milestone must be completed before awaiting approval")
        if errors:
            return print_validation(errors, "audit")
    if desired == "repair" and incomplete_milestones(state, {"phase2_approval"}):
        return print_validation(["phase2_approval milestone must document the user's approval"], "approval")
    if desired == "complete":
        errors = gate_errors(state, "release")
        if errors:
            return print_validation(errors, "release")
    state["phase"] = desired
    append_event(state, {"type": "phase_changed", "from": current, "to": desired})
    atomic_write(path, state)
    print(f"Phase: {current} -> {desired}")
    print(summary_text(state))
    return 0


def command_summary(args: argparse.Namespace) -> int:
    state = load_state(state_path(args.state))
    if args.format == "json":
        items = normalized_items(state)
        value = {
            "project": state.get("project"),
            "phase": state.get("phase"),
            "overall": calculate_metrics(items),
            "milestone_progress": calculate_milestone_metrics(state),
            "by_category": group_metrics(items, "category"),
            "by_platform": group_metrics(items, "platform"),
            "milestones": state.get("milestones", {}),
        }
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(summary_text(state))
    return 0


def command_list(args: argparse.Namespace) -> int:
    state = load_state(state_path(args.state))
    items = normalized_items(state)
    if args.status:
        statuses = set(args.status)
        items = [item for item in items if item.get("status") in statuses]
    if args.category:
        items = [item for item in items if item.get("category") == args.category]
    if args.platform:
        items = [item for item in items if item.get("platform") == args.platform]
    for item in sorted(items, key=lambda value: str(value.get("id", ""))):
        print(
            f"{item.get('id')}\t{item.get('status')}\t{item.get('criticality')}\t"
            f"{item.get('platform')}\t{item.get('title')}"
        )
    print(f"Listed {len(items)} item(s)")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    state = load_state(state_path(args.state))
    errors = gate_errors(state, args.gate)
    return print_validation(errors, args.gate)


def escape_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def metrics_table(groups: dict[str, dict[str, Any]], label: str) -> list[str]:
    lines = [
        f"### By {label}",
        "",
        f"| {label.capitalize()} | Items | Audit complete | Verified | Remaining item coverage | Failed | Blocked |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in groups.items():
        lines.append(
            f"| {escape_cell(name)} | {metrics['items']} | {format_pct(metrics['audit_completion_pct'])} | "
            f"{format_pct(metrics['verified_coverage_pct'])} | {format_pct(metrics['remaining_to_release_pct'])} | "
            f"{metrics['status_counts']['failed']} | {metrics['status_counts']['blocked']} |"
        )
    if not groups:
        lines.append(f"| No {escape_cell(label)} inventory | 0 | 0.00% | 0.00% | 100.00% | 0 | 0 |")
    return lines


def render_report(state: dict[str, Any]) -> str:
    items = normalized_items(state)
    metrics = calculate_metrics(items)
    lines = [
        f"# Coverage Dashboard — {escape_cell(state.get('project', ''))}",
        "",
        f"- Phase: `{escape_cell(state.get('phase', ''))}`",
        f"- Inventory items: **{metrics['items']}**",
        f"- Audit completion: **{format_pct(metrics['audit_completion_pct'])}**",
        f"- Audit still unexecuted: **{format_pct(metrics['audit_remaining_pct'])}**",
        f"- Verified coverage: **{format_pct(metrics['verified_coverage_pct'])}**",
        f"- Remaining item coverage to release: **{format_pct(metrics['remaining_to_release_pct'])}**",
        f"- Run milestone completion: **{format_pct(calculate_milestone_metrics(state)['completion_pct'])}**",
        f"- Run milestone work remaining: **{format_pct(calculate_milestone_metrics(state)['remaining_pct'])}**",
        "",
        "> Audit completion counts passed, failed, and blocked items as executed. Only passed items count as verified coverage.",
        "",
        "## Run milestones",
        "",
        "| Milestone | Complete | Evidence files |",
        "|---|---|---:|",
    ]
    milestones = state.get("milestones", {})
    for name in MILESTONE_NAMES:
        milestone = milestones.get(name, {}) if isinstance(milestones, dict) else {}
        evidence = milestone.get("evidence", []) if isinstance(milestone, dict) else []
        lines.append(
            f"| {name} | {'yes' if milestone.get('completed') else 'no'} | "
            f"{len(evidence) if isinstance(evidence, list) else 0} |"
        )
    lines.extend([
        "",
        "## Status",
        "",
        "| Status | Items | Weight |",
        "|---|---:|---:|",
    ])
    for status in STATUSES:
        lines.append(f"| {status} | {metrics['status_counts'][status]} | {metrics['status_weights'][status]} |")
    lines.extend(["", *metrics_table(group_metrics(items, "category"), "category")])
    lines.extend(["", *metrics_table(group_metrics(items, "platform"), "platform")])

    unresolved = [item for item in items if item.get("status") != "passed"]
    lines.extend(
        [
            "",
            "## Items not verified",
            "",
            "| ID | Status | Criticality | Platform | Role | Title | Latest note |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for item in sorted(unresolved, key=lambda value: (-int(value.get("weight", 0)), str(value.get("id", "")))):
        notes = item.get("notes", [])
        latest_note = notes[-1] if isinstance(notes, list) and notes else ""
        lines.append(
            "| "
            + " | ".join(
                escape_cell(value)
                for value in (
                    item.get("id"),
                    item.get("status"),
                    item.get("criticality"),
                    item.get("platform"),
                    item.get("role"),
                    item.get("title"),
                    latest_note,
                )
            )
            + " |"
        )
    if not unresolved:
        lines.append("| — | — | — | — | — | Every inventory item is verified | — |")
    lines.extend(
        [
            "",
            "_Percentages describe the current inventoried scope. They do not prove that unknown future defects are impossible._",
            "",
        ]
    )
    return "\n".join(lines)


def command_report(args: argparse.Namespace) -> int:
    ledger_path = state_path(args.state)
    output = state_path(args.output)
    if output == ledger_path:
        raise SystemExit("Report output must not overwrite the coverage ledger")
    if output.exists():
        raise SystemExit(f"Report output already exists; choose a new path to preserve history: {output}")
    state = load_state(ledger_path)
    errors = structural_errors(state)
    if errors:
        return print_validation(errors, "structure")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(state), encoding="utf-8")
    print(f"Coverage dashboard written to {output}")
    print(summary_text(state))
    return 0


def add_item_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--category", required=True, choices=CATEGORIES)
    parser.add_argument("--criticality", required=True, choices=tuple(CRITICALITY_WEIGHTS))
    parser.add_argument("--platform", default="unspecified")
    parser.add_argument("--surface", default="unspecified")
    parser.add_argument("--role", default="unspecified")
    parser.add_argument("--journey", default="")
    parser.add_argument("--expected", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--notes", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="Create a new coverage ledger")
    init_parser.add_argument("--state", required=True)
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--run-id")
    init_parser.set_defaults(handler=command_init)

    evidence_parser = commands.add_parser("record-evidence", help="Create a structured runtime-evidence record")
    evidence_parser.add_argument("--output", required=True)
    evidence_parser.add_argument("--kind", required=True, choices=EVIDENCE_KINDS)
    evidence_parser.add_argument("--build", required=True)
    evidence_parser.add_argument("--environment", required=True)
    evidence_parser.add_argument("--platform", required=True)
    evidence_parser.add_argument("--scenario", required=True)
    evidence_parser.add_argument("--expected", required=True)
    evidence_parser.add_argument("--actual", required=True)
    evidence_parser.add_argument("--artifact", action="append", required=True)
    evidence_parser.add_argument("--command-line")
    evidence_parser.add_argument("--notes")
    evidence_parser.set_defaults(handler=command_record_evidence)

    milestone_parser = commands.add_parser("set-milestone", help="Complete a chronological run milestone")
    milestone_parser.add_argument("--state", required=True)
    milestone_parser.add_argument("--name", required=True, choices=MILESTONE_NAMES)
    milestone_parser.add_argument("--evidence", action="append", required=True)
    milestone_parser.add_argument("--notes")
    milestone_parser.set_defaults(handler=command_set_milestone)

    add_parser = commands.add_parser("add", help="Add one inventory item")
    add_parser.add_argument("--state", required=True)
    add_item_arguments(add_parser)
    add_parser.set_defaults(handler=command_add)

    import_parser = commands.add_parser("import-items", help="Import inventory items from JSON")
    import_parser.add_argument("--state", required=True)
    import_parser.add_argument("--input", required=True)
    import_parser.set_defaults(handler=command_import)

    status_parser = commands.add_parser("set-status", help="Set an item's execution status")
    status_parser.add_argument("--state", required=True)
    status_parser.add_argument("--id", required=True)
    status_parser.add_argument("--status", required=True, choices=STATUSES)
    status_parser.add_argument("--evidence", action="append")
    status_parser.add_argument("--notes")
    status_parser.set_defaults(handler=command_set_status)

    phase_parser = commands.add_parser("set-phase", help="Advance the chronological workflow phase")
    phase_parser.add_argument("--state", required=True)
    phase_parser.add_argument("--phase", required=True, choices=PHASES)
    phase_parser.set_defaults(handler=command_set_phase)

    summary_parser = commands.add_parser("summary", help="Print current percentages")
    summary_parser.add_argument("--state", required=True)
    summary_parser.add_argument("--format", choices=("text", "json"), default="text")
    summary_parser.set_defaults(handler=command_summary)

    list_parser = commands.add_parser("list", help="List inventory items")
    list_parser.add_argument("--state", required=True)
    list_parser.add_argument("--status", action="append", choices=STATUSES)
    list_parser.add_argument("--category", choices=CATEGORIES)
    list_parser.add_argument("--platform")
    list_parser.set_defaults(handler=command_list)

    validate_parser = commands.add_parser("validate", help="Validate structure, audit, or release gate")
    validate_parser.add_argument("--state", required=True)
    validate_parser.add_argument("--gate", choices=("structure", "audit", "release"), default="structure")
    validate_parser.set_defaults(handler=command_validate)

    report_parser = commands.add_parser("report", help="Write a Markdown coverage dashboard")
    report_parser.add_argument("--state", required=True)
    report_parser.add_argument("--output", required=True)
    report_parser.set_defaults(handler=command_report)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
