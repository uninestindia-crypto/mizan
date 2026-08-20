"""Content-bound session-calendar and historical-universe authorities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlsplit

from quant_system.data.market_data import AuthorityReference, CalendarReference
from quant_system.data.market_data_evidence import canonical_sha256, utc_text


@dataclass(frozen=True, slots=True)
class ExchangeSessionV1:
    exchange_date: date
    open_at: datetime
    close_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.open_at, "open_at")
        _require_aware(self.close_at, "close_at")
        if self.open_at >= self.close_at:
            raise ValueError("exchange session open must precede close")
        if self.open_at.date() != self.exchange_date or self.close_at.date() != self.exchange_date:
            raise ValueError("exchange session timestamps must use the exchange date")

    def to_canonical_dict(self) -> dict[str, str]:
        return {
            "close_at": utc_text(self.close_at),
            "exchange_date": self.exchange_date.isoformat(),
            "open_at": utc_text(self.open_at),
        }


@dataclass(frozen=True, slots=True)
class SessionCalendarV1:
    reference: CalendarReference
    sessions: tuple[ExchangeSessionV1, ...]

    def __post_init__(self) -> None:
        if not self.sessions:
            raise ValueError("session calendar cannot be empty")
        _require_identifier(self.reference.calendar_id, "calendar_id")
        _require_identifier(self.reference.version, "calendar version")
        dates = tuple(session.exchange_date for session in self.sessions)
        if tuple(sorted(set(dates))) != dates:
            raise ValueError("session calendar dates must be unique and strictly ascending")
        for previous, current in zip(self.sessions[:-1], self.sessions[1:], strict=True):
            if previous.close_at >= current.open_at:
                raise ValueError("session calendar instants must be unique and strictly ascending")
        expected_hash = canonical_sha256(_calendar_payload(self.reference, self.sessions))
        if self.reference.content_hash != expected_hash:
            raise ValueError("session calendar content hash does not match its sessions")

    @classmethod
    def create(
        cls,
        calendar_id: str,
        version: str,
        sessions: tuple[ExchangeSessionV1, ...],
    ) -> SessionCalendarV1:
        unsigned_reference = CalendarReference(calendar_id, version, "")
        content_hash = canonical_sha256(_calendar_payload(unsigned_reference, sessions))
        return cls(CalendarReference(calendar_id, version, content_hash), sessions)

    def session_for_date(self, exchange_date: date) -> ExchangeSessionV1 | None:
        return next(
            (session for session in self.sessions if session.exchange_date == exchange_date),
            None,
        )

    def ordinal_for_close(self, close_at: datetime) -> int | None:
        return next(
            (
                ordinal
                for ordinal, session in enumerate(self.sessions)
                if session.close_at == close_at
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class HistoricalUniverseSnapshotV1:
    authority: AuthorityReference
    provider_instrument_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_authority_reference(self.authority, field_name="universe authority")
        if not self.provider_instrument_ids:
            raise ValueError("historical universe cannot be empty")
        if any(not member or len(member) > 256 for member in self.provider_instrument_ids):
            raise ValueError("historical universe members must be non-empty bounded strings")
        if tuple(sorted(set(self.provider_instrument_ids))) != self.provider_instrument_ids:
            raise ValueError("historical universe members must be unique and sorted")
        if self.authority.content_hash != canonical_sha256(self._unsigned_payload()):
            raise ValueError("historical universe content hash does not match its members")

    @classmethod
    def create(
        cls,
        *,
        authority_id: str,
        source_url: str,
        publication_date: date,
        effective_from: date,
        effective_to: date | None,
        version: str,
        provider_instrument_ids: tuple[str, ...],
    ) -> HistoricalUniverseSnapshotV1:
        if len(set(provider_instrument_ids)) != len(provider_instrument_ids):
            raise ValueError("historical universe members must be unique")
        members = tuple(sorted(provider_instrument_ids))
        unsigned_authority = AuthorityReference(
            authority_id=authority_id,
            source_url=source_url,
            publication_date=publication_date,
            effective_from=effective_from,
            effective_to=effective_to,
            version=version,
            content_hash="",
        )
        draft = cls.__new__(cls)
        object.__setattr__(draft, "authority", unsigned_authority)
        object.__setattr__(draft, "provider_instrument_ids", members)
        content_hash = canonical_sha256(draft._unsigned_payload())
        authority = AuthorityReference(
            authority_id=authority_id,
            source_url=source_url,
            publication_date=publication_date,
            effective_from=effective_from,
            effective_to=effective_to,
            version=version,
            content_hash=content_hash,
        )
        return cls(authority=authority, provider_instrument_ids=members)

    def contains(self, provider_instrument_id: str) -> bool:
        return provider_instrument_id in self.provider_instrument_ids

    def is_effective(self, exchange_date: date) -> bool:
        return _authority_is_effective(self.authority, exchange_date)

    def _unsigned_payload(self) -> dict[str, object]:
        return {
            "authority_id": self.authority.authority_id,
            "effective_from": self.authority.effective_from.isoformat(),
            "effective_to": (
                self.authority.effective_to.isoformat() if self.authority.effective_to else None
            ),
            "provider_instrument_ids": list(self.provider_instrument_ids),
            "publication_date": self.authority.publication_date.isoformat(),
            "schema_id": "quantos.historical_universe",
            "schema_version": 1,
            "source_url": self.authority.source_url,
            "version": self.authority.version,
        }


def authority_is_effective(authority: AuthorityReference, exchange_date: date) -> bool:
    return _authority_is_effective(authority, exchange_date)


def validate_authority_reference(
    authority: AuthorityReference,
    *,
    field_name: str = "authority",
) -> None:
    """Reject authority references that cannot be independently reconstructed."""
    _require_identifier(authority.authority_id, f"{field_name} id")
    _require_identifier(authority.version, f"{field_name} version")
    parsed = urlsplit(authority.source_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{field_name} source_url must be a reconstructable HTTPS location")
    if len(authority.source_url) > 2048:
        raise ValueError(f"{field_name} source_url is too long")
    if authority.effective_to is not None and authority.effective_to < authority.effective_from:
        raise ValueError(f"{field_name} effective range is invalid")


def _authority_is_effective(authority: AuthorityReference, exchange_date: date) -> bool:
    if authority.publication_date >= exchange_date or authority.effective_from > exchange_date:
        return False
    return authority.effective_to is None or exchange_date <= authority.effective_to


def _calendar_payload(
    reference: CalendarReference,
    sessions: tuple[ExchangeSessionV1, ...],
) -> dict[str, object]:
    return {
        "calendar_id": reference.calendar_id,
        "schema_id": "quantos.session_calendar",
        "schema_version": 1,
        "sessions": [session.to_canonical_dict() for session in sessions],
        "version": reference.version,
    }


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_identifier(value: str, field_name: str) -> None:
    if not value or value != value.strip() or len(value) > 128:
        raise ValueError(f"{field_name} must be a non-empty bounded identifier")
