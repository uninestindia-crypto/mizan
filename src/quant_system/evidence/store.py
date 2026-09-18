"""Crash-safe immutable evidence store with verified reads."""

# craft-allow: god-file — Crash-safe immutable evidence storage, publication, and verification engine
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.evidence.canonical import (
    canonical_json_bytes,
    parse_canonical_json,
    sha256_hex,
    validate_strict_total_order,
)
from quant_system.evidence.errors import (
    EvidenceConflict,
    EvidenceIntegrityError,
    EvidenceNotFound,
    EvidenceStorageError,
)
from quant_system.evidence.io import (
    aware_utc,
    decompress_bounded,
    parse_active_reference,
    parse_jsonl,
    read_bounded,
    reject_symlink,
    write_fsynced,
)
from quant_system.evidence.lease import LeaseManager, recover_stale_lease
from quant_system.evidence.models import (
    ActiveReference,
    CommitPhase,
    CommitResult,
    EvidenceDraft,
    EvidenceIdentity,
    EvidenceManifest,
    EvidenceResourceType,
    EvidenceStoreConfig,
    IntegrityScanReport,
    RecoveryReport,
    VerifiedEvidence,
)
from quant_system.evidence.preparation import PreparedBlob, PreparedDraft, prepare_draft

PhaseHook = Callable[[CommitPhase], None]
CommitPrecondition = Callable[[], None]


class EvidenceStore:
    """Publish immutable resources and return data only after full verification."""

    def __init__(self, config: EvidenceStoreConfig) -> None:
        self.config = config
        self.root = config.root.resolve()
        self._initialize_directories()
        self._lease = LeaseManager(
            self.root / "locks" / "governed-operation.lock",
            wait_seconds=config.lease_wait_seconds,
        )

    def commit(
        self,
        draft: EvidenceDraft,
        *,
        operation_id: str,
        phase_hook: PhaseHook | None = None,
        precondition: CommitPrecondition | None = None,
        duplicate_precondition: CommitPrecondition | None = None,
    ) -> CommitResult:
        prepared = prepare_draft(draft, self.config)
        now = aware_utc(self.config.clock())
        hook = phase_hook or _no_phase_hook
        lease = self._lease.acquire(operation_id, now)
        with lease:
            existing = self._existing_result(draft, prepared)
            if existing is not None:
                if duplicate_precondition is not None:
                    duplicate_precondition()
                return existing
            if precondition is not None:
                precondition()
            self._preflight_space(prepared)

            def notify(phase: CommitPhase) -> None:
                lease.heartbeat(aware_utc(self.config.clock()))
                hook(phase)

            return self._publish(draft, prepared, now, notify)

    def open_verified(
        self,
        resource_type: EvidenceResourceType,
        resource_id: str,
    ) -> VerifiedEvidence:
        resource_directory = self._resource_directory(resource_type, resource_id)
        if not resource_directory.is_dir():
            raise EvidenceNotFound(f"evidence resource does not exist: {resource_id}")
        return self._verify_resource_directory(resource_directory, resource_type, resource_id)

    def _verify_resource_manifest(
        self,
        resource_directory: Path,
        resource_type: EvidenceResourceType,
        resource_id: str,
    ) -> EvidenceManifest:
        reject_symlink(resource_directory)
        manifest_path = resource_directory / "manifest.json"
        marker_path = resource_directory / "COMMITTED"
        if not marker_path.is_file():
            raise EvidenceIntegrityError("published evidence commit marker is missing")
        manifest_contents = read_bounded(
            manifest_path,
            self.config.max_manifest_bytes,
            description="manifest",
        )
        payload = parse_canonical_json(manifest_contents, description="manifest")
        if not isinstance(payload, dict):
            raise EvidenceIntegrityError("manifest must be an object")
        manifest_hash = payload.get("manifest_hash")
        if not isinstance(manifest_hash, str):
            raise EvidenceIntegrityError("manifest hash is missing")
        unsigned_payload = dict(payload)
        unsigned_payload.pop("manifest_hash")
        if sha256_hex(canonical_json_bytes(unsigned_payload)) != manifest_hash:
            raise EvidenceIntegrityError("manifest hash does not match its canonical payload")
        marker_contents = read_bounded(marker_path, 128, description="commit marker")
        if marker_contents != f"{manifest_hash}\n".encode():
            raise EvidenceIntegrityError("commit marker does not match manifest hash")
        manifest = EvidenceManifest.from_dict(payload)
        if manifest.resource_type != resource_type or manifest.resource_id != resource_id:
            raise EvidenceIntegrityError("manifest identity does not match its immutable path")
        return manifest

    def _verify_resource_directory(
        self,
        resource_directory: Path,
        resource_type: EvidenceResourceType,
        resource_id: str,
    ) -> VerifiedEvidence:
        manifest = self._verify_resource_manifest(resource_directory, resource_type, resource_id)
        records = self._verify_blobs(manifest)
        return VerifiedEvidence(manifest=manifest, records=records)

    # craft-allow: deep-nesting — Directory iteration with symlink and type validation guards
    def list_manifests(self, resource_type: EvidenceResourceType) -> tuple[EvidenceManifest, ...]:
        """Return verified manifests of one resource type without verifying blob bodies."""
        resource_root = self.root / resource_type.value
        reject_symlink(resource_root)
        manifests: list[EvidenceManifest] = []
        for resource_directory in sorted(resource_root.iterdir(), key=lambda path: path.name):
            reject_symlink(resource_directory)
            if not resource_directory.is_dir():
                raise EvidenceIntegrityError(
                    f"evidence catalog contains a non-directory entry: {resource_directory.name}"
                )
            manifests.append(
                self._verify_resource_manifest(
                    resource_directory, resource_type, resource_directory.name
                )
            )
        return tuple(manifests)

    # craft-allow: deep-nesting — Directory iteration with symlink and type validation guards
    def list_verified(self, resource_type: EvidenceResourceType) -> tuple[VerifiedEvidence, ...]:
        """Return every immutable resource of one type or fail on any invalid catalog entry."""
        resource_root = self.root / resource_type.value
        reject_symlink(resource_root)
        verified: list[VerifiedEvidence] = []
        for resource_directory in sorted(resource_root.iterdir(), key=lambda path: path.name):
            reject_symlink(resource_directory)
            if not resource_directory.is_dir():
                raise EvidenceIntegrityError(
                    f"evidence catalog contains a non-directory entry: {resource_directory.name}"
                )
            verified.append(self.open_verified(resource_type, resource_directory.name))
        return tuple(verified)

    def recover(self) -> RecoveryReport:
        lease_count = recover_stale_lease(
            self.root / "locks" / "governed-operation.lock",
            self.root / "quarantine" / "leases",
        )
        staging_count = 0
        staging_root = self.root / ".staging"
        quarantine = self.root / "quarantine" / "staging"
        reject_symlink(staging_root)
        for staged in sorted(staging_root.iterdir(), key=lambda path: path.name):
            reject_symlink(staged)
            quarantine.mkdir(parents=True, exist_ok=True)
            reject_symlink(quarantine)
            os.replace(staged, quarantine / f"{staged.name}-{uuid.uuid4().hex}")
            staging_count += 1
        return RecoveryReport(staging_count, lease_count)

    def set_active(
        self,
        purpose: str,
        target: EvidenceIdentity,
        *,
        before_replace: Callable[[], None] | None = None,
    ) -> ActiveReference:
        verified = self.open_verified(target.resource_type, target.resource_id)
        if verified.manifest.manifest_hash != target.manifest_hash:
            raise EvidenceIntegrityError("active target manifest hash does not match")
        now = aware_utc(self.config.clock())
        draft = ActiveReference(purpose, target, now, reference_hash="")
        reference_hash = sha256_hex(canonical_json_bytes(draft.to_dict(include_hash=False)))
        reference = replace(draft, reference_hash=reference_hash)
        final_path = self._active_path(purpose)
        temporary_path = final_path.with_name(f".{purpose}.{uuid.uuid4().hex}.tmp")
        with self._lease.acquire(f"active:{purpose}", now):
            try:
                write_fsynced(temporary_path, canonical_json_bytes(reference.to_dict()))
                if before_replace is not None:
                    before_replace()
                os.replace(temporary_path, final_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        return reference

    def resolve_active(self, purpose: str) -> VerifiedEvidence:
        path = self._active_path(purpose)
        if not path.is_file():
            raise EvidenceNotFound(f"active reference does not exist: {purpose}")
        payload = parse_canonical_json(
            read_bounded(path, self.config.max_manifest_bytes, description="active reference"),
            description="active reference",
        )
        reference = parse_active_reference(payload, purpose)
        verified = self.open_verified(
            reference.target.resource_type,
            reference.target.resource_id,
        )
        if verified.manifest.manifest_hash != reference.target.manifest_hash:
            raise EvidenceIntegrityError("active reference target hash does not match")
        return verified

    def rebuild_index(self) -> IntegrityScanReport:
        """Rebuild the deterministic valid/invalid catalog from immutable source evidence."""
        valid: list[str] = []
        invalid: list[str] = []
        referenced: set[str] = set()
        for resource_type in EvidenceResourceType:
            found_valid, found_invalid, found_blobs = self._scan_resource_type(resource_type)
            valid.extend(found_valid)
            invalid.extend(found_invalid)
            referenced |= found_blobs
        return IntegrityScanReport(
            tuple(sorted(valid)),
            tuple(sorted(invalid)),
            tuple(sorted(self._stored_blob_hashes() - referenced)),
        )

    def _stored_blob_hashes(self) -> set[str]:
        blob_root = self.root / "blobs" / "sha256"
        if not blob_root.is_dir():
            return set()
        return {
            path.name.removesuffix(".jsonl.gz")
            for path in blob_root.rglob("*.jsonl.gz")
            if path.is_file()
        }

    def scan_integrity(self) -> IntegrityScanReport:
        """Compatibility name for a full source-of-truth index rebuild."""
        return self.rebuild_index()

    def _scan_resource_type(
        self,
        resource_type: EvidenceResourceType,
    ) -> tuple[list[str], list[str], set[str]]:
        valid: list[str] = []
        invalid: list[str] = []
        referenced: set[str] = set()
        resource_root = self.root / resource_type.value
        for resource_directory in sorted(resource_root.iterdir(), key=lambda path: path.name):
            if not resource_directory.is_dir():
                # `list_manifests` and `list_verified` both treat a non-directory catalog entry as a
                # fatal integrity error. Skipping it here made this scan more permissive than the
                # read path it exists to certify: one stray file -- a partial copy, an interrupted
                # sync, an editor swapfile -- produced a clean report on a store that could not be
                # listed. Recorded rather than raised, for the same reason a corrupt resource is:
                # one bad entry must not hide the state of every other one.
                invalid.append(resource_directory.name)
                continue
            try:
                verified = self.open_verified(resource_type, resource_directory.name)
            except (EvidenceIntegrityError, EvidenceNotFound, OSError, ValueError):
                invalid.append(resource_directory.name)
            else:
                valid.append(resource_directory.name)
                referenced |= {blob.stored_hash for blob in verified.manifest.blobs}
        return valid, invalid, referenced

    def _existing_result(
        self,
        draft: EvidenceDraft,
        prepared: PreparedDraft,
    ) -> CommitResult | None:
        final_directory = self._resource_directory(draft.resource_type, draft.resource_id)
        if not final_directory.exists():
            return None
        opened = self.open_verified(draft.resource_type, draft.resource_id)
        manifest = opened.manifest
        same = (
            manifest.schema_id == draft.schema_id
            and manifest.schema_version == draft.schema_version
            and manifest.metadata == prepared.metadata
            and manifest.total_order == draft.total_order
            and manifest.canonical_records_hash == prepared.canonical_records_hash
        )
        if not same:
            raise EvidenceConflict(
                f"immutable resource ID already has different content: {draft.resource_id}"
            )
        return CommitResult(manifest, published=False, deduplicated=True)

    def _preflight_space(self, prepared: PreparedDraft) -> None:
        free = shutil.disk_usage(self.root).free
        required = prepared.stored_bytes + prepared.canonical_bytes + self.config.min_free_bytes
        if free < required:
            raise EvidenceStorageError(
                f"evidence publication requires {required} free bytes; only {free} are available"
            )

    # craft-allow: long-function - publication phases intentionally remain visible as one protocol.
    def _publish(
        self,
        draft: EvidenceDraft,
        prepared: PreparedDraft,
        created_at: datetime,
        hook: PhaseHook,
    ) -> CommitResult:
        stage = self.root / ".staging" / uuid.uuid4().hex
        stage.mkdir(parents=False, exist_ok=False)
        hook(CommitPhase.STAGING_CREATED)
        staged_blobs: list[tuple[Path, PreparedBlob]] = []
        for blob in prepared.blobs:
            staged_path = stage / blob.descriptor.relative_path
            write_fsynced(staged_path, blob.stored)
            staged_blobs.append((staged_path, blob))
        hook(CommitPhase.BLOBS_STAGED)
        for staged_path, blob in staged_blobs:
            final_path = self._contained_path(blob.descriptor.relative_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if final_path.exists():
                existing = read_bounded(
                    final_path,
                    blob.descriptor.stored_bytes,
                    description="deduplicated blob",
                )
                if sha256_hex(existing) != blob.descriptor.stored_hash:
                    raise EvidenceIntegrityError("existing content-addressed blob is corrupt")
                staged_path.unlink()
            else:
                os.replace(staged_path, final_path)
        hook(CommitPhase.BLOBS_PUBLISHED)
        unsigned = EvidenceManifest(
            resource_type=draft.resource_type,
            resource_id=draft.resource_id,
            created_at=created_at,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            metadata=prepared.metadata,
            total_order=draft.total_order,
            row_count=len(prepared.records),
            canonical_bytes=prepared.canonical_bytes,
            stored_bytes=prepared.stored_bytes,
            canonical_records_hash=prepared.canonical_records_hash,
            blobs=tuple(blob.descriptor for blob in prepared.blobs),
            manifest_hash="",
        )
        manifest_hash = sha256_hex(canonical_json_bytes(unsigned.to_dict(include_hash=False)))
        manifest = replace(unsigned, manifest_hash=manifest_hash)
        staged_resource = stage / draft.resource_type.value / draft.resource_id
        write_fsynced(staged_resource / "manifest.json", canonical_json_bytes(manifest.to_dict()))
        hook(CommitPhase.MANIFEST_STAGED)
        write_fsynced(staged_resource / "COMMITTED", f"{manifest_hash}\n".encode())
        hook(CommitPhase.COMMIT_MARKER_STAGED)
        staged_verified = self._verify_resource_directory(
            staged_resource,
            draft.resource_type,
            draft.resource_id,
        )
        if staged_verified.manifest != manifest or staged_verified.records != prepared.records:
            raise EvidenceIntegrityError("staged evidence readback does not match prepared content")
        final_resource = self._resource_directory(draft.resource_type, draft.resource_id)
        final_resource.parent.mkdir(parents=True, exist_ok=True)
        if final_resource.exists():
            raise EvidenceConflict(
                f"immutable resource appeared during publication: {draft.resource_id}"
            )
        os.replace(staged_resource, final_resource)
        hook(CommitPhase.RESOURCE_PUBLISHED)
        verified = self.open_verified(draft.resource_type, draft.resource_id)
        if verified.manifest != manifest or verified.records != prepared.records:
            raise EvidenceIntegrityError(
                "published evidence readback does not match prepared content"
            )
        shutil.rmtree(stage, ignore_errors=True)
        return CommitResult(manifest, published=True, deduplicated=False)

    def _verify_blobs(self, manifest: EvidenceManifest) -> tuple[dict[str, Any], ...]:
        records: list[dict[str, Any]] = []
        combined_hash = hashlib.sha256()
        canonical_bytes = 0
        stored_bytes = 0
        for expected_ordinal, descriptor in enumerate(manifest.blobs):
            if descriptor.ordinal != expected_ordinal:
                raise EvidenceIntegrityError("blob ordinals are not contiguous")
            expected_path = (
                f"blobs/sha256/{descriptor.stored_hash[:2]}/{descriptor.stored_hash}.jsonl.gz"
            )
            if descriptor.relative_path != expected_path:
                raise EvidenceIntegrityError("blob path is not content-addressed")
            stored = read_bounded(
                self._contained_path(descriptor.relative_path),
                descriptor.stored_bytes,
                description="blob",
            )
            if (
                len(stored) != descriptor.stored_bytes
                or sha256_hex(stored) != descriptor.stored_hash
            ):
                raise EvidenceIntegrityError("stored blob hash or size does not match")
            canonical = decompress_bounded(stored, descriptor.canonical_bytes)
            if sha256_hex(canonical) != descriptor.canonical_hash:
                raise EvidenceIntegrityError("canonical blob hash does not match")
            parsed_records = parse_jsonl(canonical)
            if len(parsed_records) != descriptor.row_count:
                raise EvidenceIntegrityError("blob row count does not match")
            records.extend(parsed_records)
            combined_hash.update(canonical)
            canonical_bytes += len(canonical)
            stored_bytes += len(stored)
        if len(records) != manifest.row_count:
            raise EvidenceIntegrityError("manifest row count does not match")
        if canonical_bytes != manifest.canonical_bytes or stored_bytes != manifest.stored_bytes:
            raise EvidenceIntegrityError("manifest byte counts do not match")
        if combined_hash.hexdigest() != manifest.canonical_records_hash:
            raise EvidenceIntegrityError("canonical records hash does not match")
        validate_strict_total_order(records, manifest.total_order)
        return tuple(records)

    def _initialize_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        reject_symlink(self.root)
        for name in (
            "blobs",
            "datasets",
            "trials",
            "models",
            "operations",
            "sessions",
            "bundles",
            "active",
            "locks",
            "quarantine",
            ".staging",
        ):
            directory = self.root / name
            directory.mkdir(exist_ok=True)
            reject_symlink(directory)

    def _resource_directory(
        self,
        resource_type: EvidenceResourceType,
        resource_id: str,
    ) -> Path:
        EvidenceDraft(
            resource_type=resource_type,
            resource_id=resource_id,
            schema_id="identity.validation",
            schema_version=1,
            metadata={},
            records=({},),
            total_order=("identity",),
        )
        return self._contained_path(f"{resource_type.value}/{resource_id}")

    def _active_path(self, purpose: str) -> Path:
        ActiveReference(
            purpose=purpose,
            target=EvidenceIdentity(EvidenceResourceType.DATASET, "dset_validation", "0" * 64),
            updated_at=datetime.now(UTC),
            reference_hash="0" * 64,
        )
        return self._contained_path(f"active/{purpose}.json")

    def _contained_path(self, relative_path: str) -> Path:
        candidate = Path(os.path.abspath(self.root / relative_path))
        if not candidate.is_relative_to(self.root):
            raise EvidenceIntegrityError("evidence path escapes configured root")
        current = self.root
        for component in candidate.relative_to(self.root).parts:
            current /= component
            reject_symlink(current)
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise EvidenceIntegrityError("evidence path resolves outside configured root")
        return candidate


def _no_phase_hook(_phase: CommitPhase) -> None:
    return None
