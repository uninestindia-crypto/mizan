import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from httpx import ASGITransport, AsyncClient

from quant_system.shariah.main import app
from quant_system.shariah.schemas.academy import (
    AcademyModuleDetail,
    DematGuideResponse,
)
from quant_system.shariah.schemas.basket import BasketDetail, BasketExportResponse, BasketSummary
from quant_system.shariah.schemas.company import CompanyDetail
from quant_system.shariah.schemas.purification import (
    PurificationCalculateResponse,
    PurificationLedgerListResponse,
)
from quant_system.shariah.schemas.screening import ScreeningResponse, ShariahAuditResponse
from quant_system.shariah.schemas.zakat import ZakatCalculateResponse


async def verify_schemas():
    print("================================================================================")
    print("           FASTAPI HTTP 200 & SCHEMA-VALID JSON VERIFICATION                    ")
    print("================================================================================")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Health
        r = await client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        print("[HTTP 200] GET /api/v1/health -> Valid JSON:", data["status"])

        # 2. Stock Lookup (TCS.NS)
        r = await client.get("/api/v1/stocks/TCS.NS")
        assert r.status_code == 200
        stock = CompanyDetail.model_validate(r.json())
        print(
            f"[HTTP 200] GET /api/v1/stocks/TCS.NS -> Schema-Valid CompanyDetail: {stock.profile.ticker} ({stock.profile.company_name})"
        )

        # 3. Stock Screening (TCS.NS)
        r = await client.get("/api/v1/stocks/TCS.NS/screen?standard=both")
        assert r.status_code == 200
        screen = ScreeningResponse.model_validate(r.json())
        print(
            f"[HTTP 200] GET /api/v1/stocks/TCS.NS/screen -> Schema-Valid ScreeningResponse: {screen.overall_status}"
        )

        # 4. Stock Audit (TCS.NS)
        r = await client.get("/api/v1/stocks/TCS.NS/audit")
        assert r.status_code == 200
        audit = ShariahAuditResponse.model_validate(r.json())
        print(
            f"[HTTP 200] GET /api/v1/stocks/TCS.NS/audit -> Schema-Valid ShariahAuditResponse: {len(audit.balance_sheet_lines)} BS lines"
        )

        # 5. Basket Listing
        r = await client.get("/api/v1/baskets")
        assert r.status_code == 200
        baskets = [BasketSummary.model_validate(b) for b in r.json()]
        print(
            f"[HTTP 200] GET /api/v1/baskets -> Schema-Valid List[BasketSummary]: {len(baskets)} baskets found"
        )

        # 6. Single Basket Detail
        r = await client.get(f"/api/v1/baskets/{baskets[0].id}")
        assert r.status_code == 200
        basket_det = BasketDetail.model_validate(r.json())
        print(
            f"[HTTP 200] GET /api/v1/baskets/{baskets[0].id} -> Schema-Valid BasketDetail: {basket_det.name}"
        )

        # 7. Basket Export
        r = await client.post(
            f"/api/v1/baskets/{baskets[0].id}/export",
            json={"broker": "zerodha", "capital": 100000.0},
        )
        assert r.status_code == 200
        export = BasketExportResponse.model_validate(r.json())
        print(
            f"[HTTP 200] POST /api/v1/baskets/.../export -> Schema-Valid BasketExportResponse: {export.order_count} orders"
        )

        # 8. Purification Calculation
        r = await client.post(
            "/api/v1/purification/calculate",
            json={"ticker": "TCS.NS", "dividend_amount": 10.0, "shares_held": 500},
        )
        assert r.status_code == 200
        pur = PurificationCalculateResponse.model_validate(r.json())
        print(
            f"[HTTP 200] POST /api/v1/purification/calculate -> Schema-Valid PurificationCalculateResponse: payable=INR {pur.purification_payable:.2f}"
        )

        # 9. Purification Ledger
        r = await client.get("/api/v1/purification/ledger")
        assert r.status_code == 200
        ledger = PurificationLedgerListResponse.model_validate(r.json())
        print(
            f"[HTTP 200] GET /api/v1/purification/ledger -> Schema-Valid PurificationLedgerListResponse: chain_valid={ledger.is_chain_valid}"
        )

        # 10. Zakat Calculation (Active)
        r = await client.post(
            "/api/v1/zakat/calculate",
            json={
                "method": "active",
                "holdings": [{"ticker": "TCS.NS", "shares": 100}],
                "cash_balance": 25000.0,
                "calendar": "lunar",
            },
        )
        assert r.status_code == 200
        zak_act = ZakatCalculateResponse.model_validate(r.json())
        print(
            f"[HTTP 200] POST /api/v1/zakat/calculate (Active) -> Schema-Valid ZakatCalculateResponse: due=INR {zak_act.zakat_due:.2f}"
        )

        # 11. Zakat Calculation (Long-Term)
        r = await client.post(
            "/api/v1/zakat/calculate",
            json={
                "method": "long_term",
                "holdings": [{"ticker": "TCS.NS", "shares": 100}],
                "cash_balance": 25000.0,
                "calendar": "lunar",
            },
        )
        assert r.status_code == 200
        zak_lt = ZakatCalculateResponse.model_validate(r.json())
        print(
            f"[HTTP 200] POST /api/v1/zakat/calculate (Long-Term) -> Schema-Valid ZakatCalculateResponse: due=INR {zak_lt.zakat_due:.2f}"
        )

        # 12. Academy Modules
        r = await client.get("/api/v1/academy/modules")
        assert r.status_code == 200
        modules = [AcademyModuleDetail.model_validate(m) for m in r.json()]
        print(
            f"[HTTP 200] GET /api/v1/academy/modules -> Schema-Valid List[AcademyModuleDetail]: {len(modules)} modules"
        )

        # 13. Demat Guide
        r = await client.get("/api/v1/academy/demat-guide")
        assert r.status_code == 200
        dg = DematGuideResponse.model_validate(r.json())
        print(
            f"[HTTP 200] GET /api/v1/academy/demat-guide -> Schema-Valid DematGuideResponse: {len(dg.brokers)} brokers, {len(dg.universal_rules)} universal rules"
        )

    print("================================================================================")
    print("           ALL FASTAPI ENDPOINTS RESPONDED HTTP 200 WITH VALID SCHEMAS          ")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(verify_schemas())
