import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


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
        return self.DATA_DIR / self.SQLITE_DB_FILE

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
