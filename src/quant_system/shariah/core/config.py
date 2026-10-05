import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


def ensure_shariah_database(target_path: Path) -> None:
    """Ensures target_path is a valid populated Shariah SQLite database."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.is_file() and target_path.stat().st_size > 10000:
        return

    import shutil
    import sys

    # Candidates for pre-bundled seed database
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "_internal" / "data" / "shariah" / "halal_stocks.db")
        candidates.append(exe_dir / "data" / "shariah" / "halal_stocks.db")
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "data" / "shariah" / "halal_stocks.db")

    # Relative to this file's repository root
    repo_root = Path(__file__).resolve().parents[4]
    candidates.append(repo_root / "data" / "shariah" / "halal_stocks.db")
    candidates.append(repo_root / "_internal" / "data" / "shariah" / "halal_stocks.db")

    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 10000:
            try:
                shutil.copy2(candidate, target_path)
                return
            except Exception:
                pass

    # Fallback: initialize database schema if no seed file could be copied
    try:
        from quant_system.shariah.db.init_db import init_db

        init_db(str(target_path))
    except Exception:
        pass


class Settings(BaseModel):
    PROJECT_NAME: str = "Halal Investment & Wealth-Building Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Base directories
    @property
    def DATA_DIR(self) -> Path:
        app_root = os.environ.get("QUANTOS_APP_ROOT")
        if app_root:
            root = Path(app_root)
        else:
            root = Path(__file__).resolve().parents[4]
        d = root / "data" / "shariah"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # SQLite configuration
    SQLITE_DB_FILE: str = "halal_stocks.db"

    @property
    def SQLITE_DB_PATH(self) -> Path:
        path = self.DATA_DIR / self.SQLITE_DB_FILE
        ensure_shariah_database(path)
        return path

    # DuckDB configuration
    DUCKDB_FILE: str = "analytics.duckdb"

    @property
    def DUCKDB_PATH(self) -> Path:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return self.DATA_DIR / self.DUCKDB_FILE

    # CORS Origins (Allow Flutter Web, Desktop, Mobile, and local testing)
    CORS_ORIGINS: list[str] | str = [
        "*",
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v  # type: ignore
        raise ValueError(v)

    # Shariah Quantitative Thresholds (Strict inequalities: < 33%, < 5%)
    MAX_DEBT_RATIO: float = 0.33
    MAX_CASH_RATIO: float = 0.33
    MAX_RECEIVABLES_RATIO: float = 0.33
    MAX_IMPERMISSIBLE_REVENUE_RATIO: float = 0.05

    # Warning Thresholds (For Questionable / Mushbooh classification)
    WARN_DEBT_RATIO: float = 0.32
    WARN_CASH_RATIO: float = 0.32
    WARN_RECEIVABLES_RATIO: float = 0.32
    WARN_IMPERMISSIBLE_REVENUE_RATIO: float = 0.045

    # Indian Silver Nisab Default (595 grams * ~90 INR/g)
    DEFAULT_SILVER_NISAB_INR: float = 53550.0

    model_config = ConfigDict(
        extra="allow",
    )


settings = Settings()
