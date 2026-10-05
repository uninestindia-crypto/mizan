from fastapi import APIRouter
from quant_system.shariah.api.v1.endpoints import (
    health,
    stocks,
    screening,
    baskets,
    purification,
    zakat,
    academy,
    community,
    notifications,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(stocks.router, tags=["Stocks"])
api_router.include_router(screening.router, tags=["Shariah Screening"])
api_router.include_router(baskets.router, tags=["Curated Baskets & Broker Export"])
api_router.include_router(purification.router, tags=["Dividend Purification & Cryptographic Ledger"])
api_router.include_router(zakat.router, tags=["Equity Zakat Calculator"])
api_router.include_router(academy.router, tags=["Halal Wealth Academy & Demat Guides"])
api_router.include_router(community.router, tags=["Portfolio, Radar & Community"])
api_router.include_router(notifications.router, tags=["Notifications & Alerts"])

