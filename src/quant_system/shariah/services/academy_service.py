"""Service providing the Wealth Academy Curriculum & Non-Margin Demat Onboarding Guides (R6)."""

from quant_system.shariah.schemas.academy import (
    AcademyModuleDetail,
    BrokerDematGuide,
    DematGuideResponse,
    DematMandatoryRule,
    QuizQuestion,
)

# ---------------------------------------------------------------------------
# 1. Four Core Interactive Educational Modules
# ---------------------------------------------------------------------------

MODULE_1 = AcademyModuleDetail(
    id="stewardship-and-inflation",
    title="The Stewardship Imperative & Inflation Trap",
    subtitle="Amanah, Wealth Preservation (Hifz al-Mal), and Beating Fiat Currency Devaluation",
    icon="savings",
    reading_time_minutes=8,
    markdown_content="""# The Stewardship Imperative & Inflation Trap

## 1. Wealth as a Divine Trust (*Amanah*)
In Islamic theology, absolute ownership of all creation belongs solely to Allah (SWT). Wealth placed in human hands is not absolute personal property to squander or hoard; it is a sacred trust (*Amanah*). The Quran explicitly establishes that wealth must circulate beneficially within the economy rather than remaining concentrated:
> *"So that it will not be a perpetual distribution among the rich from among you."* (Surah Al-Hashr 59:7)

Preserving and cultivating wealth ethically is enshrined within the Five Essential Objectives of Islamic Jurisprudence (*Maqasid al-Shariah*) under **Hifz al-Mal** (Protection and Preservation of Wealth).

## 2. The Silent Destruction of Fiat Inflation
In India, consumer price inflation (CPI) has historically compounded at 5.5% to 7.0% per annum. Consider the empirical reality of leaving wealth idle:
- ₹1,000,000 kept in cash or zero-interest bank accounts loses ~50% of its real purchasing power in 10 to 12 years.
- In 25 years, ₹1,000,000 of idle fiat currency will purchase less than ₹200,000 worth of real goods today.

Stashing money in cash under mattresses or non-earning accounts is not piety—it is the guaranteed destruction of your family's economic security and community empowerment.

## 3. The Prohibition of Hoarding (*Kanz*)
The Quran severely condemns the sterile withdrawal of capital from productive commerce:
> *"And those who hoard gold and silver and spend it not in the way of Allah - give them tidings of a painful punishment."* (Surah At-Tawbah 9:34)

True Islamic financial discipline demands deploying surplus savings into productive, asset-backed commercial enterprises that create employment, manufacture real goods, and build ethical societal infrastructure.
""",
    key_takeaways=[
        "Wealth is an Amanah (trust) from Allah, not an absolute personal possession.",
        "Hifz al-Mal (Preservation of Wealth) is a core Maqasid al-Shariah objective.",
        "Indian CPI inflation (5.5%-7.0%) cuts idle cash purchasing power by half every decade.",
        "Hoarding idle currency (Kanz) is severely prohibited in Quran 9:34.",
        "Deploying capital into productive, ethical business partnerships fulfills Islamic stewardship.",
    ],
    quiz_questions=[
        QuizQuestion(
            id="q1-1",
            question="What is the theological status of human wealth in Islam?",
            options=[
                "Absolute individual ownership with unrestricted rights",
                "A sacred trust (Amanah) held under divine stewardship",
                "An evil burden that should be discarded entirely",
                "State-owned property managed by community leaders",
            ],
            correct_index=1,
            explanation="Islam teaches that absolute ownership belongs to Allah alone, while humans act as stewards (Mustakhlafeen) holding wealth as an Amanah.",
        ),
        QuizQuestion(
            id="q1-2",
            question="Why does keeping wealth in idle cash violate Islamic economic principles?",
            options=[
                "Because cash is physically dirty and should not be stored",
                "Because inflation erodes its purchasing power while hoarding (Kanz) denies productive economic circulation",
                "Because paper currency is completely prohibited in classical fiqh",
                "Because commercial banks charge a penalty on uninvested cash",
            ],
            correct_index=1,
            explanation="Leaving cash idle subjects it to guaranteed purchasing power destruction via fiat inflation and violates the prohibition against hoarding (Kanz) cited in Surah At-Tawbah 9:34.",
        ),
        QuizQuestion(
            id="q1-3",
            question="Which essential objective of Islamic law (Maqasid al-Shariah) governs investing?",
            options=[
                "Hifz al-Nafs (Preservation of Life)",
                "Hifz al-'Aql (Preservation of Intellect)",
                "Hifz al-Mal (Preservation and Growth of Wealth)",
                "Hifz al-Nasl (Preservation of Lineage)",
            ],
            correct_index=2,
            explanation="Hifz al-Mal mandates protecting, preserving, and multiplying wealth through lawful, ethical commercial channels.",
        ),
    ],
)

MODULE_2 = AcademyModuleDetail(
    id="islamic-architecture-equities",
    title="Islamic Architecture of Equities (Musharakah)",
    subtitle="Equity Partnerships, Risk-Sharing vs Debt, and the Juristic Nature of Shares",
    icon="handshake",
    reading_time_minutes=10,
    markdown_content="""# Islamic Architecture of Equities (Musharakah)

## 1. What is an Equity Share? (*Hissah Shari'iyyah*)
A common share of stock is not a speculative betting token or a digital casino chip. Legally and jurisprudentially, a share represents an undivided proportionate title of ownership (*Hissah Shari'iyyah*) in the net real assets, intellectual property, inventory, equipment, and future profits of a corporate enterprise.

When you purchase shares of TCS or Infosys, you become a partner owning an undivided fraction of:
- High-tech campus buildings, servers, and software patents.
- Contractual receivables from Fortune 500 enterprise clients.
- Working capital balances and operating cash reserves.

## 2. Classical Partnerships: *Sharikah al-'Inan* & *Mudarabah*
Modern joint-stock corporations map directly to the classical Islamic partnership models:
1. **Sharikah al-'Inan (Contractual Partnership)**: Partners contribute capital and share profits according to agreed ratios and losses strictly proportionate to capital invested.
2. **Mudarabah (Capital-Labor Venture)**: Passive shareholders provide capital while professional executives and corporate management provide labor and operational expertise.

The foundational juristic maxim governing equity is:
> **"Al-Ghunm bil-Ghurm"** *(Profit accompanies liability for loss)*
Unlike conventional lenders who demand guaranteed interest regardless of business success or bankruptcy, an equity partner takes genuine commercial business risk.

## 3. Legitimacy of Limited Liability (*Dhimmah Mustaqillah*)
In 1990, the OIC Islamic Fiqh Academy issued landmark Resolution No. 63 formally ratifying the concept of the modern corporation with limited liability. The Academy established that a corporation possesses an independent juristic personality (*Dhimmah Mustaqillah* / *Shakhsiyyah I'tibariyyah*), meaning:
- The company's legal obligations do not automatically attach to the shareholder's personal estate.
- The investor's liability is strictly capped at their invested capital in the shares.
""",
    key_takeaways=[
        "A share of stock represents true undivided ownership (Hissah) in real business assets.",
        "Joint-stock companies are legitimate modern forms of Sharikah al-'Inan and Mudarabah.",
        "The core Islamic principle 'Al-Ghunm bil-Ghurm' mandates sharing risk to justify profit.",
        "Corporate limited liability is recognized by the OIC Fiqh Academy under Dhimmah Mustaqillah.",
        "Equity investing is fundamentally distinct from conventional interest-based lending.",
    ],
    quiz_questions=[
        QuizQuestion(
            id="q2-1",
            question="What does an equity share represent in Islamic jurisprudence?",
            options=[
                "A loan given to the CEO with an expectation of interest",
                "An undivided fractional ownership title in the company's real assets and business",
                "A government-guaranteed debt bond",
                "A speculative derivative contract on market sentiment",
            ],
            correct_index=1,
            explanation="A share is a legal title (Hissah) to an undivided fractional share of the tangible assets, intangible rights, and enterprise value of the operating corporation.",
        ),
        QuizQuestion(
            id="q2-2",
            question="What is the meaning of the legal maxim 'Al-Ghunm bil-Ghurm'?",
            options=[
                "Profits are guaranteed to those who trade daily",
                "Entitlement to profit is justified only by bearing liability for commercial loss",
                "Debt must be repaid with compounded interest",
                "Losses should always be transferred to external brokers",
            ],
            correct_index=1,
            explanation="'Al-Ghunm bil-Ghurm' establishes that one cannot legitimately claim business profits without accepting the corresponding commercial risk and liability of enterprise loss.",
        ),
        QuizQuestion(
            id="q2-3",
            question="How did the OIC Islamic Fiqh Academy resolve the question of limited liability?",
            options=[
                "It declared limited liability completely invalid and impermissible",
                "It approved limited liability based on the independent legal personality (Dhimmah Mustaqillah) of corporations",
                "It restricted limited liability only to non-profit charitable trusts",
                "It permitted limited liability only if the company has zero employees",
            ],
            correct_index=1,
            explanation="Resolution No. 63 (1990) of the OIC Islamic Fiqh Academy affirmed that modern corporations have a distinct legal persona (Shakhsiyyah I'tibariyyah), validating limited liability.",
        ),
    ],
)

MODULE_3 = AcademyModuleDetail(
    id="financial-evils-riba-gharar-maysir",
    title="Financial Evils: Riba, Gharar & Maysir",
    subtitle="Anatomy of Contemporary Financial Evils and Why Modern Derivatives are Prohibited",
    icon="warning_amber",
    reading_time_minutes=11,
    markdown_content="""# Financial Evils: Riba, Gharar & Maysir

## 1. The Three Prohibitions of Islamic Commercial Jurisprudence
Every financial prohibition in Shariah traces back to three fundamental structural evils:
1. **Riba (Usury / Interest)**: Unjustified contractual increase on loans or exchanges of monetary assets without counter-value (*'Iwad*).
2. **Gharar (Excessive Ambiguity / Uncertainty)**: Ignorance or indeterminacy regarding the existence, delivery, quantity, or quality of the transacted commodity.
3. **Maysir / Qimar (Gambling & Speculation)**: Zero-sum arrangements where one party's financial gain is contingent purely on the unearned financial loss of the counterparty.

## 2. Riba in Modern Capital Markets
Riba is not merely exorbitant loan-sharking; all predetermined interest is prohibited, including:
- Interest paid on bank Fixed Deposits (FDs) and recurring deposits.
- Interest coupons paid on corporate debentures and government treasury bonds.
- **Margin Trading Facility (MTF)**: Borrowing money from a broker at 12% to 18% p.a. to purchase equities is direct *Riba al-Nasiah*.

## 3. Why Derivatives (Futures & Options - F&O) are Haram
In India, the National Stock Exchange (NSE) sees trillions of rupees transacted in index and stock derivatives. Why does Islamic jurisprudence strictly prohibit Futures and Options?
- **Trading the Non-Existent**: Selling a call or put option sells a synthetic contractual right, not real property (*Mal Mutaqawwim*).
- **Separation of Risk from Asset**: Derivatives sever financial risk from physical ownership, creating massive systemic instability.
- **Sale of Debt for Debt (*Bay' al-Kali bil-Kali*)**: In index futures, neither the underlying shares are ever delivered nor is full cash paid at settlement; it is purely a settlement of price differences.
- **Pure Maysir (Gambling)**: SEBI's official study revealed that 93% of individual F&O retail traders in India lost money, surrendering collective wealth to automated algorithmic market makers.

## 4. Short Selling and Securities Lending (SLBM)
The Prophet Muhammad (peace be upon him) commanded:
> **"Do not sell that which you do not possess."** (Sunan Abu Dawood, Tirmidhi)
In conventional short selling, a trader borrows shares via the Securities Lending & Borrowing Mechanism (SLBM) and sells them into the market hoping for a price collapse. This is impermissible because:
- The seller does not own the shares at the time of sale.
- The lender charges an interest-like fee for lending securities.
""",
    key_takeaways=[
        "Islamic commercial transactions must be completely free from Riba, Gharar, and Maysir.",
        "Margin Trading Facilities (MTF) charge 12%-18% interest and are categorically Riba.",
        "Futures and Options (F&O) decouple risk from real assets and function as zero-sum gambling.",
        "Short selling violates the explicit Prophetic prohibition 'Do not sell what you do not own.'",
        "Halal investing strictly requires cash-and-carry delivery (CNC) of actual shares.",
    ],
    quiz_questions=[
        QuizQuestion(
            id="q3-1",
            question="Why is Margin Trading Facility (MTF) prohibited in Islamic finance?",
            options=[
                "Because brokers charge too low a commission",
                "Because it involves borrowing capital on compound interest (Riba) to purchase stocks",
                "Because MTF stocks are never listed on the exchange",
                "Because SEBI has banned MTF for all Indian citizens",
            ],
            correct_index=1,
            explanation="MTF involves borrowing money from the brokerage at an interest rate (typically 12%-18% p.a.), which constitutes unambiguous Riba al-Nasiah.",
        ),
        QuizQuestion(
            id="q3-2",
            question="Why are equity Futures and Options (F&O) contracts impermissible in Shariah?",
            options=[
                "Because options do not represent real physical property (Mal) and separate risk from asset ownership (Gharar and Maysir)",
                "Because index options are too cheap to purchase",
                "Because options can only be purchased on American exchanges",
                "Because options pay no dividends",
            ],
            correct_index=0,
            explanation="Derivatives lack underlying physical property rights (Mal Mutaqawwim), involve excessive speculation (Gharar Fahish), and constitute zero-sum gambling (Maysir).",
        ),
        QuizQuestion(
            id="q3-3",
            question="Which Prophetic Hadith directly prohibits conventional short selling?",
            options=[
                "'Seek knowledge even unto China'",
                "'Do not sell that which you do not possess' (La tabi' ma laysa 'indak)",
                "'Actions are judged by intentions'",
                "'The strong believer is better than the weak believer'",
            ],
            correct_index=1,
            explanation="The Prophet (SAW) commanded 'Do not sell that which you do not possess,' directly forbidding selling borrowed shares that one does not own.",
        ),
    ],
)

MODULE_4 = AcademyModuleDetail(
    id="ten-principles-disciplined-investor",
    title="10 Principles of the Disciplined Halal Investor",
    subtitle="Long-Term Wealth Compounding, Dual Screening, Dividend Cleansing, and Waqf Legacy",
    icon="verified",
    reading_time_minutes=12,
    markdown_content="""# 10 Principles of the Disciplined Halal Investor

The disciplined Halal investor avoids market hysteria, short-term speculation, and emotional panic by adhering to ten timeless principles:

### Principle 1: Invest Only in Real Businesses You Understand
Never buy a ticker based on anonymous social media 'tips' or viral hype. Demand clarity on how the enterprise creates tangible economic value for customers.

### Principle 2: Demand Zero or Low Interest-Bearing Debt (< 33%)
High debt invites financial fragility and violates Islamic guidelines. Select companies with interest-bearing debt strictly under 33% of market cap or total assets.

### Principle 3: Filter Out Impermissible Business Activities
Strictly exclude conventional commercial banking, insurance, alcohol, gambling, pork, tobacco, non-halal entertainment media, and defense manufacturing.

### Principle 4: Implement Dual-Standard Screening (AAOIFI & TASIS)
Verify compliance under both global standards: AAOIFI (market capitalization denominator) and TASIS / BSE Shariah 50 (total book assets denominator).

### Principle 5: Purify Every Dividend Without Hesitation
Cleans incidental non-operating interest income earned by companies on cash reserves by calculating $\\rho = \\text{Interest Income} / \\text{Total Revenue}$ and donating that exact portion to public charity.

### Principle 6: Calculate and Disburse Exact Annual Zakat
Pay 2.5% on qualifying wealth annually. Utilize the Long-Term Investor method (Zakatable Net Working Assets per share) to avoid paying Zakat on exempt factory machinery.

### Principle 7: Adopt a 5 to 10 Year Compounding Horizon
Equity wealth is harvested through long-term corporate growth and compounding retained earnings, not intraday churn. Patient capital is the hallmark of the believer.

### Principle 8: Maintain 100% Cash-and-Carry Discipline (CNC Only)
Never use margin leverage, day trading, or borrowed capital. If you have ₹50,000, buy exactly ₹50,000 worth of shares for delivery into your Demat account.

### Principle 9: Diversify Across 15 to 25 Quality Leaders
Never concentrate all savings in a single stock or sector. Diversify across information technology, healthcare, FMCG, infrastructure, and green engineering.

### Principle 10: Establish a Generational Endowment (*Waqf*)
Dedicate a percentage of long-term investment gains to establishing perpetual endowments (Waqf) for public education, rural healthcare, and community uplifting.
""",
    key_takeaways=[
        "Disciplined equity investing requires patience, business understanding, and ethical conviction.",
        "Both AAOIFI and TASIS screening criteria should be monitored to detect financial divergence.",
        "Dividend purification cleanses wealth from incidental bank interest without expectation of spiritual reward.",
        "Annual Zakat must be calculated with precision on circulating working capital.",
        "The ultimate goal of Halal wealth creation is family security and perpetual community Waqf.",
    ],
    quiz_questions=[
        QuizQuestion(
            id="q4-1",
            question="What is the recommended holding horizon for a disciplined Halal equity investor?",
            options=[
                "Intraday (sell before market close at 3:30 PM)",
                "Weekly swing trading based on momentum charts",
                "5 to 10 years of patient business compounding",
                "1 to 2 months between quarterly earnings announcements",
            ],
            correct_index=2,
            explanation="True equity wealth generation aligns with multi-year business growth and compounding, avoiding speculative short-term churn.",
        ),
        QuizQuestion(
            id="q4-2",
            question="What must an investor do with the dividend purification amount?",
            options=[
                "Reinvest it into purchasing more shares of the same company",
                "Donate it to public charity without expecting personal spiritual reward (thawab)",
                "Use it to pay personal income taxes to the government",
                "Keep it in a dedicated fixed deposit account",
            ],
            correct_index=1,
            explanation="AAOIFI Standard No. 21 requires giving the impermissible income portion to public charity to cleanse wealth, without expectation of religious thawab.",
        ),
        QuizQuestion(
            id="q4-3",
            question="Why is Cash-and-Carry (CNC) the only permissible product type for Muslim investors in India?",
            options=[
                "Because CNC orders have lower government brokerage taxes",
                "Because CNC ensures full upfront payment and true physical delivery of shares to your Demat account without margin borrowing",
                "Because CNC orders can only be placed during morning hours",
                "Because CNC is restricted exclusively to Shariah-compliant equities",
            ],
            correct_index=1,
            explanation="CNC (Cash & Carry) guarantees 100% full delivery of legal share ownership without utilizing interest-bearing margin loans (MIS/MTF).",
        ),
    ],
)

ALL_MODULES: list[AcademyModuleDetail] = [MODULE_1, MODULE_2, MODULE_3, MODULE_4]

# Module lookup map for fast O(1) slug and alias resolution
_MODULE_MAP = {
    "stewardship-and-inflation": MODULE_1,
    "module-1": MODULE_1,
    "module_1": MODULE_1,
    "1": MODULE_1,
    "islamic-architecture-equities": MODULE_2,
    "module-2": MODULE_2,
    "module_2": MODULE_2,
    "2": MODULE_2,
    "financial-evils-riba-gharar-maysir": MODULE_3,
    "module-3": MODULE_3,
    "module_3": MODULE_3,
    "3": MODULE_3,
    "ten-principles-disciplined-investor": MODULE_4,
    "module-4": MODULE_4,
    "module_4": MODULE_4,
    "4": MODULE_4,
}


# ---------------------------------------------------------------------------
# 2. Universal Demat Rules & 4-Broker Onboarding Guides
# ---------------------------------------------------------------------------

UNIVERSAL_DEMAT_RULES: list[DematMandatoryRule] = [
    DematMandatoryRule(
        rule_id="RULE-1",
        rule_text="Open standard Equity Cash account only",
        is_mandatory=True,
        shariah_rationale="Confines the account strictly to genuine asset ownership and excludes speculative derivatives.",
    ),
    DematMandatoryRule(
        rule_id="RULE-2",
        rule_text="Ensure order product is strictly CNC (Cash & Carry)",
        is_mandatory=True,
        shariah_rationale="Guarantees full upfront capital payment and physical delivery of shares into CDSL/NSDL Demat.",
    ),
    DematMandatoryRule(
        rule_id="RULE-3",
        rule_text="Decline Intraday MIS trading",
        is_mandatory=True,
        shariah_rationale="MIS (Margin Intraday Square-off) relies on broker leverage and forces same-day closure, mimicking gambling.",
    ),
    DematMandatoryRule(
        rule_id="RULE-4",
        rule_text="Decline Futures & Options segment",
        is_mandatory=True,
        shariah_rationale="F&O derivatives are synthetic contracts containing excessive Gharar and zero-sum Maysir.",
    ),
    DematMandatoryRule(
        rule_id="RULE-5",
        rule_text="Decline Securities Lending & Borrowing Mechanism (SLBM)",
        is_mandatory=True,
        shariah_rationale="Prevents the broker from lending your shares to short-sellers who sell what they do not own.",
    ),
]

MANDATORY_RULES_LIST = [
    "Open standard Equity Cash account only",
    "Ensure order product is strictly CNC (Cash & Carry)",
    "Decline Intraday MIS trading",
    "Decline Futures & Options segment",
    "Decline Securities Lending & Borrowing Mechanism (SLBM)",
]

ZERODHA_GUIDE = BrokerDematGuide(
    broker_id="zerodha",
    broker_name="Zerodha",
    tagline="India's largest discount broker, naturally well-suited for Halal investing due to absence of interest-bearing MTF.",
    account_type="Equity Cash & Demat (CDSL)",
    product_mode="CNC",
    margin_mtf="DISABLED",
    slbm_status="INACTIVE",
    derivatives_fo="DISABLED",
    mandatory_rules=MANDATORY_RULES_LIST,
    setup_steps=[
        "Step 1 (Account Opening): Complete digital e-KYC. When prompted for segment selection, select ONLY 'Equity'. Leave 'Futures & Options' and 'Commodity' UNCHECKED.",
        "Step 2 (Margin Check): Zerodha does not offer conventional Margin Trading Facility (MTF) with interest charges, eliminating the primary Riba trap in Indian brokerages.",
        "Step 3 (Verify SLBM): Log into Zerodha Console > Navigate to 'Account' > 'Demat' > Confirm that SLBM status is set to 'Inactive'.",
        "Step 4 (Order Execution): When placing buy orders in Kite web or mobile, verify the toggle is strictly set to 'Longterm (CNC)'. Never select 'Intraday (MIS)'.",
        "Step 5 (Linked Bank Account): Ensure your linked savings account does not feature automatic sweep-in fixed deposits that accrue compound interest.",
    ],
    critical_warnings=[
        "Never use 'Kite Margin' or 'Intraday MIS' orders. MIS positions are auto-squared off at 3:20 PM by the risk management system.",
        "Do not activate the F&O segment even if prompted with automated activation nudges.",
    ],
    verification_checklist=[
        "CDSL Demat statement shows direct delivery credit of shares (T+1 settlement).",
        "Console profile displays: F&O segment: INACTIVE.",
        "Console profile displays: SLBM: INACTIVE.",
        "Order history confirms 100% of completed trades executed under product code 'CNC'.",
    ],
)

GROWW_GUIDE = BrokerDematGuide(
    broker_id="groww",
    broker_name="Groww",
    tagline="Modern mobile-first broker. Requires explicit deactivation of 'Groww Pay Later / MTF'.",
    account_type="Equity Stocks & Demat",
    product_mode="CNC",
    margin_mtf="DISABLED",
    slbm_status="INACTIVE",
    derivatives_fo="DISABLED",
    mandatory_rules=MANDATORY_RULES_LIST,
    setup_steps=[
        "Step 1: Open standard Stocks account using Aadhaar e-Sign. Skip F&O activation during onboarding.",
        "Step 2 (Deactivate MTF): Groww aggressively markets 'Pay Later / MTF'. Navigate to App Settings > 'Trading Preferences' > 'Margin Trading Facility (MTF)' > Toggle OFF or Click 'Deactivate'.",
        "Step 3 (Order Placement): On the stock order screen, ensure the top tab is set to 'Delivery'. Never toggle to 'Intraday'.",
        "Step 4 (SLBM Check): Ensure account is not enrolled in Groww Securities Lending. Contact Groww support to confirm SLBM is disabled.",
    ],
    critical_warnings=[
        "Groww Pay Later charges up to 18% annualized interest on borrowed margin. You must explicitly ensure it is turned OFF.",
        "Do not enable 'Instant Pay Later' during checkout or stock purchasing.",
    ],
    verification_checklist=[
        "Profile shows MTF / Pay Later status: DEACTIVATED.",
        "Order confirmation receipt displays 'Delivery (CNC)'.",
        "F&O segment status shows 'Not Activated'.",
    ],
)

UPSTOX_GUIDE = BrokerDematGuide(
    broker_id="upstox",
    broker_name="Upstox",
    tagline="Technology-focused discount broker. Promptly decline 4x MTF leverage banners.",
    account_type="Equity Cash & Delivery Demat",
    product_mode="DELIVERY",
    margin_mtf="DISABLED",
    slbm_status="INACTIVE",
    derivatives_fo="DISABLED",
    mandatory_rules=MANDATORY_RULES_LIST,
    setup_steps=[
        "Step 1: Complete online application for 'Equity Delivery' only. Deselect F&O and MCX Commodities.",
        "Step 2 (Decline MTF): When prompted on login with 'Get up to 4x Buying Power with Margin Trading Facility', click 'Decline / Not Interested'.",
        "Step 3 (Order Window): In Upstox Pro app, select order product 'Delivery'. Avoid 'Intraday' or 'Cover Order (CO)'.",
        "Step 4: Verify in Upstox Profile > Segments that Securities Lending (SLBM) is completely inactive.",
    ],
    critical_warnings=[
        "Never accept '4x Buying Power' prompts—these are interest-accruing margin loans.",
        "Do not use Cover Orders or Bracket Orders, as they mandate intraday stop-loss leverage.",
    ],
    verification_checklist=[
        "Segment status shows 'Equity Cash: Active' and 'F&O: Inactive'.",
        "Margin Trading Facility (MTF) agreement status shows 'Not Opted In'.",
        "All trades settle with delivery into your CDSL Demat depository.",
    ],
)

ANGELONE_GUIDE = BrokerDematGuide(
    broker_id="angelone",
    broker_name="AngelOne",
    tagline="Full-service retail broker. Requires deliberate opt-out from Margin Trade Funding.",
    account_type="AngelOne Equity Delivery Demat",
    product_mode="DELIVERY",
    margin_mtf="DISABLED",
    slbm_status="INACTIVE",
    derivatives_fo="DISABLED",
    mandatory_rules=MANDATORY_RULES_LIST,
    setup_steps=[
        "Step 1: Open AngelOne SuperApp account. Choose basic Equity segment. De-select Commodity and Currency.",
        "Step 2 (Revoke MTF): AngelOne often pre-approves Margin Trade Funding. Go to Profile > 'Active Services' > 'Margin Trading Facility (MTF)' > Click 'Opt-Out / Revoke'.",
        "Step 3 (Order Mode): In the order pad, select 'Delivery'. Avoid 'Intraday' and 'Margin (MTF)'.",
        "Step 4 (Revoke SLBM): Ensure your Demat mandate does not permit lending your held shares to institutional borrowers.",
    ],
    critical_warnings=[
        "AngelOne's order screen often defaults to 'Margin' rather than 'Delivery'. Always double check that 'Delivery' is highlighted before swiping to buy.",
        "Check your monthly statement for any 'Margin Interest' or 'Delayed Payment Charges'. A pure cash account should have zero interest charges.",
    ],
    verification_checklist=[
        "Active Segments confirms MTF has been successfully revoked.",
        "Trade ledger confirms 100% of securities purchased under 'Delivery'.",
        "Zero interest charges or ledger debit charges recorded on cash balance.",
    ],
)

ALL_BROKERS = [ZERODHA_GUIDE, GROWW_GUIDE, UPSTOX_GUIDE, ANGELONE_GUIDE]

_BROKER_MAP = {
    "zerodha": ZERODHA_GUIDE,
    "kite": ZERODHA_GUIDE,
    "groww": GROWW_GUIDE,
    "upstox": UPSTOX_GUIDE,
    "upstoxpro": UPSTOX_GUIDE,
    "angelone": ANGELONE_GUIDE,
    "angel-one": ANGELONE_GUIDE,
    "angel_one": ANGELONE_GUIDE,
    "angel": ANGELONE_GUIDE,
}


# ---------------------------------------------------------------------------
# 3. Service Query Functions
# ---------------------------------------------------------------------------


def get_all_modules() -> list[AcademyModuleDetail]:
    """Return all 4 core interactive educational modules."""
    return ALL_MODULES


def get_module_by_id(module_id: str) -> AcademyModuleDetail | None:
    """Return a single educational module by unique slug ID or alias."""
    clean_id = module_id.lower().strip()
    if clean_id in _MODULE_MAP:
        return _MODULE_MAP[clean_id]
    for m in ALL_MODULES:
        if m.id == clean_id or m.title.lower() == clean_id:
            return m
    return None


def get_demat_onboarding_guide() -> DematGuideResponse:
    """Return universal Shariah onboarding rules and 4-broker setup guides."""
    return DematGuideResponse(
        universal_rules=UNIVERSAL_DEMAT_RULES,
        brokers=ALL_BROKERS,
    )


def get_broker_guide(broker_id: str) -> BrokerDematGuide | None:
    """Return onboarding guide for a specific Indian broker."""
    clean_id = broker_id.lower().strip()
    if clean_id in _BROKER_MAP:
        return _BROKER_MAP[clean_id]
    for b in ALL_BROKERS:
        if b.broker_id == clean_id or b.broker_name.lower() == clean_id:
            return b
    return None
