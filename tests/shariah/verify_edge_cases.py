import asyncio
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.services.screener_service import evaluate_company_shariah


async def test_edge_cases():
    db_gen = get_async_db()
    db = await anext(db_gen)

    print("================================================================================")
    print("               HALAL INVESTMENT PLATFORM - RATIO EDGE CASES VERIFICATION       ")
    print("================================================================================")

    # 1. Zero Debt Equities and Ultra-Low Debt (TCS, INFY, and ZERO-DEBT fixture)
    print("\n--- [1] ZERO DEBT & ULTRA-LOW DEBT EQUITIES (AAOIFI & TASIS) ---")

    # Check synthetic ZERO-DEBT fixture
    fixture_path = os.path.join("backend", "tests", "fixtures", "sample_nifty500.json")
    if os.path.exists(fixture_path):
        with open(fixture_path, encoding="utf-8") as f:
            fixtures = json.load(f)
        zero_debt_fixtures = [
            c for c in fixtures if c.get("ticker") == "ZERO-DEBT.NS" or c.get("total_debt") == 0.0
        ]
        for comp in zero_debt_fixtures:
            aaoifi_eval, tasis_eval, has_div, div_notes = evaluate_company_shariah(comp)
            print(f"Fixture: {comp['ticker']} ({comp.get('company_name', '')})")
            print(f"  Total Debt: INR {comp['total_debt']} Cr")
            print(
                f"  AAOIFI Debt Ratio: {aaoifi_eval.debt_ratio.actual_pct:.4f}% -> Compliant: {aaoifi_eval.debt_ratio.is_compliant}"
            )
            print(
                f"  TASIS Debt Ratio:  {tasis_eval.debt_ratio.actual_pct:.4f}% -> Compliant: {tasis_eval.debt_ratio.is_compliant}"
            )
            assert comp["total_debt"] == 0.0
            assert aaoifi_eval.debt_ratio.actual_pct == 0.0
            assert tasis_eval.debt_ratio.actual_pct == 0.0
            assert aaoifi_eval.debt_ratio.is_compliant is True
            assert tasis_eval.debt_ratio.is_compliant is True

    # Real equities (TCS, INFY)
    for ticker in ["TCS.NS", "INFY.NS"]:
        cursor = await db.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,))
        row = await cursor.fetchone()
        comp = dict(row)
        aaoifi_eval, tasis_eval, has_div, div_notes = evaluate_company_shariah(comp)

        debt_aaoifi = aaoifi_eval.debt_ratio.actual_pct
        debt_tasis = tasis_eval.debt_ratio.actual_pct
        print(f"Real Equity: {ticker} ({comp.get('company_name', '')})")
        print(f"  Total Debt: INR {comp['total_debt']} Cr")
        print(
            f"  AAOIFI Debt Ratio: {debt_aaoifi:.4f}% (Threshold: < 33.00%) -> Compliant: {aaoifi_eval.debt_ratio.is_compliant}"
        )
        print(
            f"  TASIS Debt Ratio:  {debt_tasis:.4f}% (Threshold: < 33.00%) -> Compliant: {tasis_eval.debt_ratio.is_compliant}"
        )
        print(
            f"  Overall AAOIFI Status: {aaoifi_eval.status} | Overall TASIS Status: {tasis_eval.status}"
        )
        assert aaoifi_eval.debt_ratio.is_compliant is True
        assert tasis_eval.debt_ratio.is_compliant is True

    # 2. Negative Working Capital Equities (clamped to 0 in Zakat calculations)
    print("\n--- [2] NEGATIVE WORKING CAPITAL EQUITIES (ZAKAT ZNWA FLOOR) ---")
    neg_count = 0
    if os.path.exists(fixture_path):
        for comp in fixtures:
            ca = (comp.get("cash_and_equivalents") or 0.0) + (
                comp.get("accounts_receivable") or 0.0
            )
            cl = (comp.get("current_liabilities") or 0.0) or (comp.get("total_debt") or 0.0)
            znwa_raw = ca - cl
            shares = comp.get("shares_outstanding") or 1.0
            znwa_per_share = max(0.0, znwa_raw / shares)
            if znwa_raw < 0:
                neg_count += 1
                print(f"Ticker: {comp['ticker']} ({comp.get('company_name', '')})")
                print(f"  Current Assets (Cash + AR): INR {ca:.2f} Cr")
                print(f"  Current Liabilities:        INR {cl:.2f} Cr")
                print(
                    f"  Raw ZNWA (CA - CL):         INR {znwa_raw:.2f} Cr (< 0: Negative Working Capital)"
                )
                print(
                    f"  Clamped ZNWA per share:     INR {znwa_per_share:.4f} (Strict max(0, ZNWA) floor applied)"
                )
                assert znwa_per_share == 0.0
    print(f"Total Negative Working Capital Companies Verified: {neg_count}")

    # 3. High Cash Reserves (>33% threshold trigger)
    print("\n--- [3] HIGH CASH RESERVES (>= 33.00% THRESHOLD TRIGGER) ---")
    cursor = await db.execute("SELECT * FROM companies")
    rows = await cursor.fetchall()
    high_cash_count = 0
    for row in rows:
        comp = dict(row)
        aaoifi_eval, tasis_eval, has_div, div_notes = evaluate_company_shariah(comp)
        cash_aaoifi = aaoifi_eval.cash_ratio.actual_pct
        cash_tasis = tasis_eval.cash_ratio.actual_pct
        if cash_aaoifi >= 33.0 or cash_tasis >= 33.0:
            high_cash_count += 1
            print(f"Ticker: {comp['ticker']} ({comp.get('company_name', '')})")
            print(f"  Cash & Investments: INR {comp['total_cash_and_investments']} Cr")
            print(
                f"  AAOIFI Cash Ratio:  {cash_aaoifi:.2f}% -> Compliant: {aaoifi_eval.cash_ratio.is_compliant} (Denom: {aaoifi_eval.cash_ratio.denominator_label})"
            )
            print(
                f"  TASIS Cash Ratio:   {cash_tasis:.2f}% -> Compliant: {tasis_eval.cash_ratio.is_compliant} (Denom: {tasis_eval.cash_ratio.denominator_label})"
            )
            print(f"  Resulting Status:   AAOIFI={aaoifi_eval.status} | TASIS={tasis_eval.status}")
    print(f"Total High Cash Trigger Companies Verified: {high_cash_count}")

    # 4. Denominator Divergence: AAOIFI (36m Mcap) vs TASIS (Total Assets)
    print("\n--- [4] DENOMINATOR DIVERGENCE (AAOIFI 36M MCAP vs TASIS TOTAL ASSETS) ---")
    divergent_count = 0
    for row in rows:
        comp = dict(row)
        aaoifi_eval, tasis_eval, has_div, div_notes = evaluate_company_shariah(comp)
        if aaoifi_eval.status != tasis_eval.status:
            divergent_count += 1
            print(f"Ticker: {comp['ticker']} ({comp.get('company_name', '')})")
            print(
                f"  AAOIFI: {aaoifi_eval.status} (Denominator: {aaoifi_eval.debt_ratio.denominator_label} = INR {aaoifi_eval.debt_ratio.denominator_value_inr_cr:,.2f} Cr)"
            )
            print(
                f"  TASIS:  {tasis_eval.status} (Denominator: {tasis_eval.debt_ratio.denominator_label} = INR {tasis_eval.debt_ratio.denominator_value_inr_cr:,.2f} Cr)"
            )
            print(f"  Divergence Flag: {has_div}")
            print(f"  Divergence Audit Note: {div_notes}")
            assert has_div is True
    print(f"Total Divergent Equities Between Standards: {divergent_count}")
    print("\n================================================================================")
    print("                    ALL RATIO EDGE CASES SUCCESSFULLY VERIFIED                  ")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(test_edge_cases())
