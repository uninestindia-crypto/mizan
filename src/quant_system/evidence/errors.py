"""Stable failures for immutable evidence operations."""


class EvidenceError(RuntimeError):
    """Base class for evidence failures safe to map at an application boundary."""


class CanonicalizationError(EvidenceError):
    """A value cannot be represented by the canonical evidence contract."""


class EvidenceIntegrityError(EvidenceError):
    """Published evidence failed structural or cryptographic verification."""


class EvidenceConflict(EvidenceError):
    """An immutable resource ID already exists with different content."""


class EvidenceNotFound(EvidenceError):
    """The requested evidence resource or active reference does not exist."""


class EvidenceLimitExceeded(EvidenceError):
    """Evidence exceeds a configured byte, row, or chunk limit."""


class EvidenceSensitiveData(EvidenceError):
    """Secret-shaped data was refused at the persistence boundary."""


class EvidenceBusy(EvidenceError):
    """Another process owns the governed evidence mutation lease."""


class EvidenceStorageError(EvidenceError):
    """The filesystem cannot safely complete evidence publication."""
