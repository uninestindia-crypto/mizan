"""QuantOS 2.0: retail API (``/api/v2``) and the React app served at ``/``."""

from __future__ import annotations

from fastapi import FastAPI

from quant_system.server.v2.router import register_api
from quant_system.server.v2.spa import register_spa


def register_v2(app: FastAPI) -> None:
    register_api(app)
    register_spa(app)


__all__ = ["register_v2"]
