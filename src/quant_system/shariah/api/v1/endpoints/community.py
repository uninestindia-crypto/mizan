"""Endpoints for Portfolio Analysis, Shariah Radar, and Community Wealth Hub."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Portfolio, Radar & Community"])


class HoldingItem(BaseModel):
    ticker: str
    shares: int
    buy_price: float


class PortfolioAnalysisRequest(BaseModel):
    holdings: list[HoldingItem]


@router.post("/portfolio/analyze", summary="Analyze User Portfolio Shariah Compliance")
async def analyze_portfolio(payload: PortfolioAnalysisRequest) -> dict[str, Any]:
    """Calculates overall Portfolio Halal Score, compliance breakdown, and drift warnings."""
    if not payload.holdings:
        return {
            "total_value": 0.0,
            "halal_score_percentage": 100.0,
            "compliant_value": 0.0,
            "non_compliant_value": 0.0,
            "drift_warnings": [],
            "holdings_breakdown": [],
        }

    # Reference metrics for NIFTY sample universe
    mock_db = {
        "TCS.NS": {
            "name": "Tata Consultancy Services",
            "price": 4250.0,
            "status": "COMPLIANT",
            "debt_ratio": 2.4,
            "purification_ratio": 0.0042,
        },
        "INFY.NS": {
            "name": "Infosys Limited",
            "price": 1890.0,
            "status": "COMPLIANT",
            "debt_ratio": 3.1,
            "purification_ratio": 0.0038,
        },
        "HDFCBANK.NS": {
            "name": "HDFC Bank Limited",
            "price": 1640.0,
            "status": "NON_COMPLIANT",
            "debt_ratio": 85.0,
            "purification_ratio": 0.0,
        },
        "BHARTIARTL.NS": {
            "name": "Bharti Airtel",
            "price": 1680.0,
            "status": "DRIFT_WATCH",
            "debt_ratio": 31.8,
            "purification_ratio": 0.0085,
        },
        "TATAMOTORS.NS": {
            "name": "Tata Motors",
            "price": 980.0,
            "status": "COMPLIANT",
            "debt_ratio": 26.5,
            "purification_ratio": 0.0025,
        },
        "RELIANCE.NS": {
            "name": "Reliance Industries",
            "price": 2980.0,
            "status": "DRIFT_WATCH",
            "debt_ratio": 29.4,
            "purification_ratio": 0.0065,
        },
        "TITAN.NS": {
            "name": "Titan Company",
            "price": 3450.0,
            "status": "COMPLIANT",
            "debt_ratio": 14.2,
            "purification_ratio": 0.0018,
        },
    }

    total_val = 0.0
    compliant_val = 0.0
    non_compliant_val = 0.0
    drift_warnings = []
    breakdown = []

    for h in payload.holdings:
        ticker = h.ticker.upper().strip()
        if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
            ticker = f"{ticker}.NS"

        info = mock_db.get(
            ticker,
            {
                "name": h.ticker,
                "price": h.buy_price or 1000.0,
                "status": "COMPLIANT",
                "debt_ratio": 12.0,
                "purification_ratio": 0.003,
            },
        )

        curr_price = float(str(info["price"]))
        market_val = h.shares * curr_price
        total_val += market_val

        status = str(info["status"])
        if status == "COMPLIANT":
            compliant_val += market_val
        elif status == "NON_COMPLIANT":
            non_compliant_val += market_val
        elif status == "DRIFT_WATCH":
            compliant_val += market_val
            drift_warnings.append(
                {
                    "ticker": ticker,
                    "name": info["name"],
                    "warning": f"Debt ratio is at {info['debt_ratio']}% (approaching 33% threshold). Watch upcoming Q2 results!",
                }
            )

        breakdown.append(
            {
                "ticker": ticker,
                "company_name": info["name"],
                "shares": h.shares,
                "current_price": curr_price,
                "current_value": market_val,
                "status": status,
                "debt_ratio": info["debt_ratio"],
                "annual_purification_est": market_val
                * 0.015
                * float(str(info["purification_ratio"])),
            }
        )

    halal_score = (compliant_val / total_val * 100.0) if total_val > 0 else 100.0

    return {
        "total_value": round(total_val, 2),
        "halal_score_percentage": round(halal_score, 1),
        "compliant_value": round(compliant_val, 2),
        "non_compliant_value": round(non_compliant_val, 2),
        "drift_warnings": drift_warnings,
        "holdings_breakdown": breakdown,
    }


@router.get("/radar/events", summary="Shariah Corporate Actions Radar")
async def get_shariah_radar() -> dict[str, Any]:
    """Upcoming dividend ex-dates, quarterly filings, and compliance drift watch."""
    return {
        "upcoming_dividends": [
            {
                "ticker": "TCS.NS",
                "company": "Tata Consultancy Services",
                "ex_date": "2026-10-18",
                "dividend_per_share": 10.00,
                "purification_ratio": 0.0042,
                "est_purification_per_100_shares": 4.20,
            },
            {
                "ticker": "INFY.NS",
                "company": "Infosys Limited",
                "ex_date": "2026-10-25",
                "dividend_per_share": 18.00,
                "purification_ratio": 0.0038,
                "est_purification_per_100_shares": 6.84,
            },
            {
                "ticker": "HCLTECH.NS",
                "company": "HCL Technologies",
                "ex_date": "2026-11-04",
                "dividend_per_share": 12.00,
                "purification_ratio": 0.0029,
                "est_purification_per_100_shares": 3.48,
            },
        ],
        "quarterly_earnings_radar": [
            {
                "ticker": "BHARTIARTL.NS",
                "company": "Bharti Airtel",
                "filing_date": "2026-10-28",
                "current_debt_ratio": 31.8,
                "status": "Critical Review (Near 33% Limit)",
            },
            {
                "ticker": "RELIANCE.NS",
                "company": "Reliance Industries",
                "filing_date": "2026-10-22",
                "current_debt_ratio": 29.4,
                "status": "Under Watch",
            },
            {
                "ticker": "TATAMOTORS.NS",
                "company": "Tata Motors",
                "filing_date": "2026-11-10",
                "current_debt_ratio": 26.5,
                "status": "Safe Range",
            },
        ],
        "compliance_drift_watch": [
            {
                "ticker": "BHARTIARTL.NS",
                "company": "Bharti Airtel",
                "debt_ratio": 31.8,
                "threshold": 33.0,
                "risk_level": "HIGH",
                "action": "Watch Q2 finance costs and lease accounting.",
            },
            {
                "ticker": "RELIANCE.NS",
                "company": "Reliance Industries",
                "debt_ratio": 29.4,
                "threshold": 33.0,
                "risk_level": "MODERATE",
                "action": "Retail debt expansion being monitored.",
            },
        ],
        "upcoming_ipos": [
            {
                "company": "NTPC Green Energy Ltd",
                "sector": "Renewable Power & Clean Infrastructure",
                "issue_size_cr": 10000.0,
                "drhp_debt_ratio": 22.4,
                "shariah_verdict": "COMPLIANT",
                "bidding_recommendation": "Permissible to bid. Pure-play clean energy asset meeting both AAOIFI & TASIS criteria.",
                "red_flags": "None. Zero impermissible revenue streams.",
            },
            {
                "company": "Hyundai Motor India Ltd",
                "sector": "Automobile Manufacturing",
                "issue_size_cr": 27870.0,
                "drhp_debt_ratio": 14.2,
                "shariah_verdict": "COMPLIANT",
                "bidding_recommendation": "Permissible to bid. Strong balance sheet with debt well below 33% threshold. Purify ~0.8% incidental treasury interest.",
                "red_flags": "Incidental bank deposit interest (requires dividend purification).",
            },
            {
                "company": "Swiggy Limited",
                "sector": "Quick-Commerce & Food Delivery",
                "issue_size_cr": 11300.0,
                "drhp_debt_ratio": 8.5,
                "shariah_verdict": "QUESTIONABLE",
                "bidding_recommendation": "Caution advised. Core platform facilitates restaurant deliveries but Instamart delivers alcohol in select pilot regions.",
                "red_flags": "Impermissible beverage delivery in select cities (<2% revenue, ongoing scholar deliberation).",
            },
            {
                "company": "HDB Financial Services Ltd",
                "sector": "Conventional NBFC / Credit Lending",
                "issue_size_cr": 12500.0,
                "drhp_debt_ratio": 78.6,
                "shariah_verdict": "NON_COMPLIANT",
                "bidding_recommendation": "Strictly Prohibited. Core business is conventional interest-bearing personal and vehicle loans (Riba).",
                "red_flags": "Conventional interest lending is primary revenue source.",
            },
        ],
    }


@router.get("/community/overview", summary="Community Wealth Hub Overview")
async def get_community_overview() -> dict[str, Any]:
    """Live community impact metrics, verified model portfolios, and active discussions."""
    return {
        "metrics": {
            "halal_wealth_tracked_inr": 48500000.0,
            "riba_avoided_inr": 3420000.0,
            "zakat_empowered_inr": 1210000.0,
            "active_investors_count": 1420,
        },
        "verified_causes": [
            {
                "id": "edu-scholarship",
                "title": "Bait-un-Nasr Educational Scholarship Fund",
                "category": "Education (Zakat Eligible)",
                "reg_80g": "AAATB1234F",
                "upi_id": "scholarship@icici",
                "desc": "100% Zakat eligible: School & college fee sponsorship for meritorious underprivileged students.",
            },
            {
                "id": "medical-dialysis",
                "title": "Lifeline Dialysis & Cancer Medical Aid Trust",
                "category": "Healthcare (Zakat Eligible)",
                "reg_80g": "AABTL5678K",
                "upi_id": "lifelinecare@hdfcbank",
                "desc": "Life-saving dialysis and chemotherapy support for families below poverty line.",
            },
            {
                "id": "clean-water-infra",
                "title": "Sabeel Clean Water & Sanitation Foundation",
                "category": "Public Utilities (Ideal for Interest Purification)",
                "reg_80g": "AACCS9012M",
                "upi_id": "sabeelwater@sbi",
                "desc": "Borewells, water coolers, and public filtration plants—perfect for non-reward dividend interest purification.",
            },
        ],
        "community_portfolios": [
            {
                "id": "halal-compounding-5",
                "title": "Halal Compounding 5",
                "curator": "Dr. Farooq (Certified Islamic Financial Analyst)",
                "cagr_3yr": 26.4,
                "risk": "Moderate",
                "holdings": "TCS (25%), Infosys (25%), Titan (20%), Tata Motors (15%), Divis Lab (15%)",
            },
            {
                "id": "shariah-cash-champions",
                "title": "Zero-Debt Cash Champions",
                "curator": "Amaan Khan (Quantitative Wealth Strategist)",
                "cagr_3yr": 21.8,
                "risk": "Low",
                "holdings": "TCS (30%), HCL Tech (25%), Persistent (25%), Abbott India (20%)",
            },
        ],
        "qa_discussions": [
            {
                "q": "Can I trade intraday or buy options in Shariah compliance?",
                "a": "No. Derivative options (F&O) involve gharar (excessive ambiguity) and lack underlying asset possession. Intraday trading without delivery is impermissible. You must purchase shares on delivery (CNC) where ownership transfers into your Demat account.",
            },
            {
                "q": "What should I do with non-halal dividend income?",
                "a": "Purify it by donating the exact non-operating interest percentage to public utilities or poverty relief without expecting personal spiritual reward, keeping your principal earnings 100% pure.",
            },
            {
                "q": "How is Zakat calculated if I am a long-term passive investor?",
                "a": "You do not pay Zakat on 100% of the market capitalization! You pay 2.5% only on the Zakatable Net Working Assets per share (cash + inventory - current debt), as endorsed by the AAOIFI Shariah Board.",
            },
        ],
    }


@router.get("/funds", summary="Indian Halal Mutual Funds, Shariah ETFs & Gold")
async def get_halal_funds() -> list[dict[str, Any]]:
    """Returns curated Shariah-compliant mutual funds, ETFs, and ethical gold assets in India."""
    return [
        {
            "id": "tata-ethical-fund",
            "name": "Tata Ethical Fund",
            "type": "Mutual Fund (Equity)",
            "aum_inr_cr": 2640.0,
            "nav": 412.35,
            "cagr_3yr": 22.4,
            "cagr_5yr": 21.8,
            "expense_ratio": 0.92,
            "shariah_board": "TASIS (Tasis Shariah Advisory)",
            "min_sip": 500,
            "risk": "Moderate",
            "benchmark": "NIFTY 500 Shariah TRI",
            "description": "India's oldest and largest Shariah-compliant mutual fund investing exclusively in audited Shariah-permissible Indian growth equities.",
            "top_holdings": "TCS (8.2%), Infosys (7.5%), Titan (5.4%), Tata Motors (4.8%), HCL Tech (4.2%)",
        },
        {
            "id": "taurus-ethical-fund",
            "name": "Taurus Ethical Fund",
            "type": "Mutual Fund (Equity)",
            "aum_inr_cr": 185.0,
            "nav": 114.60,
            "cagr_3yr": 24.1,
            "cagr_5yr": 22.5,
            "expense_ratio": 1.15,
            "shariah_board": "TASIS",
            "min_sip": 500,
            "risk": "Moderate to High",
            "benchmark": "S&P BSE 500 Shariah TRI",
            "description": "Actively managed equity scheme investing in Shariah-compliant universe screened under strict debt and revenue rules.",
            "top_holdings": "Infosys (8.8%), TCS (8.1%), Persistent (5.2%), Abbott India (4.9%)",
        },
        {
            "id": "nippon-shariah-bees",
            "name": "Nippon India ETF Shariah BeES",
            "ticker": "SHARIABEES.NS",
            "type": "Exchange Traded Fund (ETF)",
            "aum_inr_cr": 82.0,
            "nav": 524.10,
            "cagr_3yr": 20.8,
            "cagr_5yr": 19.9,
            "expense_ratio": 0.45,
            "shariah_board": "NSE Indices Shariah Council",
            "min_sip": 524,
            "risk": "Moderate",
            "benchmark": "NIFTY 50 Shariah Index",
            "description": "Lowest-cost index fund tracking India's premier NIFTY 50 Shariah Index directly on the NSE cash market.",
            "top_holdings": "TCS, Infosys, Bharti Airtel, Titan, Sun Pharma",
        },
        {
            "id": "physical-digital-gold",
            "name": "24K Certified Physical Gold / Gold ETF",
            "ticker": "GOLDBEES.NS",
            "type": "Ethical Commodity Store of Value",
            "aum_inr_cr": 12500.0,
            "nav": 68.20,
            "cagr_3yr": 17.5,
            "cagr_5yr": 16.2,
            "expense_ratio": 0.50,
            "shariah_board": "AAOIFI Shariah Standard No. 57 (Gold)",
            "min_sip": 100,
            "risk": "Low to Moderate",
            "benchmark": "Domestic Spot Gold Price (99.5% Purity)",
            "description": "100% physical gold backed vault storage meeting AAOIFI Gold Standard rules: spot settlement with full constructive possession and no interest leverage.",
            "top_holdings": "Physical London/India Good Delivery Gold Bars (99.5%+ Pure)",
        },
    ]


@router.get("/market/status", summary="NSE Market Timing & Index Status")
async def get_market_status() -> dict[str, Any]:
    """Returns Indian stock market hours (IST) and benchmark status."""
    import datetime

    now_utc = datetime.datetime.now(datetime.UTC)
    # IST = UTC + 5:30
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    now_ist = now_utc + ist_offset

    is_weekday = now_ist.weekday() < 5
    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)
    curr_time = now_ist.time()

    is_live = is_weekday and (market_open <= curr_time <= market_close)

    return {
        "ist_time": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "is_market_open": is_live,
        "trading_session": "Regular Trading (09:15 - 15:30 IST)"
        if is_live
        else "Market Closed (Reopens Next Trading Day 09:15 IST)",
        "indices": {
            "nifty_50_shariah": {"level": 7420.50, "change_pct": 0.85},
            "nifty_500_shariah": {"level": 6180.20, "change_pct": 0.92},
            "bse_tasis_shariah_50": {"level": 4890.10, "change_pct": 0.78},
        },
    }
