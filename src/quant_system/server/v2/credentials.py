"""API keys and tokens in Windows Credential Manager, never in a file written by QuantOS.

Values are write-only from the UI's point of view: the API reports whether a secret is set and where
it came from, never the secret itself. Stored secrets are copied into the process environment at
startup (without overriding a value already set, e.g. from ``.env``), which is how the existing
provider clients read them.
"""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass

TARGET_PREFIX = "QuantOS:"
_MAX_BLOB = 5 * 512  # CRED_MAX_CREDENTIAL_BLOB_SIZE for generic credentials


@dataclass(frozen=True, slots=True)
class SecretSpec:
    name: str
    label: str
    group: str
    help: str


SECRETS: tuple[SecretSpec, ...] = (
    SecretSpec("UPSTOX_API_KEY", "Upstox API key", "Upstox", "From your Upstox developer app."),
    SecretSpec(
        "UPSTOX_ACCESS_TOKEN",
        "Upstox access token",
        "Upstox",
        "Expires every day around 3:30 AM; paste a fresh one each trading day.",
    ),
    SecretSpec(
        "UPSTOX_ANALYTICS_TOKEN", "Upstox analytics token", "Upstox", "Read-only market data token."
    ),
    SecretSpec("ANTHROPIC_API_KEY", "Anthropic API key", "AI assistants", "For Claude models."),
    SecretSpec("OPENAI_API_KEY", "OpenAI API key", "AI assistants", "For OpenAI models."),
    SecretSpec(
        "HF_TOKEN", "Hugging Face token", "Research", "Only for downloading research models."
    ),
)
_NAMES = {spec.name for spec in SECRETS}


class CredentialError(RuntimeError):
    """The credential store refused an operation."""


class CredentialStore:
    """Thin wrapper over ``CredWriteW``/``CredReadW``/``CredDeleteW`` for generic credentials."""

    def __init__(self, prefix: str = TARGET_PREFIX) -> None:
        self._api: _WinCredApi | None = _WinCredApi() if sys.platform == "win32" else None
        self._prefix = prefix

    @property
    def available(self) -> bool:
        return self._api is not None

    def get(self, name: str) -> str | None:
        _check_name(name)
        return self._api.read(self._prefix + name) if self._api else None

    def set(self, name: str, value: str) -> None:
        _check_name(name)
        cleaned = value.strip()
        if not cleaned:
            raise CredentialError("The value is empty.")
        if len(cleaned.encode("utf-8")) > _MAX_BLOB:
            raise CredentialError("The value is too long for Windows Credential Manager.")
        if self._api is None:
            raise CredentialError("Windows Credential Manager is not available on this system.")
        self._api.write(self._prefix + name, cleaned)

    def delete(self, name: str) -> bool:
        _check_name(name)
        return self._api.delete(self._prefix + name) if self._api else False

    def status(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for spec in SECRETS:
            stored = self.get(spec.name) is not None
            in_env = bool(os.environ.get(spec.name))
            out.append(
                {
                    "name": spec.name,
                    "label": spec.label,
                    "group": spec.group,
                    "help": spec.help,
                    "stored": stored,
                    "active": in_env,
                    "source": "credential_manager"
                    if stored
                    else ("environment" if in_env else None),
                }
            )
        return out

    def apply_to_environment(self) -> list[str]:
        """Copy stored secrets into ``os.environ`` where not already set. Returns the names applied."""
        applied: list[str] = []
        for spec in SECRETS:
            if os.environ.get(spec.name):
                continue
            value = self.get(spec.name)
            if value:
                os.environ[spec.name] = value
                applied.append(spec.name)
        return applied


def _check_name(name: str) -> None:
    if name not in _NAMES:
        raise CredentialError(f"{name} is not a secret QuantOS manages.")


class _WinCredApi:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self) -> None:
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        self._credential = CREDENTIAL
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        self._write = advapi.CredWriteW
        self._write.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        self._write.restype = wintypes.BOOL
        self._read = advapi.CredReadW
        self._read.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(CREDENTIAL)),
        ]
        self._read.restype = wintypes.BOOL
        self._delete = advapi.CredDeleteW
        self._delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._delete.restype = wintypes.BOOL
        self._free = advapi.CredFree
        self._free.argtypes = [ctypes.c_void_p]
        self._free.restype = None

    def write(self, target: str, value: str) -> None:
        blob = value.encode("utf-8")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = self._credential()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "QuantOS"
        if not self._write(ctypes.byref(credential), 0):
            raise CredentialError(
                f"Windows refused to store the secret (error {ctypes.get_last_error()})."
            )

    def read(self, target: str) -> str | None:
        pointer = ctypes.POINTER(self._credential)()
        if not self._read(target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == self.ERROR_NOT_FOUND:
                return None
            raise CredentialError(f"Windows refused to read the secret (error {error}).")
        try:
            credential = pointer.contents
            size = int(credential.CredentialBlobSize)
            raw = bytes(
                ctypes.cast(
                    credential.CredentialBlob, ctypes.POINTER(ctypes.c_ubyte * size)
                ).contents
            )
            return raw.decode("utf-8")
        finally:
            self._free(pointer)

    def delete(self, target: str) -> bool:
        if self._delete(target, self.CRED_TYPE_GENERIC, 0):
            return True
        if ctypes.get_last_error() == self.ERROR_NOT_FOUND:
            return False
        raise CredentialError(
            f"Windows refused to delete the secret (error {ctypes.get_last_error()})."
        )
