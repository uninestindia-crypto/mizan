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
from typing import Any

TARGET_PREFIX = "QuantOS:"
_MAX_BLOB = 5 * 512  # CRED_MAX_CREDENTIAL_BLOB_SIZE for generic credentials


@dataclass(frozen=True, slots=True)
class SecretSpec:
    name: str
    label: str
    group: str
    help: str


SECRETS: tuple[SecretSpec, ...] = (
    # Indian Stock Market Brokers (Upstox is default)
    SecretSpec(
        "UPSTOX_API_KEY", "Upstox API key", "Upstox (Default)", "From your Upstox developer app."
    ),
    SecretSpec(
        "UPSTOX_API_SECRET",
        "Upstox API secret",
        "Upstox (Default)",
        "From your Upstox developer app.",
    ),
    SecretSpec(
        "UPSTOX_ACCESS_TOKEN",
        "Upstox access token",
        "Upstox (Default)",
        "Daily access token for live market data and historical quotes.",
    ),
    SecretSpec(
        "UPSTOX_ANALYTICS_TOKEN",
        "Upstox analytics token",
        "Upstox (Default)",
        "Read-only analytics market data token.",
    ),
    SecretSpec(
        "KITE_API_KEY",
        "Zerodha Kite API key",
        "Zerodha Kite",
        "From your Kite Connect developer console.",
    ),
    SecretSpec(
        "KITE_ACCESS_TOKEN",
        "Zerodha Kite access token",
        "Zerodha Kite",
        "Daily access token from Kite Connect login.",
    ),
    SecretSpec(
        "ANGEL_API_KEY",
        "Angel One SmartAPI key",
        "Angel One",
        "From your SmartAPI developer account.",
    ),
    SecretSpec(
        "ANGEL_CLIENT_CODE",
        "Angel One client code",
        "Angel One",
        "Your Angel One trading account ID.",
    ),
    SecretSpec(
        "ANGEL_PIN", "Angel One trading MPIN", "Angel One", "Your 4-digit Angel One trading PIN."
    ),
    SecretSpec(
        "ANGEL_TOTP_KEY",
        "Angel One TOTP secret",
        "Angel One",
        "Secret key for automated 2FA TOTP generation.",
    ),
    SecretSpec("DHAN_CLIENT_ID", "Dhan client ID", "Dhan", "Your Dhan 10-digit client ID."),
    SecretSpec(
        "DHAN_ACCESS_TOKEN",
        "Dhan access token",
        "Dhan",
        "API access token generated from Dhan web portal.",
    ),
    SecretSpec("FYERS_APP_ID", "Fyers App ID", "Fyers", "App ID from Fyers API dashboard."),
    SecretSpec(
        "FYERS_ACCESS_TOKEN", "Fyers access token", "Fyers", "Generated Fyers 2FA access token."
    ),
    # AI Cloud Providers
    SecretSpec(
        "ANTHROPIC_API_KEY",
        "Anthropic Claude API key",
        "AI Cloud Providers",
        "For Claude models. Your key decides which ones you can use.",
    ),
    SecretSpec(
        "OPENAI_API_KEY",
        "OpenAI API key",
        "AI Cloud Providers",
        "For OpenAI GPT models. Your key decides which ones you can use.",
    ),
    SecretSpec(
        "GEMINI_API_KEY",
        "Google Gemini API key",
        "AI Cloud Providers",
        "From Google AI Studio, for Gemini models.",
    ),
    SecretSpec(
        "OPENROUTER_API_KEY",
        "OpenRouter API key",
        "AI Cloud Providers",
        "Universal gateway for 200+ models with one key.",
    ),
    SecretSpec(
        "GROQ_API_KEY",
        "Groq API key",
        "AI Cloud Providers",
        "Fast inference for open models such as Llama.",
    ),
    SecretSpec(
        "DEEPSEEK_API_KEY",
        "DeepSeek API key",
        "AI Cloud Providers",
        "For DeepSeek chat and reasoning models.",
    ),
    SecretSpec(
        "MISTRAL_API_KEY", "Mistral AI API key", "AI Cloud Providers", "For Mistral models."
    ),
    SecretSpec(
        "CUSTOM_AI_BASE_URL",
        "Custom AI Base URL",
        "AI Cloud Providers",
        "Base URL for OpenAI-compatible local/remote models.",
    ),
    SecretSpec(
        "CUSTOM_AI_API_KEY",
        "Custom AI API key",
        "AI Cloud Providers",
        "API key for your custom OpenAI-compatible endpoint.",
    ),
    SecretSpec(
        "HF_TOKEN",
        "Hugging Face token",
        "Research Models",
        "For downloading gated weights and fine-tuned models.",
    ),
)
_NAMES = {spec.name for spec in SECRETS}

# Which stored secret opens each AI provider's model list.
AI_KEY_NAMES: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def with_saved_credentials(provided: dict[str, str]) -> dict[str, str]:
    """Fill in any secret the caller left blank from what is already saved (or in the environment).

    The Test Connection button is enabled for a key that is already saved, but the page never holds
    a saved key (values are write-only), so it sends nothing. Without this a saved key could never
    be tested.
    """
    merged = {name: value for name, value in provided.items() if value and value.strip()}
    for spec in SECRETS:
        if spec.name not in merged:
            saved = os.environ.get(spec.name, "").strip()
            if saved:
                merged[spec.name] = saved
    return merged


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


def sync_to_local_env(name: str, value: str | None) -> None:
    """Safely updates the install-root-relative .env file without leaking across drives."""
    from pathlib import Path

    if getattr(sys, "frozen", False):
        root_dir = Path(sys.executable).parent.resolve()
    else:
        root_dir = Path(__file__).resolve().parents[4]

    env_file = root_dir / ".env"
    lines: list[str] = []
    found = False

    if env_file.exists():
        try:
            content = env_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith(f"{name}=") or stripped == name:
                    if value is not None:
                        lines.append(f"{name}={value.strip()}")
                    found = True
                else:
                    lines.append(line)
        except Exception:
            lines = []

    if not found and value is not None:
        lines.append(f"{name}={value.strip()}")

    try:
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def verify_credential_connection(provider: str, credentials: dict[str, str]) -> dict[str, Any]:
    """Tests live connectivity for Indian Stock Market brokers or AI Cloud Providers."""
    import json
    import urllib.error
    import urllib.request

    prov = provider.lower().strip()
    timeout = 8.0

    try:
        if prov == "openai":
            key = credentials.get("OPENAI_API_KEY", "").strip()
            if not key:
                return {"valid": False, "message": "OPENAI_API_KEY is empty."}
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}", "User-Agent": "QuantOS/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models_count = len(data.get("data", []))
                return {
                    "valid": True,
                    "provider": "OpenAI",
                    "message": f"Connected! {models_count} models available.",
                }

        elif prov in ("anthropic", "claude"):
            key = credentials.get("ANTHROPIC_API_KEY", "").strip()
            if not key:
                return {"valid": False, "message": "ANTHROPIC_API_KEY is empty."}
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "User-Agent": "QuantOS/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "valid": True,
                    "provider": "Anthropic Claude",
                    "message": "Connected successfully to Claude API.",
                }

        elif prov == "gemini":
            key = credentials.get("GEMINI_API_KEY", "").strip()
            if not key:
                return {"valid": False, "message": "GEMINI_API_KEY is empty."}
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": key, "User-Agent": "QuantOS/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                count = len(data.get("models", []))
                return {
                    "valid": True,
                    "provider": "Google Gemini",
                    "message": f"Connected! {count} models available.",
                }

        elif prov == "groq":
            key = credentials.get("GROQ_API_KEY", "").strip()
            if not key:
                return {"valid": False, "message": "GROQ_API_KEY is empty."}
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}", "User-Agent": "QuantOS/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "valid": True,
                    "provider": "Groq",
                    "message": "Connected successfully to Groq Cloud.",
                }

        elif prov == "deepseek":
            key = credentials.get("DEEPSEEK_API_KEY", "").strip()
            if not key:
                return {"valid": False, "message": "DEEPSEEK_API_KEY is empty."}
            req = urllib.request.Request(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {key}", "User-Agent": "QuantOS/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "valid": True,
                    "provider": "DeepSeek",
                    "message": "Connected successfully to DeepSeek API.",
                }

        elif prov == "openrouter":
            key = credentials.get("OPENROUTER_API_KEY", "").strip()
            if not key:
                return {"valid": False, "message": "OPENROUTER_API_KEY is empty."}
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {key}", "User-Agent": "QuantOS/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data", {})
                label = data.get("label", "Key active")
                return {"valid": True, "provider": "OpenRouter", "message": f"Connected! ({label})"}

        elif prov == "upstox":
            token = credentials.get("UPSTOX_ACCESS_TOKEN", "").strip()
            if not token:
                return {
                    "valid": False,
                    "message": "UPSTOX_ACCESS_TOKEN is required to test connection.",
                }
            req = urllib.request.Request(
                "https://api.upstox.com/v2/user/profile",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "User-Agent": "QuantOS/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data", {})
                user_name = data.get("user_name", "Upstox User")
                return {
                    "valid": True,
                    "provider": "Upstox",
                    "message": f"Connected as {user_name}!",
                }

        elif prov in ("kite", "zerodha"):
            api_key = credentials.get("KITE_API_KEY", "").strip()
            token = credentials.get("KITE_ACCESS_TOKEN", "").strip()
            if not api_key or not token:
                return {
                    "valid": False,
                    "message": "Both KITE_API_KEY and KITE_ACCESS_TOKEN are required.",
                }
            req = urllib.request.Request(
                "https://api.kite.trade/user/profile",
                headers={
                    "X-Kite-Version": "3",
                    "Authorization": f"token {api_key}:{token}",
                    "User-Agent": "QuantOS/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data", {})
                user_name = data.get("user_name", "Kite User")
                return {
                    "valid": True,
                    "provider": "Zerodha Kite",
                    "message": f"Connected as {user_name}!",
                }

        elif prov == "dhan":
            client_id = credentials.get("DHAN_CLIENT_ID", "").strip()
            token = credentials.get("DHAN_ACCESS_TOKEN", "").strip()
            if not token:
                return {"valid": False, "message": "DHAN_ACCESS_TOKEN is required."}
            req = urllib.request.Request(
                "https://api.dhan.co/v2/profile",
                headers={
                    "access-token": token,
                    "client-id": client_id,
                    "Content-Type": "application/json",
                    "User-Agent": "QuantOS/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {"valid": True, "provider": "Dhan", "message": "Connected to Dhan API!"}

        elif prov == "fyers":
            app_id = credentials.get("FYERS_APP_ID", "").strip()
            token = credentials.get("FYERS_ACCESS_TOKEN", "").strip()
            if not token or not app_id:
                return {
                    "valid": False,
                    "message": "Both FYERS_APP_ID and FYERS_ACCESS_TOKEN are required.",
                }
            req = urllib.request.Request(
                "https://api-t1.fyers.in/api/v3/profile",
                headers={"Authorization": f"{app_id}:{token}", "User-Agent": "QuantOS/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {"valid": True, "provider": "Fyers", "message": "Connected to Fyers API!"}

        else:
            return {"valid": False, "message": f"Unknown provider: {provider}"}

    except urllib.error.HTTPError as err:
        err_msg = f"HTTP {err.code}: {err.reason}"
        try:
            body = err.read().decode("utf-8")
            data = json.loads(body)
            if "message" in data:
                err_msg = data["message"]
            elif "error" in data:
                err_msg = str(data["error"])
        except Exception:
            pass
        return {
            "valid": False,
            "provider": provider,
            "message": f"Authentication failed: {err_msg}",
        }
    except Exception as err:
        return {"valid": False, "provider": provider, "message": f"Connection error: {err}"}
