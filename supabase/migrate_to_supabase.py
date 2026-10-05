"""Migration script: Sync SQLite database to Supabase PostgreSQL."""

import os
import sqlite3
import httpx
import asyncio

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

async def migrate():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("[!] Error: Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
        print("    Example: $env:SUPABASE_URL='https://xyz.supabase.co'; $env:SUPABASE_SERVICE_ROLE_KEY='eyJ...'")
        return

    db_path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "halal_stocks.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM companies")
    companies = cursor.fetchall()
    print(f"[*] Found {len(companies)} companies in local SQLite database.")

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    records = []
    for c in companies:
        records.append({
            "ticker": c["ticker"],
            "symbol": c["symbol"],
            "isin": c["isin"],
            "bse_code": c["bse_code"],
            "company_name": c["company_name"],
            "sector": c["sector"],
            "industry": c["industry"],
            "business_summary": c["business_summary"],
            "current_price": float(c["current_price"]),
            "market_cap": float(c["market_cap"]),
            "avg_36m_market_cap": float(c["avg_36m_market_cap"]),
            "shares_outstanding": float(c["shares_outstanding"]),
            "total_assets": float(c["total_assets"]),
            "total_debt": float(c["total_debt"]),
            "total_cash_and_investments": float(c["total_cash_and_investments"]),
            "total_receivables": float(c["total_receivables"]),
            "total_revenue": float(c["total_revenue"]),
            "total_impermissible_income": float(c["total_impermissible_income"]),
            "sector_compliant": bool(c["sector_compliant"]),
            "sector_failure_reason": c["sector_failure_reason"],
            "purification_ratio": float(c["purification_ratio"]),
            "zakatable_assets_per_share": float(c["zakatable_assets_per_share"]),
            "is_nifty_50": bool(c["is_nifty_50"]),
            "is_nifty_500": bool(c["is_nifty_500"]),
            "audit_notes": c["audit_notes"],
        })

    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{SUPABASE_URL}/rest/v1/companies"
        res = await client.post(url, headers=headers, json=records)
        if res.status_code in [200, 201]:
            print(f"[✓] Successfully migrated {len(records)} companies to Supabase!")
        else:
            print(f"[✗] Migration failed: {res.status_code} - {res.text}")

if __name__ == "__main__":
    asyncio.run(migrate())
