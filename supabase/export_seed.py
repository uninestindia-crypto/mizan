"""Export SQLite Seed Data into Supabase SQL Inserts."""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "halal_stocks.db")
output_path = os.path.join(os.path.dirname(__file__), "seed_data.sql")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM companies")
companies = cursor.fetchall()

sql_lines = [
    "-- =====================================================================",
    "-- NIFTY 500 PRE-AUDITED SHARIAH FINANCIAL FUNDAMENTALS (SUPABASE SEED)",
    "-- =====================================================================",
    ""
]

for c in companies:
    ticker = c["ticker"].replace("'", "''")
    symbol = c["symbol"].replace("'", "''")
    isin = (c["isin"] or "").replace("'", "''")
    bse = (c["bse_code"] or "").replace("'", "''")
    name = c["company_name"].replace("'", "''")
    sec = c["sector"].replace("'", "''")
    ind = c["industry"].replace("'", "''")
    summary = (c["business_summary"] or "").replace("'", "''")
    sec_fail = (c["sector_failure_reason"] or "").replace("'", "''")
    notes = (c["audit_notes"] or "").replace("'", "''")
    sec_comp = "true" if c["sector_compliant"] else "false"
    n50 = "true" if c["is_nifty_50"] else "false"
    n500 = "true" if c["is_nifty_500"] else "false"
    
    sql = (
        f"INSERT INTO public.companies "
        f"(ticker, symbol, isin, bse_code, company_name, sector, industry, business_summary, "
        f"current_price, market_cap, avg_36m_market_cap, shares_outstanding, total_assets, "
        f"total_debt, total_cash_and_investments, total_receivables, total_revenue, "
        f"total_impermissible_income, sector_compliant, sector_failure_reason, "
        f"purification_ratio, zakatable_assets_per_share, is_nifty_50, is_nifty_500, audit_notes) "
        f"VALUES ('{ticker}', '{symbol}', '{isin}', '{bse}', '{name}', '{sec}', '{ind}', '{summary}', "
        f"{c['current_price']}, {c['market_cap']}, {c['avg_36m_market_cap']}, {c['shares_outstanding']}, "
        f"{c['total_assets']}, {c['total_debt']}, {c['total_cash_and_investments']}, {c['total_receivables']}, "
        f"{c['total_revenue']}, {c['total_impermissible_income']}, {sec_comp}, '{sec_fail}', "
        f"{c['purification_ratio']}, {c['zakatable_assets_per_share']}, {n50}, {n500}, '{notes}') "
        f"ON CONFLICT (ticker) DO NOTHING;"
    )
    sql_lines.append(sql)

# Also seed curated baskets
sql_lines.append("\n-- Baskets Seed Data")
sql_lines.append("""INSERT INTO public.curated_baskets (id, title, description, category, risk_level, cagr_3yr, sharpe_ratio, min_investment) VALUES
('halal-tech-titans', 'Halal Tech Titans', 'Leading zero-debt Indian technology giants driving global IT transformation and enterprise software.', 'Large Cap IT', 'Moderate', 24.80, 1.45, 5000.00),
('shariah-dividend-champions', 'Shariah Dividend Champions', 'High cash-flow, zero-interest blue chips offering consistent dividend payouts and defensive balance sheets.', 'Dividend Yield', 'Low to Moderate', 19.40, 1.32, 5000.00),
('green-ethical-infra', 'Green & Ethical Infrastructure', 'Capital-efficient clean energy, transmission, and environmental leaders screened for ethical operations.', 'Thematic Growth', 'High', 28.60, 1.58, 10000.00),
('nifty-shariah-25-core', 'NIFTY Shariah 25 Core', 'A foundational Shariah-compliant market-weight index basket capturing India''s top halal enterprises.', 'Index Tracker', 'Moderate', 21.20, 1.28, 5000.00)
ON CONFLICT (id) DO NOTHING;""")

# Also seed academy modules
sql_lines.append("\n-- Academy Modules Seed Data")
sql_lines.append("""INSERT INTO public.academy_modules (id, slug, title, summary, read_time_minutes, icon_name, sections) VALUES
(1, 'why-muslims-must-invest', 'Why Muslims Must Invest', 'Discover how capital stewardship and beating inflation is essential for community empowerment and financial independence.', 5, 'trending_up', '[{"title": "The Inflation Trap", "body": "Leaving savings in cash or zero-interest accounts causes purchasing power to erode rapidly over time due to 6-7% inflation in India."}, {"title": "Equity as Musharakah", "body": "Buying shares is becoming an equity partner (Musharakah) in a real productive business, sharing risks and ethical profits."}]'::jsonb),
(2, 'shariah-screening-demystified', 'Shariah Screening Demystified', 'Learn the two-tier Shariah audit: sector business activity exclusions and financial ratio thresholds.', 6, 'verified', '[{"title": "Sector Exclusions", "body": "Companies in alcohol, gambling, pork, conventional interest-bearing banking, and weapons are strictly impermissible."}, {"title": "The 33% Financial Rule", "body": "Scholars establish that interest-bearing debt, interest-earning cash, and receivables must not exceed 33% of the company capitalization."}]'::jsonb),
(3, 'dividend-purification-guide', 'Dividend Purification Guide', 'Understand how to identify, calculate, and purify non-permissible interest income from stock dividends.', 4, 'cleaning_services', '[{"title": "Why Purify?", "body": "Even compliant companies may hold short-term cash in conventional accounts earning incidental interest. That small portion must be given to charity without intention of personal reward."}, {"title": "How to Calculate", "body": "Multiply your gross dividend received by the company non-operating interest ratio."}]'::jsonb),
(4, 'equity-zakat-masterclass', 'Equity Zakat Masterclass', 'Master Zakat calculation on stock portfolios: Active Trader method vs Long-Term Investor method.', 7, 'calculate', '[{"title": "Active Traders", "body": "If buying shares for short-term capital gains (trading inventory), pay 2.5% on 100% of the portfolio net liquidation value above Nisab."}, {"title": "Long-Term Investors", "body": "If holding shares for dividend yield and long-term ownership, pay 2.5% only on the Zakatable Net Working Assets per share, not fixed machinery."}]'::jsonb)
ON CONFLICT (id) DO NOTHING;""")

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(sql_lines) + "\n")

print(f"Generated {output_path} successfully ({len(companies)} company inserts).")
