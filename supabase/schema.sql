-- =====================================================================
-- HALAL INVESTMENT & WEALTH-BUILDING PLATFORM — SUPABASE POSTGRES SCHEMA
-- Dual-Standard Shariah Screening (AAOIFI & TASIS) + Portfolios + Ledger
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------
-- 1. COMPANIES & SHARIAH FINANCIAL FUNDAMENTALS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    isin TEXT,
    bse_code TEXT,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    business_summary TEXT,
    current_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    market_cap NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    avg_36m_market_cap NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    shares_outstanding NUMERIC(18, 2) DEFAULT 0.00,
    total_assets NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    total_debt NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    total_cash_and_investments NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    total_receivables NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    total_revenue NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    total_impermissible_income NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    sector_compliant BOOLEAN NOT NULL DEFAULT true,
    sector_failure_reason TEXT,
    purification_ratio NUMERIC(6, 4) NOT NULL DEFAULT 0.0000,
    zakatable_assets_per_share NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    is_nifty_50 BOOLEAN NOT NULL DEFAULT false,
    is_nifty_500 BOOLEAN NOT NULL DEFAULT true,
    audit_notes TEXT,
    
    -- AAOIFI Compliance (36-month rolling avg Market Cap denominator)
    aaoifi_status TEXT GENERATED ALWAYS AS (
        CASE 
            WHEN NOT sector_compliant THEN 'NON_COMPLIANT'
            WHEN (total_impermissible_income / NULLIF(total_revenue, 0)) >= 0.05 THEN 'NON_COMPLIANT'
            WHEN (total_debt / NULLIF(avg_36m_market_cap, 0)) >= 0.33 THEN 'NON_COMPLIANT'
            WHEN (total_cash_and_investments / NULLIF(avg_36m_market_cap, 0)) >= 0.33 THEN 'NON_COMPLIANT'
            WHEN (total_receivables / NULLIF(avg_36m_market_cap, 0)) >= 0.33 THEN 'NON_COMPLIANT'
            ELSE 'COMPLIANT'
        END
    ) STORED,

    -- TASIS Compliance (Total Assets denominator - Indian Scholarly Consensus)
    tasis_status TEXT GENERATED ALWAYS AS (
        CASE 
            WHEN NOT sector_compliant THEN 'NON_COMPLIANT'
            WHEN (total_impermissible_income / NULLIF(total_revenue, 0)) >= 0.05 THEN 'NON_COMPLIANT'
            WHEN (total_debt / NULLIF(total_assets, 0)) >= 0.33 THEN 'NON_COMPLIANT'
            WHEN (total_cash_and_investments / NULLIF(total_assets, 0)) >= 0.33 THEN 'NON_COMPLIANT'
            WHEN (total_receivables / NULLIF(total_assets, 0)) >= 0.49 THEN 'NON_COMPLIANT'
            ELSE 'COMPLIANT'
        END
    ) STORED,
    
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Search and filter indexes
CREATE INDEX IF NOT EXISTS idx_companies_search ON public.companies USING gin(to_tsvector('english', ticker || ' ' || company_name || ' ' || sector));
CREATE INDEX IF NOT EXISTS idx_companies_aaoifi ON public.companies(aaoifi_status);
CREATE INDEX IF NOT EXISTS idx_companies_tasis ON public.companies(tasis_status);

-- ---------------------------------------------------------------------
-- 2. CURATED THEMATIC BASKETS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.curated_baskets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    cagr_3yr NUMERIC(5, 2) NOT NULL,
    sharpe_ratio NUMERIC(5, 2) NOT NULL,
    min_investment NUMERIC(10, 2) NOT NULL DEFAULT 5000.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.basket_constituents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    basket_id TEXT REFERENCES public.curated_baskets(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    weight_percentage NUMERIC(5, 2) NOT NULL,
    CONSTRAINT unique_basket_ticker UNIQUE(basket_id, ticker)
);

-- ---------------------------------------------------------------------
-- 3. CRYPTOGRAPHIC PURIFICATION LEDGER (Per User)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_purification_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    dividend_amount NUMERIC(12, 2) NOT NULL,
    shares_held INTEGER NOT NULL,
    total_dividend NUMERIC(12, 2) NOT NULL,
    purification_ratio NUMERIC(6, 4) NOT NULL,
    purification_due NUMERIC(12, 2) NOT NULL,
    charity_name TEXT,
    is_purified BOOLEAN NOT NULL DEFAULT false,
    prev_entry_hash TEXT NOT NULL DEFAULT 'GENESIS',
    entry_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 4. EQUITY ZAKAT RECORDS (Per User)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_zakat_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    portfolio_value NUMERIC(15, 2) NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('active', 'long_term')),
    calendar TEXT NOT NULL CHECK (calendar IN ('lunar', 'solar')),
    rate_applied NUMERIC(6, 5) NOT NULL,
    nisab_threshold NUMERIC(12, 2) NOT NULL DEFAULT 53550.00,
    is_nisab_met BOOLEAN NOT NULL,
    total_zakat_due NUMERIC(12, 2) NOT NULL,
    holdings_breakdown JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 5. HALAL WEALTH ACADEMY MODULES
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.academy_modules (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    read_time_minutes INTEGER NOT NULL,
    icon_name TEXT NOT NULL,
    sections JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ---------------------------------------------------------------------
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access to companies" ON public.companies FOR SELECT USING (true);

ALTER TABLE public.curated_baskets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access to baskets" ON public.curated_baskets FOR SELECT USING (true);

ALTER TABLE public.basket_constituents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access to basket constituents" ON public.basket_constituents FOR SELECT USING (true);

ALTER TABLE public.academy_modules ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access to academy modules" ON public.academy_modules FOR SELECT USING (true);

ALTER TABLE public.user_purification_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view and manage their own purification ledger"
    ON public.user_purification_ledger FOR ALL
    USING (auth.uid() = user_id);

ALTER TABLE public.user_zakat_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view and manage their own zakat records"
    ON public.user_zakat_records FOR ALL
    USING (auth.uid() = user_id);
