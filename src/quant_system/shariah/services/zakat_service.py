"""Service implementing the Dual-Method Equity Zakat Engine (R6)."""

from typing import Any

import aiosqlite

from quant_system.shariah.core.config import settings
from quant_system.shariah.schemas.zakat import (
    ZakatCalculateRequest,
    ZakatCalculateResponse,
    ZakatHoldingBreakdown,
)

# Authoritative Zakat Constants (DomainOracle calibration)
SILVER_NISAB_DEFAULT = 53550.0  # 595 grams * 90 INR/g
LUNAR_RATE = 0.025000  # 2.500%
SOLAR_RATE = 0.025770  # 2.577% (2.5% * 365.25 / 354)

_ZAKAT_METRICS_CACHE: dict[str, dict[str, Any] | None] = {}


async def lookup_company_zakat_metrics(
    ticker: str,
    db: aiosqlite.Connection,
) -> dict[str, Any] | None:
    """Look up zakatable assets per share and current price from database."""
    clean_ticker = ticker.strip().upper()
    if clean_ticker in _ZAKAT_METRICS_CACHE:
        return _ZAKAT_METRICS_CACHE[clean_ticker]

    variants = [clean_ticker]
    if clean_ticker.endswith(".NS") or clean_ticker.endswith(".BO"):
        variants.append(clean_ticker[:-3])
    else:
        variants.append(f"{clean_ticker}.NS")
        variants.append(f"{clean_ticker}.BO")

    placeholders = ",".join("?" for _ in variants)
    sql = f"""
        SELECT ticker, symbol, company_name, current_price, zakatable_assets_per_share
        FROM companies
        WHERE ticker IN ({placeholders}) OR symbol IN ({placeholders})
        LIMIT 1;
    """
    cursor = await db.execute(sql, tuple(variants + variants))
    row = await cursor.fetchone()
    if row:
        result = {
            "ticker": row["ticker"],
            "symbol": row["symbol"],
            "company_name": row["company_name"],
            "current_price": float(row["current_price"]),
            "zakatable_assets_per_share": float(row["zakatable_assets_per_share"]),
        }
    else:
        result = None

    _ZAKAT_METRICS_CACHE[clean_ticker] = result
    return result


async def calculate_equity_zakat(
    request: ZakatCalculateRequest,
    db: aiosqlite.Connection,
) -> ZakatCalculateResponse:
    """
    Calculates Equity Zakat using either Active Trader (100% NLV) or
    Long-Term Investor (Zakatable Net Working Assets per share) method.
    """
    method = request.method.lower().strip()
    calendar = request.calendar.lower().strip()
    rate = SOLAR_RATE if calendar == "solar" else LUNAR_RATE
    rate_pct = round(rate * 100.0, 4)
    nisab_threshold = (
        request.custom_nisab_inr or settings.DEFAULT_SILVER_NISAB_INR or SILVER_NISAB_DEFAULT
    )

    breakdown: list[ZakatHoldingBreakdown] = []
    portfolio_value = float(request.portfolio_value or 0.0)
    cash_balance = round(float(request.cash_balance or 0.0), 2)

    computed_portfolio_value = 0.0
    holdings_zakatable_base = 0.0

    if request.holdings:
        for item in request.holdings:
            info = await lookup_company_zakat_metrics(item.ticker, db)
            price = (
                item.current_price
                if item.current_price is not None
                else (info["current_price"] if info else 0.0)
            )
            comp_name = info["company_name"] if info else item.ticker
            symbol = info["symbol"] if info else item.ticker.replace(".NS", "").replace(".BO", "")

            # Market value for this holding
            holding_mkt_val = round(price * item.shares, 2)
            computed_portfolio_value += holding_mkt_val

            if method == "active":
                # Active trader: 100% of market value is zakatable
                item_zakatable = holding_mkt_val
                znwa_reported = (
                    item.znwa_per_share
                    if item.znwa_per_share is not None
                    else (info["zakatable_assets_per_share"] if info else 0.0)
                )
                method_applied = "Active Trader (100% Market Value)"
            else:
                # Long-Term investor: Zakatable Net Working Assets per share
                if item.znwa_per_share is not None:
                    znwa_reported = max(0.0, float(item.znwa_per_share))
                elif info is not None:
                    znwa_reported = max(0.0, float(info["zakatable_assets_per_share"]))
                else:
                    # Conservative 25% proxy of current market price
                    znwa_reported = round(price * 0.25, 2)

                item_zakatable = round(znwa_reported * item.shares, 2)
                method_applied = "Long-Term (Zakatable Net Working Assets)"

            holdings_zakatable_base += item_zakatable

            breakdown.append(
                ZakatHoldingBreakdown(
                    ticker=item.ticker,
                    symbol=symbol,
                    company_name=comp_name,
                    shares=item.shares,
                    current_price=price,
                    market_value=holding_mkt_val,
                    znwa_per_share=znwa_reported,
                    zakatable_amount=item_zakatable,
                    method_applied=method_applied,
                )
            )

    # Determine final zakatable base
    if method == "active":
        # If aggregate portfolio_value was supplied and positive, prefer it; otherwise use computed
        effective_portfolio_val = (
            portfolio_value if portfolio_value > 0.0 else computed_portfolio_value
        )
        zakatable_base = round(effective_portfolio_val + cash_balance, 2)
        final_portfolio_val = effective_portfolio_val
        method_notes = (
            "Active Trader Method ('Urud al-Tijarah): 100% of portfolio liquidation value "
            "plus uninvested cash is subject to Zakat as trade merchandise."
        )
    else:
        # Long-Term investor
        if request.holdings:
            final_portfolio_val = (
                portfolio_value if portfolio_value > 0.0 else computed_portfolio_value
            )
            zakatable_base = round(holdings_zakatable_base + cash_balance, 2)
        else:
            # Fallback if only aggregate portfolio_value was supplied for long-term method
            final_portfolio_val = portfolio_value
            proxy_zakatable = round(portfolio_value * 0.25, 2) if portfolio_value > 0.0 else 0.0
            zakatable_base = round(proxy_zakatable + cash_balance, 2)

        method_notes = (
            "Long-Term Investor Method (Mustathmir): Zakat is levied only on circulating "
            "Net Working Assets (Cash, Receivables, Inventory less Current Liabilities). "
            "Fixed assets, machinery, and factory buildings are 100% exempt."
        )

    # Evaluate Nisab & Obligation
    is_obligatory = zakatable_base >= nisab_threshold
    if is_obligatory:
        zakat_due = round(zakatable_base * rate, 2)
        exemption_reason = None
    else:
        zakat_due = 0.0
        exemption_reason = (
            f"Zakatable base (₹{zakatable_base:,.2f}) is below the Indian Silver Nisab threshold "
            f"(₹{nisab_threshold:,.2f}); wealth is exempt from Zakat for this lunar cycle."
        )

    return ZakatCalculateResponse(
        method=method,
        calendar=calendar,
        rate=rate,
        rate_pct=rate_pct,
        zakatable_base=zakatable_base,
        portfolio_value=final_portfolio_val,
        cash_balance=cash_balance,
        nisab_threshold=nisab_threshold,
        is_obligatory=is_obligatory,
        zakat_due=zakat_due,
        breakdown=breakdown,
        exemption_reason=exemption_reason,
        method_notes=method_notes,
    )
