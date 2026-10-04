#!/usr/bin/env python3
"""
QuantOS Moonshot Strategic Whitepaper & Technical Architecture Generator
Generates an 11-page publication-grade institutional whitepaper in Light Mode.
"""
# mypy: ignore-errors

import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

pt = 1.0

# Institutional Color Palette
PRIMARY_NAVY = colors.HexColor("#0B1E3D")  # Dominant institutional header
SECONDARY_BLUE = colors.HexColor("#1D4ED8")  # Vibrant accent
SLATE_DARK = colors.HexColor("#0F172A")  # Deep charcoal heading
BODY_CHARCOAL = colors.HexColor("#334155")  # High readability body
MUTED_TEXT = colors.HexColor("#64748B")  # Subtitles and table headers
ACCENT_GREEN = colors.HexColor("#047857")  # Invariant pass / green signal
ACCENT_RED = colors.HexColor("#B91C1C")  # Risk circuit / red team alert
ACCENT_AMBER = colors.HexColor("#B45309")  # Warning / friction
BG_LIGHT_BLUE = colors.HexColor("#F0F5FA")  # Box background
BG_CARD_LIGHT = colors.HexColor("#F8FAFC")  # Card fill
BORDER_LIGHT = colors.HexColor("#E2E8F0")  # Table and card border
BORDER_NAVY = colors.HexColor("#0B1E3D")  # Thick rule border

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 44 * pt


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total pages and stamp
    publication-grade running headers and footers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(MUTED_TEXT)

        # Skip running header on cover page
        if self._pageNumber > 1:
            # Running Header
            self.drawString(
                MARGIN, PAGE_HEIGHT - 32 * pt, "QUANTOS : INSTITUTIONAL RESEARCH & EXECUTION OS"
            )
            self.drawRightString(
                PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 32 * pt, "STRATEGIC MOONSHOT BLUEPRINT"
            )
            self.setStrokeColor(BORDER_LIGHT)
            self.setLineWidth(0.75)
            self.line(MARGIN, PAGE_HEIGHT - 36 * pt, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 36 * pt)

        # Running Footer (All pages)
        self.setStrokeColor(BORDER_LIGHT)
        self.setLineWidth(0.75)
        self.line(MARGIN, 38 * pt, PAGE_WIDTH - MARGIN, 38 * pt)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED_TEXT)
        self.drawString(
            MARGIN,
            26 * pt,
            "CONFIDENTIAL & PROPRIETARY — FOR INSTITUTIONAL ALLOCATORS & CORE ARCHITECTS",
        )
        self.drawRightString(
            PAGE_WIDTH - MARGIN, 26 * pt, f"Page {self._pageNumber} of {page_count}"
        )
        self.restoreState()


def create_styles():
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(
        ParagraphStyle(
            name="DocSuperTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=SECONDARY_BLUE,
            textTransform="uppercase",
            spaceAfter=4,
        )
    )

    styles.add(
        ParagraphStyle(
            name="DocTitle",
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=PRIMARY_NAVY,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="DocSubtitle",
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=BODY_CHARCOAL,
            spaceAfter=14,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=PRIMARY_NAVY,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubSectionHeader",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13.5,
            textColor=SECONDARY_BLUE,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        )
    )

    styles.add(
        ParagraphStyle(
            name="WhitepaperBody",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=BODY_CHARCOAL,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="WhitepaperBodyBold",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.5,
            textColor=SLATE_DARK,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CalloutText",
            fontName="Helvetica",
            fontSize=8.2,
            leading=11.2,
            textColor=SLATE_DARK,
        )
    )

    styles.add(
        ParagraphStyle(
            name="FormulaText",
            fontName="Courier-Bold",
            fontSize=8.2,
            leading=11,
            textColor=PRIMARY_NAVY,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=7.8,
            leading=10,
            textColor=BODY_CHARCOAL,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableCellBold",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            leading=10,
            textColor=SLATE_DARK,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableHead",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TeaserHeadline",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=PRIMARY_NAVY,
            spaceAfter=4,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BadgeLabel",
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8,
            textColor=MUTED_TEXT,
            textTransform="uppercase",
            alignment=1,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BadgeValue",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=PRIMARY_NAVY,
            alignment=1,
        )
    )

    return styles


def build_card(content_list, bg_color=BG_CARD_LIGHT, border_color=BORDER_LIGHT, padding=8):
    """Encapsulates flowables into a styled institutional card."""
    t = Table([[content_list]], colWidths=[PAGE_WIDTH - 2 * MARGIN])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 0.75, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                ("TOPPADDING", (0, 0), (-1, -1), padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ]
        )
    )
    return t


def build_pdf(filename="docs/QuantOS_Moonshot_Strategic_Whitepaper.pdf"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    styles = create_styles()
    story = []

    # ==========================================
    # PAGE 1: TITLE & EXECUTIVE TEASER ONE-PAGER
    # ==========================================
    story.append(
        Paragraph("INSTITUTIONAL RESEARCH MONOGRAPH & STRATEGIC BLUEPRINT", styles["DocSuperTitle"])
    )
    story.append(
        Paragraph(
            "QuantOS: The Governed Operating System for Systematic Capital & Autonomous Alpha",
            styles["DocTitle"],
        )
    )
    story.append(
        Paragraph(
            "A rigorous mathematical framework, modular software architecture, and 5-year strategic moonshot "
            "designed to eliminate backtest overfitting and pioneer autonomous, multi-agent quantitative fund infrastructure.",
            styles["DocSubtitle"],
        )
    )

    # Metadata Strip
    meta_data = [
        [
            Paragraph(
                "<b>DOCUMENT REVISION</b><br/>v2.4 Professional Release Candidate",
                styles["TableCell"],
            ),
            Paragraph(
                "<b>MARKET UNIVERSE</b><br/>NSE India (Cash Equities, Futures & Options)",
                styles["TableCell"],
            ),
            Paragraph(
                "<b>COMPLIANCE TIER</b><br/>T2/P5 Release Candidate Ready", styles["TableCell"]
            ),
            Paragraph(
                "<b>SECURITY & AUDIT</b><br/>Content-Addressed Immutable Vault", styles["TableCell"]
            ),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[(PAGE_WIDTH - 2 * MARGIN) / 4.0] * 4)
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # KPI Highlight Badges
    badge_data = [
        [
            Paragraph(
                "<font color='#047857'><b>1,519+</b></font><br/><font size='7' color='#64748B'>PASSING UNIT/INT TESTS</font>",
                styles["BadgeValue"],
            ),
            Paragraph(
                "<font color='#1D4ED8'><b>0.0000%</b></font><br/><font size='7' color='#64748B'>FLOAT DRIFT (DECIMAL)</font>",
                styles["BadgeValue"],
            ),
            Paragraph(
                "<font color='#B45309'><b>0.224%</b></font><br/><font size='7' color='#64748B'>NSE STATUTORY FRICTION</font>",
                styles["BadgeValue"],
            ),
            Paragraph(
                "<font color='#0B1E3D'><b>101</b></font><br/><font size='7' color='#64748B'>GOVERNED REAL TRIALS</font>",
                styles["BadgeValue"],
            ),
            Paragraph(
                "<font color='#B91C1C'><b>0 ORDERS</b></font><br/><font size='7' color='#64748B'>LIVE BROKER (SHADOW T4)</font>",
                styles["BadgeValue"],
            ),
        ]
    ]
    badge_table = Table(badge_data, colWidths=[(PAGE_WIDTH - 2 * MARGIN) / 5.0] * 5)
    badge_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(badge_table)
    story.append(Spacer(1, 10))

    # Executive Teaser Card
    teaser_content = [
        Paragraph("EXECUTIVE TEASER : THE 3-MINUTE OVERVIEW", styles["TeaserHeadline"]),
        Paragraph(
            "<b>The Problem:</b> Over 90% of commercial and academic quantitative models fail when deployed with real capital. "
            "The root cause is not lack of mathematical sophistication, but the <i>Quant Reproducibility Crisis</i>: "
            "subtle lookahead bias, floating-point penny leaks, omitted statutory friction, survivorship bias, and rampant "
            "p-hacking (testing hundreds of variations and reporting only the best Sharpe ratio).",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>What QuantOS Is:</b> QuantOS is an institutional, local-first quantitative research, backtesting, risk governance, "
            "and shadow-trading operating system built natively for Indian NSE equities and derivatives. It is architected "
            "around a fundamental iron law: <i>A trading model cannot be promoted or executed on evidence it has not earned.</i>",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>The Core Innovation:</b> 1) <b>Exact Decimal Accounting</b> eliminating floating-point rounding error across cash, "
            "STT, GST, and SEBI charges. 2) <b>Deterministic Zero-Lookahead Engine</b> where bar-close signals strictly execute at next-bar open. "
            "3) <b>Statistical Governance via Deflated Sharpe Ratios (DSR)</b> that mathematically penalizes models for every trial "
            "conducted across the research lifecycle. 4) <b>Immutable Content-Addressed Vaults</b> guaranteeing end-to-end auditability.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>The 5-Year Moonshot Trajectory:</b> Transforming QuantOS from an institutional research operating system into a "
            "globally scalable, autonomous quantitative fund platform powered by self-optimizing multi-agent AI swarms, sub-microsecond "
            "co-located C++/Rust execution, cross-asset international arbitrage, and a cryptographic capital allocation sandbox.",
            styles["WhitepaperBody"],
        ),
    ]
    story.append(
        build_card(teaser_content, bg_color=BG_CARD_LIGHT, border_color=SECONDARY_BLUE, padding=9)
    )
    story.append(Spacer(1, 10))

    teaser_footer = Paragraph(
        '<i>"QuantOS does not exist to manufacture flattering backtests. It exists to be an incorruptible truth-seeking engine '
        'that protects capital against statistical self-deception."</i>',
        styles["WhitepaperBodyBold"],
    )
    story.append(teaser_footer)

    story.append(PageBreak())

    # ==========================================
    # PAGE 2: TABLE OF CONTENTS & MOONSHOT THESIS
    # ==========================================
    story.append(
        Paragraph("SECTION 1 : TABLE OF CONTENTS & STRATEGIC FOUNDATIONS", styles["DocSuperTitle"])
    )
    story.append(Paragraph("Table of Contents & Executive Thesis", styles["SectionHeader"]))
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    toc_data = [
        [
            Paragraph("<b>Sec</b>", styles["TableHead"]),
            Paragraph("<b>Section Title</b>", styles["TableHead"]),
            Paragraph("<b>Core Coverage & Methodological Highlights</b>", styles["TableHead"]),
            Paragraph("<b>Page</b>", styles["TableHead"]),
        ],
        [
            Paragraph("1", styles["TableCellBold"]),
            Paragraph("Table of Contents & Strategic Foundations", styles["TableCellBold"]),
            Paragraph(
                "Executive outline, document taxonomy, and the Moonshot Thesis", styles["TableCell"]
            ),
            Paragraph("2", styles["TableCell"]),
        ],
        [
            Paragraph("2", styles["TableCellBold"]),
            Paragraph("The Quant Crisis & Five Non-Negotiable Invariants", styles["TableCellBold"]),
            Paragraph(
                "Reproducibility failure, Decimal precision, zero-lookahead, and risk governance",
                styles["TableCell"],
            ),
            Paragraph("3", styles["TableCell"]),
        ],
        [
            Paragraph("3", styles["TableCellBold"]),
            Paragraph("System Architecture & Pipeline Topology", styles["TableCellBold"]),
            Paragraph(
                "Modular monolith, supervised worker hierarchy, and state machine transitions",
                styles["TableCell"],
            ),
            Paragraph("4", styles["TableCell"]),
        ],
        [
            Paragraph("4", styles["TableCellBold"]),
            Paragraph("The Empirical Ground Truth : 101 Governed Trials", styles["TableCellBold"]),
            Paragraph(
                "The NIFTY 50 campaign post-mortem, friction breakdown, and corporate action realities",
                styles["TableCell"],
            ),
            Paragraph("5", styles["TableCell"]),
        ],
        [
            Paragraph("5", styles["TableCellBold"]),
            Paragraph("Mathematical Governance & Deflated Sharpe Engine", styles["TableCellBold"]),
            Paragraph(
                "Bailey & López de Prado formulations, moment boundary stability, and purged folds",
                styles["TableCell"],
            ),
            Paragraph("6", styles["TableCell"]),
        ],
        [
            Paragraph("6", styles["TableCellBold"]),
            Paragraph("Subsystems Breakdown & Software Craftsmanship", styles["TableCellBold"]),
            Paragraph(
                "10 modular engine specifications, 1,519-test suite, and strict Mypy/Ruff gates",
                styles["TableCell"],
            ),
            Paragraph("7", styles["TableCell"]),
        ],
        [
            Paragraph("7", styles["TableCellBold"]),
            Paragraph(
                "5-Year Moonshot : Pillars 1 & 2 (AI Swarms & Colo Core)", styles["TableCellBold"]
            ),
            Paragraph(
                "Autonomous LLM research swarms, sub-microsecond C++/Rust kernel, and BKC Colo",
                styles["TableCell"],
            ),
            Paragraph("8", styles["TableCell"]),
        ],
        [
            Paragraph("8", styles["TableCellBold"]),
            Paragraph(
                "5-Year Moonshot : Pillars 3 & 4 (Global & Capital OS)", styles["TableCellBold"]
            ),
            Paragraph(
                "Cross-market expansion (US/FX/Crypto) and decentralized quantitative allocator OS",
                styles["TableCell"],
            ),
            Paragraph("9", styles["TableCell"]),
        ],
        [
            Paragraph("9", styles["TableCellBold"]),
            Paragraph("Institutional Roadmap & Governance Slices", styles["TableCellBold"]),
            Paragraph(
                "Phased milestones (2026-2030), verification gates, and institutional assurance matrix",
                styles["TableCell"],
            ),
            Paragraph("10", styles["TableCell"]),
        ],
        [
            Paragraph("10", styles["TableCellBold"]),
            Paragraph("Epilogue, Risk Disclosures & Scientific Citations", styles["TableCellBold"]),
            Paragraph(
                "The QuantOS Manifesto, formal boundary disclaimers, and academic bibliography",
                styles["TableCell"],
            ),
            Paragraph("11", styles["TableCell"]),
        ],
    ]
    toc_table = Table(toc_data, colWidths=[30 * pt, 165 * pt, 276 * pt, 36 * pt])
    toc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
            ]
        )
    )
    story.append(toc_table)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "The Moonshot Thesis: Engineering Incorruptible Alpha", styles["SubSectionHeader"]
        )
    )
    story.append(
        Paragraph(
            "Quantitative finance is currently paralyzed by an unacknowledged epistemological failure. Decades of low-interest rates "
            "and computational democratization produced thousands of quantitative asset managers advertising backtested Sharpe ratios "
            "exceeding 2.5. Yet, upon live capital allocation, these strategies uniformly deteriorate. "
            "This breakdown is not bad luck; it is mathematical inevitability. When a research team tests 1,000 statistical hypotheses "
            "on historical financial series, standard t-statistics are entirely invalidated. In statistical physics, testing multiple "
            "configurations requires Bonferroni or False Discovery Rate (FDR) corrections. In finance, it has traditionally been ignored.",
            styles["WhitepaperBody"],
        )
    )
    story.append(
        Paragraph(
            "<b>QuantOS was born to solve this structural failure.</b> Rather than treating risk management and statistical verification "
            "as post-hoc reporting checks, QuantOS compiles governance into the execution substrate itself. In QuantOS, every backtest, "
            "data point, feature row, and model fit is permanently tied to an immutable cryptographic manifest. The platform computes "
            "family-wise trial multiplicity in real time, adjusting promotion gates so that as more searches are attempted, the statistical "
            "hurdle increases logarithmically. <i>If a strategy cannot withstand institutional friction and rigorous statistical deflation, "
            "it cannot run.</i>",
            styles["WhitepaperBody"],
        )
    )

    thesis_box = [
        Paragraph(
            "<b>CORE PRINCIPLE : SCIENTIFIC HONESTY AS A COMPETITIVE ADVANTAGE</b>",
            styles["WhitepaperBodyBold"],
        ),
        Paragraph(
            "Most platforms maximize user satisfaction by delivering green equity curves. QuantOS maximizes allocator longevity "
            "by aggressively seeking disproof. By validating failures before live capital is committed, QuantOS turns the scientific method "
            "into a durable financial moat.",
            styles["WhitepaperBody"],
        ),
    ]
    story.append(
        build_card(thesis_box, bg_color=BG_LIGHT_BLUE, border_color=SECONDARY_BLUE, padding=7)
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 3: THE QUANT CRISIS & FIVE INVARIANTS
    # ==========================================
    story.append(Paragraph("SECTION 2 : ARCHITECTURAL INVARIANTS", styles["DocSuperTitle"]))
    story.append(
        Paragraph("The Quant Reproducibility Crisis & The Five Invariants", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "Modern algorithmic trading engines suffer from five pervasive structural vulnerabilities that invalidate theoretical research. "
            "QuantOS resolves each vulnerability with an unyielding architectural invariant enforced at the compiler and runtime levels:",
            styles["WhitepaperBody"],
        )
    )

    invariants_data = [
        [
            Paragraph("<b>Invariant</b>", styles["TableHead"]),
            Paragraph("<b>Industry Failure Mode (The Crisis)</b>", styles["TableHead"]),
            Paragraph("<b>QuantOS Architectural Guarantee</b>", styles["TableHead"]),
        ],
        [
            Paragraph("<b>1. Exact Decimal Accounting</b>", styles["TableCellBold"]),
            Paragraph(
                "Standard systems use IEEE-754 64-bit floating point. Rounding drift accumulates across thousands of fills, misstating cash balances, margins, and cost drag by pennies that compound into massive ledger divergence.",
                styles["TableCell"],
            ),
            Paragraph(
                "Every transaction, fee, slippage, and portfolio ledger balance is computed using arbitrary-precision <code>Decimal</code> fixed-point mathematics. Zero floating-point penny leaks.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>2. Strict Pre-Trade Risk Governor</b>", styles["TableCellBold"]),
            Paragraph(
                "Strategy algorithms possess direct broker pipes. Algorithmic bugs, stale market data, or aberrant loops cause flash crashes, broker margin breaches, and total account liquidations.",
                styles["TableCell"],
            ),
            Paragraph(
                "All trade proposals must receive cryptographically verified approval from the <code>PreTradeRiskGovernor</code> before reaching execution. Enforces leverage, drawdown, and circuit breakers.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>3. Zero-Lookahead State Engine</b>", styles["TableCellBold"]),
            Paragraph(
                "Backtesters calculate indicators using the current bar's close price and fill the order at the current bar's close (or open), creating impossible retroactive execution that guarantees backtest profitability.",
                styles["TableCell"],
            ),
            Paragraph(
                "Hardware-level state machine constraint: signals calculated on bar <i>t</i> close strictly execute no earlier than bar <i>t+1</i> open. Same-bar fills are structurally impossible.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>4. Multiplicity & Deflated Sharpe</b>", styles["TableCellBold"]),
            Paragraph(
                "Researchers test hundreds of factor combinations (p-hacking). Only the lucky survivor is published, concealing the vast graveyard of failed attempts that generated the false positive.",
                styles["TableCell"],
            ),
            Paragraph(
                "Every training session and parameter sweep immutably logs to the <code>EvidenceStore</code>. The Deflated Sharpe Ratio (DSR) discounts performance against the entire historical trial count.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>5. Fail-Closed Point-in-Time Data</b>", styles["TableCellBold"]),
            Paragraph(
                "Data feeds silently adjust past bars for splits, dividends, or survivorship bias without timestamp authority, or fall back to synthetic approximations when servers disconnect.",
                styles["TableCell"],
            ),
            Paragraph(
                "Point-in-time corporate action authorities enforce exact historical availability. Ingestions fail closed upon network or schema errors; synthetic mock fallback is strictly forbidden.",
                styles["TableCell"],
            ),
        ],
    ]

    inv_table = Table(invariants_data, colWidths=[110 * pt, 195 * pt, 190 * pt])
    inv_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
            ]
        )
    )
    story.append(inv_table)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Friction Accounting: The Brutal Reality of Indian Exchange Trading",
            styles["SubSectionHeader"],
        )
    )
    story.append(
        Paragraph(
            "QuantOS models the complete, dated statutory friction schedule mandated by the Securities and Exchange Board of India (SEBI), "
            "the National Stock Exchange (NSE), and the Ministry of Finance. For cash equity delivery in India, statutory and market costs "
            "total approximately <b>0.224% per round trip</b>:",
            styles["WhitepaperBody"],
        )
    )

    costs_data = [
        [
            Paragraph("<b>Cost Component</b>", styles["TableHead"]),
            Paragraph("<b>Statutory Authority / Basis</b>", styles["TableHead"]),
            Paragraph("<b>Buy Side Rate</b>", styles["TableHead"]),
            Paragraph("<b>Sell Side Rate</b>", styles["TableHead"]),
            Paragraph("<b>Round-Trip Impact</b>", styles["TableHead"]),
        ],
        [
            Paragraph("Securities Transaction Tax (STT)", styles["TableCellBold"]),
            Paragraph("Finance Act (Government of India)", styles["TableCell"]),
            Paragraph("0.100%", styles["TableCell"]),
            Paragraph("0.100%", styles["TableCell"]),
            Paragraph("0.2000% (Delivery)", styles["TableCell"]),
        ],
        [
            Paragraph("NSE Exchange Turnover Fee", styles["TableCellBold"]),
            Paragraph("National Stock Exchange of India", styles["TableCell"]),
            Paragraph("0.00297%", styles["TableCell"]),
            Paragraph("0.00297%", styles["TableCell"]),
            Paragraph("0.00594%", styles["TableCell"]),
        ],
        [
            Paragraph("Goods & Services Tax (GST)", styles["TableCellBold"]),
            Paragraph("Central GST + State GST (18%)", styles["TableCell"]),
            Paragraph("18% on Brokerage+Turnover", styles["TableCell"]),
            Paragraph("18% on Brokerage+Turnover", styles["TableCell"]),
            Paragraph("~0.00160%", styles["TableCell"]),
        ],
        [
            Paragraph("SEBI Regulatory Turnover Fee", styles["TableCellBold"]),
            Paragraph("SEBI (Regulatory Fee Schedule)", styles["TableCell"]),
            Paragraph("Rs. 10 per crore (0.0001%)", styles["TableCell"]),
            Paragraph("Rs. 10 per crore (0.0001%)", styles["TableCell"]),
            Paragraph("0.00020%", styles["TableCell"]),
        ],
        [
            Paragraph("Stamp Duty", styles["TableCellBold"]),
            Paragraph("Indian Stamp Act (Revenue Dept)", styles["TableCell"]),
            Paragraph("0.0150% (Buy only)", styles["TableCell"]),
            Paragraph("0.0000%", styles["TableCell"]),
            Paragraph("0.01500%", styles["TableCell"]),
        ],
        [
            Paragraph("Bid-Ask Spread & Model Slippage", styles["TableCellBold"]),
            Paragraph("Empirical Liquidity Curve (Tier 1)", styles["TableCell"]),
            Paragraph("0.0010%", styles["TableCell"]),
            Paragraph("0.0010%", styles["TableCell"]),
            Paragraph("0.00200%", styles["TableCell"]),
        ],
        [
            Paragraph("<b>Total Modeled Friction</b>", styles["TableCellBold"]),
            Paragraph("<b>Exact Decimal Summation</b>", styles["TableCellBold"]),
            Paragraph("<b>0.1191%</b>", styles["TableCellBold"]),
            Paragraph("<b>0.1051%</b>", styles["TableCellBold"]),
            Paragraph("<b>~0.2247% Round Trip</b>", styles["TableCellBold"]),
        ],
    ]
    cost_table = Table(costs_data, colWidths=[120 * pt, 140 * pt, 75 * pt, 75 * pt, 85 * pt])
    cost_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, -1), (-1, -1), BG_LIGHT_BLUE),
            ]
        )
    )
    story.append(cost_table)

    story.append(PageBreak())

    # ==========================================
    # PAGE 4: SYSTEM ARCHITECTURE & TOPOLOGY
    # ==========================================
    story.append(Paragraph("SECTION 3 : SYSTEM ARCHITECTURE", styles["DocSuperTitle"]))
    story.append(
        Paragraph("Modular Monolith Architecture & Execution Pipeline", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "QuantOS rejects fragile distributed microservice setups in favor of a high-performance <b>Modular Monolith</b>. "
            "All domain modules communicate through strongly-typed, immutable interfaces with zero cyclic dependencies. "
            "Heavy computation (backtesting, model optimization, market data fetching) is offloaded to supervised worker processes "
            "governed by heartbeat leases and atomic state recovery.",
            styles["WhitepaperBody"],
        )
    )

    # Architecture Topology Visual Representation Table
    topo_data = [
        [
            Paragraph("<b>Pipeline Stage</b>", styles["TableHead"]),
            Paragraph("<b>Subsystem & Module</b>", styles["TableHead"]),
            Paragraph("<b>Operational Mechanics & Core Invariants</b>", styles["TableHead"]),
        ],
        [
            Paragraph("<b>1. Ingestion & Authority</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.data</code><br/>Upstox V3 & Historical Engine",
                styles["TableCell"],
            ),
            Paragraph(
                "Pulls tick/1m/daily bars. Validates continuous session calendar against official NSE exchange dates. Enforces provenance hashes and point-in-time corporate action adjustments.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>2. Feature & Dataset Kernel</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.modeling</code><br/>Canonical Window Kernel (v2)",
                styles["TableCell"],
            ),
            Paragraph(
                "Computes feature vectors strictly consuming trailing 21 point-in-time bars. Enforces schema consistency across training and shadow execution to prevent feature divergence.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>3. Alpha & Multi-Model Fusion</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.alpha</code><br/>Technical, Greeks & AI Consensus",
                styles["TableCell"],
            ),
            Paragraph(
                "Calculates Black-Scholes Greeks, Implied Volatility surfaces, momentum vectors, and interfaces with multi-agent LLM advisors for qualitative regime filters.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>4. Sizing & Capital Allocation</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.portfolio</code><br/>Volatility Parity & Half-Kelly",
                styles["TableCell"],
            ),
            Paragraph(
                "Translates raw alpha scores into exact target portfolio weights. Rebalances allocations using Volatility Parity and Fractional Kelly to optimize compound growth while capping tail ruin.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>5. Pre-Trade Risk Governor</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.risk</code><br/>PreTradeRiskGovernor", styles["TableCell"]
            ),
            Paragraph(
                "The gatekeeper. Evaluates proposed order vectors against maximum drawdown limits, intraday loss caps, concentration limits, and bid-ask spread circuit breakers.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>6. Deterministic Execution</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.backtest</code><br/><code>quant_system.execution</code>",
                styles["TableCell"],
            ),
            Paragraph(
                "Simulates order state transitions. Fills buy/sell orders at bar <i>t+1</i> open. Applies statutory friction and slippage. In shadow mode, submits zero broker orders (T4 invariant).",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>7. Immutable Evidence Vault</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.evidence</code><br/>Content-Addressed Store",
                styles["TableCell"],
            ),
            Paragraph(
                "Serializes models, execution logs, and tearsheets into SHA-256 content-addressed immutable files. Enforces crash-recovery integrity and independent clean-clone verification.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>8. Presentation & Studio UI</b>", styles["TableCellBold"]),
            Paragraph(
                "<code>quant_system.server</code><br/>FastAPI & Realtime Dashboard",
                styles["TableCell"],
            ),
            Paragraph(
                "Exposes strict <code>/api/v1</code> endpoints, streaming real-time paper pilot telemetry, live risk cards, backtest visualizers, and system auto-diagnostics over local WebSockets.",
                styles["TableCell"],
            ),
        ],
    ]

    topo_table = Table(topo_data, colWidths=[100 * pt, 130 * pt, 265 * pt])
    topo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
            ]
        )
    )
    story.append(topo_table)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph("Supervised Worker Hierarchy & Crash Invariants", styles["SubSectionHeader"])
    )
    story.append(
        Paragraph(
            "To ensure that long-running backtest sweeps or high-frequency shadow sessions cannot destabilize the system, "
            "QuantOS employs an isolated worker supervisor. Workers operate under atomic file-lock leases. "
            "If a background worker terminates abnormally, the supervisor identifies the PID termination, triggers clean recovery, "
            "and quarantines uncommitted artifacts without corrupting the canonical evidence catalog.",
            styles["WhitepaperBody"],
        )
    )

    worker_box = [
        Paragraph(
            "<b>ISOLATION CONTRACT : DETERMINISTIC MULTI-PROCESS BOUNDARY</b>",
            styles["WhitepaperBodyBold"],
        ),
        Paragraph(
            "• <b>Zero Shared Memory Leaks:</b> Workers exchange immutable JSON-schema messages across stdin/stdout or isolated SQLite ledgers.<br/>"
            "• <b>Pre-Allocation Verification:</b> System memory, disk space, and process handles are pre-checked before intensive runs.<br/>"
            "• <b>Independent Verification Pass:</b> Slices 1 through 3 and governed execution were independently certified by detached Red Team verifiers.",
            styles["WhitepaperBody"],
        ),
    ]
    story.append(
        build_card(worker_box, bg_color=BG_LIGHT_BLUE, border_color=SECONDARY_BLUE, padding=6)
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 5: THE EMPIRICAL GROUND TRUTH (101 TRIALS)
    # ==========================================
    story.append(Paragraph("SECTION 4 : EMPIRICAL DISCOVERY", styles["DocSuperTitle"]))
    story.append(
        Paragraph("The Empirical Ground Truth : 101 Governed Trials", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "In quantitative finance, the ultimate test of integrity is whether a research platform tells its creators the truth. "
            "QuantOS underwent an exhaustive, governed empirical study across the <b>NIFTY 50</b> constituents over a multi-year window, "
            "followed by an expanded <b>423-name liquid research universe</b> (10-year history, turnover > Rs. 5 Crore). "
            "The candidate model was a 6-feature regularized Ridge Classifier with purged and embargoed training folds.",
            styles["WhitepaperBody"],
        )
    )

    # Empirical Results Table
    emp_data = [
        [
            Paragraph("<b>Campaign Parameter / Metric</b>", styles["TableHead"]),
            Paragraph("<b>v1 Campaign (Window-Dep.)</b>", styles["TableHead"]),
            Paragraph("<b>v2 Campaign (Canonical Window)</b>", styles["TableHead"]),
            Paragraph("<b>Expanded 423-Name Universe</b>", styles["TableHead"]),
        ],
        [
            Paragraph("Evaluated Instrument Universe", styles["TableCellBold"]),
            Paragraph("NIFTY 50 Constituents", styles["TableCell"]),
            Paragraph("NIFTY 50 Constituents", styles["TableCell"]),
            Paragraph("423 Liquid NSE Names", styles["TableCell"]),
        ],
        [
            Paragraph("Total Governed Trials Logged", styles["TableCellBold"]),
            Paragraph("51 trials (1 per name)", styles["TableCell"]),
            Paragraph("50 trials (1 per name)", styles["TableCell"]),
            Paragraph("Screened across 423 names", styles["TableCell"]),
        ],
        [
            Paragraph("Published Predictive Models", styles["TableCellBold"]),
            Paragraph("40 models (10 degenerate)", styles["TableCell"]),
            Paragraph("50 models (0 degenerate)", styles["TableCell"]),
            Paragraph("Pooled cross-sectional ranking", styles["TableCell"]),
        ],
        [
            Paragraph("Positive Raw Sharpe Ratios", styles["TableCellBold"]),
            Paragraph("14 of 40 (35.0%)", styles["TableCell"]),
            Paragraph("21 of 50 (42.0%)", styles["TableCell"]),
            Paragraph("Sharpe +0.12 (Hold 21)", styles["TableCell"]),
        ],
        [
            Paragraph("Median Sharpe Across Universe", styles["TableCellBold"]),
            Paragraph("-1.1791 (Loss)", styles["TableCell"]),
            Paragraph("-0.2278 (Loss)", styles["TableCell"]),
            Paragraph("-0.4520 (Loss)", styles["TableCell"]),
        ],
        [
            Paragraph("Best Strategy Raw Sharpe", styles["TableCellBold"]),
            Paragraph("+4.3143 (GRASIM, 9 trades)", styles["TableCell"]),
            Paragraph("+3.2207 (GRASIM)", styles["TableCell"]),
            Paragraph("+0.76 (Hold 21, Top 10)", styles["TableCell"]),
        ],
        [
            Paragraph("<b>Best Campaign Deflated Sharpe (DSR)</b>", styles["TableCellBold"]),
            Paragraph("<b>0.3978 (Required: 0.9500)</b>", styles["TableCellBold"]),
            Paragraph("<b>0.2177 (Required: 0.9500)</b>", styles["TableCellBold"]),
            Paragraph("<b>0.0841 (Vanished with data)</b>", styles["TableCellBold"]),
        ],
        [
            Paragraph("<b>Promotion Gate Verdict</b>", styles["TableCellBold"]),
            Paragraph(
                "<font color='#B91C1C'><b>NONE PROMOTABLE</b></font>", styles["TableCellBold"]
            ),
            Paragraph(
                "<font color='#B91C1C'><b>NONE PROMOTABLE</b></font>", styles["TableCellBold"]
            ),
            Paragraph(
                "<font color='#B91C1C'><b>NONE PROMOTABLE</b></font>", styles["TableCellBold"]
            ),
        ],
    ]
    emp_table = Table(emp_data, colWidths=[145 * pt, 115 * pt, 115 * pt, 120 * pt])
    emp_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF2F2")),
            ]
        )
    )
    story.append(emp_table)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Post-Mortem Analysis : Why This Result is QuantOS's Greatest Victory",
            styles["SubSectionHeader"],
        )
    )
    story.append(
        Paragraph(
            "To an untrained observer, a campaign ending in <b>NONE PROMOTABLE</b> appears to be a failure. "
            "To institutional allocators and serious quantitative scientists, <b>it is the ultimate proof of system integrity.</b> "
            "Here is what the empirical evidence revealed:",
            styles["WhitepaperBody"],
        )
    )
    story.append(
        Paragraph(
            "1. <b>Friction Eats Naive Technical Alpha:</b> The six technical features (RSI, ATR, SMA distances) produced positive raw gross "
            "signals on certain names. However, after charging the exact 0.224% NSE round-trip friction, net returns turned uniformly negative. "
            "Naive technical indicators do not carry sufficient edge to overcome statutory exchange friction.",
            styles["WhitepaperBody"],
        )
    )
    story.append(
        Paragraph(
            "2. <b>The Deflated Sharpe Shield:</b> Under naive reporting, GRASIM's raw Sharpe of +4.31 would have been touted to investors "
            "as an exceptional breakthrough. But QuantOS's multiplicity engine noted that GRASIM achieved that Sharpe on only 9 trades, "
            "and deflated the score against the 51 search trials conducted. The resulting DSR of <b>0.3978</b> fell far short of the 0.95 "
            "promotion threshold, stopping a live-money deployment that would have lost capital.",
            styles["WhitepaperBody"],
        )
    )
    story.append(
        Paragraph(
            "3. <b>Corporate Action Traps Uncovered:</b> In unadjusted data, demergers (such as the <b>HEG</b> spin-off quoted -64.3% overnight) "
            "and 10:1 stock splits (TATASTEEL) appear to naive models as massive +900% returns or catastrophic crashes. "
            "QuantOS built the Corporate Action Authority to detect provider gaps, preventing corrupted rows from manufacturing fake signals.",
            styles["WhitepaperBody"],
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 6: MATHEMATICAL GOVERNANCE & DSR
    # ==========================================
    story.append(Paragraph("SECTION 5 : MATHEMATICAL FORMULATIONS", styles["DocSuperTitle"]))
    story.append(
        Paragraph("Statistical Governance Engine & Deflated Sharpe Ratio", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "The mathematical core of QuantOS implements the <b>Deflated Sharpe Ratio (DSR)</b> formulated by David Bailey and "
            "Marcos López de Prado (2014). DSR addresses the reality that the expected maximum Sharpe ratio of <i>K</i> independent "
            "trials is strictly greater than zero, even if the underlying true Sharpe ratio is identically zero.",
            styles["WhitepaperBody"],
        )
    )

    # Mathematical Box
    dsr_math_box = [
        Paragraph(
            "<b>THE MATHEMATICAL FORMULATION OF DEFLATED SHARPE (DSR)</b>",
            styles["WhitepaperBodyBold"],
        ),
        Paragraph(
            "<b>1. Expected Maximum Sharpe Ratio Under the Null Hypothesis:</b><br/>"
            "Given <i>K</i> trials with variance <i>V</i>[{<i>SR</i><sub><i>k</i></sub>}], the expected maximum Sharpe ratio <i>E</i>[max<sub><i>k</i></sub> <i>SR</i><sub><i>k</i></sub>] is approximated by:",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>E[max(SR)] &approx; &radic;(2 ln K) &middot; &sigma;<sub>SR</sub> + "
            "(1 - &gamma;) / &radic;(2 ln K) &middot; &sigma;<sub>SR</sub></b>",
            styles["FormulaText"],
        ),
        Paragraph(
            "where &gamma; &approx; 0.5772156649 (Euler-Mascheroni constant) and &sigma;<sub>SR</sub> is the standard deviation of trial Sharpes.",
            styles["WhitepaperBody"],
        ),
        Spacer(1, 4),
        Paragraph(
            "<b>2. Deflated Sharpe Ratio Probability Transformation:</b><br/>"
            "The probability that an observed Sharpe ratio <i>SR</i> exceeds the selection benchmark <i>SR</i><sup>*</sup>, taking into account "
            "skewness (&gamma;<sub>3</sub>), kurtosis (&gamma;<sub>4</sub>), and sample length <i>N</i>:",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>DSR = &Phi;( [ (SR - SR*) &radic;(N - 1) ] / "
            "&radic;[ 1 - &gamma;<sub>3</sub> &middot; SR + ( (&gamma;<sub>4</sub> - 1) / 4 ) &middot; SR<sup>2</sup> ] )</b>",
            styles["FormulaText"],
        ),
        Paragraph(
            "where &Phi;(&middot;) is the standard normal cumulative distribution function (CDF).",
            styles["WhitepaperBody"],
        ),
        Spacer(1, 4),
        Paragraph(
            "<b>3. Floating-Point Moment Guard (The 64 &times; &epsilon; Boundary Invariant):</b><br/>"
            "For two-point discrete distributions, the algebraic identity &gamma;<sub>4</sub> - &gamma;<sub>3</sub><sup>2</sup> = 1 holds exactly. "
            "In IEEE-754 arithmetic, float residue causes false rejections. QuantOS enforces a numerical boundary check:<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>if kurtosis &lt; (skewness**2 + 1.0) - (64 * sys.float_info.epsilon): raise MomentConstraintInvalid</code>",
            styles["WhitepaperBody"],
        ),
    ]
    story.append(
        build_card(dsr_math_box, bg_color=BG_CARD_LIGHT, border_color=PRIMARY_NAVY, padding=8)
    )
    story.append(Spacer(1, 10))

    story.append(
        Paragraph("Purged and Embargoed Cross-Validation Engine", styles["SubSectionHeader"])
    )
    story.append(
        Paragraph(
            "Standard k-fold cross-validation fails in time-series finance because labels overlap in time, creating severe information "
            "leakage between training and testing sets. QuantOS implements <b>Combinatorial Purged and Embargoed Cross-Validation (CPCV)</b>:",
            styles["WhitepaperBody"],
        )
    )

    cv_data = [
        [
            Paragraph("<b>Validation Technique</b>", styles["TableHead"]),
            Paragraph("<b>Standard Industry Practice (Flawed)</b>", styles["TableHead"]),
            Paragraph("<b>QuantOS Governed Implementation</b>", styles["TableHead"]),
        ],
        [
            Paragraph("<b>Purging Mechanism</b>", styles["TableCellBold"]),
            Paragraph(
                "Randomly shuffles daily bars across folds, leaking future price information directly into training data.",
                styles["TableCell"],
            ),
            Paragraph(
                "Removes all training observations whose label horizon overlaps with the validation evaluation window. Zero lookahead.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Embargo Period</b>", styles["TableCellBold"]),
            Paragraph(
                "Begins testing immediately on the day after the training set ends, capturing serial auto-correlation.",
                styles["TableCell"],
            ),
            Paragraph(
                "Enforces a mandatory 2 to 5-session embargo buffer after validation windows to account for market memory and auto-regressive decay.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Next-Open Labeling</b>", styles["TableCellBold"]),
            Paragraph(
                "Measures returns from bar <i>t</i> close to bar <i>t+n</i> close, ignoring execution mechanics.",
                styles["TableCell"],
            ),
            Paragraph(
                "Labels are formed strictly from bar <i>t+1</i> open to bar <i>t+n+1</i> open, net of the exact 0.224% dated statutory cost.",
                styles["TableCell"],
            ),
        ],
    ]
    cv_table = Table(cv_data, colWidths=[110 * pt, 190 * pt, 195 * pt])
    cv_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
            ]
        )
    )
    story.append(cv_table)

    story.append(PageBreak())

    # ==========================================
    # PAGE 7: SUBSYSTEMS & SOFTWARE CRAFTSMANSHIP
    # ==========================================
    story.append(Paragraph("SECTION 6 : PLATFORM IMPLEMENTATION", styles["DocSuperTitle"]))
    story.append(
        Paragraph("Subsystems Breakdown & Software Craftsmanship", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "QuantOS is engineered to the highest standards of systems programming. The repository comprises over 200 strictly-typed "
            "Python source modules verified under 100% clean test-craft invariants. The 10 core subsystems operate as follows:",
            styles["WhitepaperBody"],
        )
    )

    sub_data = [
        [
            Paragraph("<b>Subsystem</b>", styles["TableHead"]),
            Paragraph("<b>Package Path</b>", styles["TableHead"]),
            Paragraph("<b>Institutional Purpose & Design Contract</b>", styles["TableHead"]),
        ],
        [
            Paragraph("Core Primitives", styles["TableCellBold"]),
            Paragraph("<code>quant_system.core</code>", styles["TableCell"]),
            Paragraph(
                "Immutable domain dataclasses: <code>Tick</code>, <code>PointInTimeBar</code>, <code>Order</code>, <code>Fill</code>, and arbitrary-precision <code>Decimal</code> financial ledgers.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Market Data Engine", styles["TableCellBold"]),
            Paragraph("<code>quant_system.data</code>", styles["TableCell"]),
            Paragraph(
                "Upstox V3 API client, multi-timeframe aggregators, option chain readers, synthetic data generators, and corporate action authorities.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Feature Kernel", styles["TableCellBold"]),
            Paragraph("<code>quant_system.modeling</code>", styles["TableCell"]),
            Paragraph(
                "Canonical Feature Window (v2) enforcing trailing-21 bar inputs, z-score normalizers, purged fold builders, and model cards.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Alpha Generators", styles["TableCellBold"]),
            Paragraph("<code>quant_system.alpha</code>", styles["TableCell"]),
            Paragraph(
                "Technical momentum/volatility, Black-Scholes Greeks (&Delta;, &Gamma;, &Theta;, Vega, Rho), Implied Volatility (IV) surface solvers, and LLM consensus.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Strategy Engine", styles["TableCellBold"]),
            Paragraph("<code>quant_system.strategies</code>", styles["TableCell"]),
            Paragraph(
                "Base strategy protocol, Equity Momentum, NIFTY 09:20 Intraday Straddles, Governed Ridge Adapters, and Directional Options Spreads.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Portfolio Allocation", styles["TableCellBold"]),
            Paragraph("<code>quant_system.portfolio</code>", styles["TableCell"]),
            Paragraph(
                "Position sizing models: Fixed Fractional, Volatility Parity, Half-Kelly, and Mean-Variance Risk-Parity optimization engines.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Pre-Trade Risk", styles["TableCellBold"]),
            Paragraph("<code>quant_system.risk</code>", styles["TableCell"]),
            Paragraph(
                "<code>PreTradeRiskGovernor</code> enforcing leverage bounds, concentration limits, maximum drawdown halts, and circuit breaker kill-switches.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Backtest Engine", styles["TableCellBold"]),
            Paragraph("<code>quant_system.backtest</code>", styles["TableCell"]),
            Paragraph(
                "Event-driven execution engine with zero lookahead, next-bar open fills, and realistic statutory friction models.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Analytics & Audit", styles["TableCellBold"]),
            Paragraph("<code>quant_system.analytics</code>", styles["TableCell"]),
            Paragraph(
                "Tearsheet generator, Sharpe/Sortino/Calmar metrics, Monte Carlo simulations, and Bailey & López de Prado Deflated Sharpe ratio.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Server & Studio UI", styles["TableCellBold"]),
            Paragraph("<code>quant_system.server</code>", styles["TableCell"]),
            Paragraph(
                "FastAPI REST backend, WebSocket real-time telemetry, paper trading pilot supervisor, and interactive desktop HTML5 dashboard.",
                styles["TableCell"],
            ),
        ],
    ]
    sub_table = Table(sub_data, colWidths=[95 * pt, 120 * pt, 280 * pt])
    sub_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
            ]
        )
    )
    story.append(sub_table)
    story.append(Spacer(1, 8))

    story.append(
        Paragraph("Verification Matrix & Static Quality Gates", styles["SubSectionHeader"])
    )
    story.append(
        Paragraph(
            "QuantOS code quality is continuously measured by strict, automated regression suites:",
            styles["WhitepaperBody"],
        )
    )

    gates_data = [
        [
            Paragraph("<b>Quality Gate</b>", styles["TableHead"]),
            Paragraph("<b>Scope / Command</b>", styles["TableHead"]),
            Paragraph("<b>Verified Baseline Status</b>", styles["TableHead"]),
        ],
        [
            Paragraph("Automated Test Suite", styles["TableCellBold"]),
            Paragraph("<code>pytest tests/ -q</code> (Forwards & Reverse)", styles["TableCell"]),
            Paragraph("<b>1,519 passing tests</b> at 100% pass rate", styles["TableCellBold"]),
        ],
        [
            Paragraph("Strict Static Typing", styles["TableCellBold"]),
            Paragraph("<code>mypy src launcher.py scripts</code>", styles["TableCell"]),
            Paragraph(
                "<b>Success</b> across 208 strictly-typed source files", styles["TableCellBold"]
            ),
        ],
        [
            Paragraph("Code Formatting & Lints", styles["TableCellBold"]),
            Paragraph(
                "<code>ruff check .</code> & <code>ruff format --check .</code>",
                styles["TableCell"],
            ),
            Paragraph("<b>Clean</b> across 671 files (0 errors)", styles["TableCellBold"]),
        ],
        [
            Paragraph("Test-Craft Integrity", styles["TableCellBold"]),
            Paragraph("<code>scripts/check-tests-craft.py</code>", styles["TableCell"]),
            Paragraph(
                "<b>100% clean:</b> 0 sleep calls, 0 unannotated loops", styles["TableCellBold"]
            ),
        ],
        [
            Paragraph("Security & Secret Scan", styles["TableCellBold"]),
            Paragraph("<code>scripts/scan-application-secrets.py</code>", styles["TableCell"]),
            Paragraph(
                "<b>0 findings</b> (Zero API keys or credentials exposed)", styles["TableCellBold"]
            ),
        ],
    ]
    gates_table = Table(gates_data, colWidths=[120 * pt, 190 * pt, 185 * pt])
    gates_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
            ]
        )
    )
    story.append(gates_table)

    story.append(PageBreak())

    # ==========================================
    # PAGE 8: 5-YEAR MOONSHOT - PILLARS 1 & 2
    # ==========================================
    story.append(
        Paragraph("SECTION 7 : STRATEGIC MOONSHOT ROADMAP (PART I)", styles["DocSuperTitle"])
    )
    story.append(Paragraph("The 5-Year Horizon : Pillars 1 & 2", styles["SectionHeader"]))
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "The long-range vision for QuantOS transcends local research. Over the next five years, QuantOS is scheduled to evolve "
            "into a fully autonomous, institutional quantitative fund operating system across four transformative pillars:",
            styles["WhitepaperBody"],
        )
    )

    # Pillar 1 Card
    p1_content = [
        Paragraph("PILLAR 1 : AUTONOMOUS MULTI-AGENT AI ALPHA SWARMS", styles["TeaserHeadline"]),
        Paragraph(
            "<b>The Moonshot Vision:</b> Transitioning quantitative research from manual human hypothesis testing to 24/7 autonomous "
            "AI agent swarms that continuously read academic papers, formulate mathematical signals, synthesize features, and stress-test models.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Architectural Hierarchy:</b><br/>"
            "• <b>Hypothesis Synthesizer:</b> Scans arXiv quantitative finance preprints, company conference call transcripts, and macroeconomic feeds to propose new alpha equations.<br/>"
            "• <b>Feature Engineer Agent:</b> Implements vector-based feature kernels within the canonical schema, verifying absence of lookahead.<br/>"
            "• <b>Red Team Adversary Agent:</b> Subject newly proposed models to adversarial stress testing (liquidity drought simulation, synthetic volatility spikes, regime shifts) to force failure.<br/>"
            "• <b>Governance Gatekeeper Agent:</b> Formally evaluates candidate models against the immutable Deflated Sharpe Ratio (DSR) threshold before human sign-off.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Institutional Invariant:</b> No agent can promote a model directly. All agents must submit cryptographic evidence to the "
            "immutable vault, subject to the same strict multiplicity penalties as human researchers.",
            styles["WhitepaperBodyBold"],
        ),
    ]
    story.append(
        build_card(p1_content, bg_color=BG_CARD_LIGHT, border_color=SECONDARY_BLUE, padding=8)
    )
    story.append(Spacer(1, 10))

    # Pillar 2 Card
    p2_content = [
        Paragraph(
            "PILLAR 2 : ULTRA-LOW-LATENCY RUST/C++ EXECUTION & NSE CO-LOCATION",
            styles["TeaserHeadline"],
        ),
        Paragraph(
            "<b>The Moonshot Vision:</b> Migrating QuantOS's execution engine from Python into a sub-microsecond native C++20 / Rust core, "
            "deployed directly in the <b>National Stock Exchange (NSE) Colocation Facility at BKC, Mumbai</b>.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Technical Specifications:</b><br/>"
            "• <b>Tick-to-Trade Latency Target:</b> &lt; 5 microseconds from Level 3 (L3) tick packet arrival to outbound order dispatch.<br/>"
            "• <b>Hardware Acceleration:</b> FPGA-based packet parsing (Solarflare / AMD Xilinx) for full NSE Multicast Tick By Tick (TBT) feeds.<br/>"
            "• <b>Lock-Free Order State Machine:</b> Ring-buffer concurrency in Rust guaranteeing zero heap allocation during active trading sessions.<br/>"
            "• <b>Deterministic L3 Queue Simulation:</b> High-fidelity historical order-book replay modeling queue priority, cancel cascades, and market-maker inventory depletion.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Institutional Invariant:</b> Python remains the research, modeling, and strategic interface; the Rust execution core enforces the "
            "exact same Decimal ledger rules and Pre-Trade Risk Governor limits in native hardware.",
            styles["WhitepaperBodyBold"],
        ),
    ]
    story.append(
        build_card(p2_content, bg_color=BG_CARD_LIGHT, border_color=PRIMARY_NAVY, padding=8)
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 9: 5-YEAR MOONSHOT - PILLARS 3 & 4
    # ==========================================
    story.append(
        Paragraph("SECTION 8 : STRATEGIC MOONSHOT ROADMAP (PART II)", styles["DocSuperTitle"])
    )
    story.append(Paragraph("The 5-Year Horizon : Pillars 3 & 4", styles["SectionHeader"]))
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    # Pillar 3 Card
    p3_content = [
        Paragraph(
            "PILLAR 3 : GLOBAL MULTI-ASSET EXPANSION & CROSS-MARKET ARBITRAGE",
            styles["TeaserHeadline"],
        ),
        Paragraph(
            "<b>The Moonshot Vision:</b> Expanding QuantOS beyond Indian equity and derivatives markets into a comprehensive multi-asset, "
            "global quantitative macro platform covering US Equities, Global FX, Commodities, and Crypto assets.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Asset Class Horizons:</b><br/>"
            "• <b>US Equities & Options:</b> Integration with Interactive Brokers, Alpaca, and Polygon.io with full SEC Section 31 and FINRA TAF fee modeling.<br/>"
            "• <b>Multi-Currency FX & Rates:</b> Continuous 24/5 liquidity modeling across G10 currencies with dynamic interest rate differential carry models.<br/>"
            "• <b>Commodities (MCX & CME):</b> Crude Oil, Natural Gas, and Gold/Silver cross-market basis trading and storage cost modeling.<br/>"
            "• <b>Cross-Market Statistical Arbitrage:</b> Exploit lead-lag relationships between Indian ADRs (e.g., INFY, HDB) traded in New York and their underlying NSE shares in Mumbai.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Institutional Invariant:</b> Every newly onboarded exchange carries its own explicit, point-in-time statutory friction schedule "
            "and calendar authority. No generic assumptions.",
            styles["WhitepaperBodyBold"],
        ),
    ]
    story.append(
        build_card(p3_content, bg_color=BG_CARD_LIGHT, border_color=SECONDARY_BLUE, padding=8)
    )
    story.append(Spacer(1, 10))

    # Pillar 4 Card
    p4_content = [
        Paragraph(
            "PILLAR 4 : CAPITAL ALLOCATION FUND OS (DECENTRALIZED QUANT SANDBOX)",
            styles["TeaserHeadline"],
        ),
        Paragraph(
            "<b>The Moonshot Vision:</b> Transforming QuantOS into the definitive Operating System for Institutional Capital Allocation, "
            "enabling external quantitative researchers to deploy strategies into institutional capital pools under total cryptographic sandboxing.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Operating System Capabilities:</b><br/>"
            "• <b>Zero-Knowledge Strategy Sandboxing:</b> Independent quantitative developers deploy compiled alpha bytecode without revealing proprietary formulas.<br/>"
            "• <b>Dynamic Risk Budgeting:</b> An algorithmic allocator dynamically assigns capital to strategies based on live Deflated Sharpe degradation and real-time covariance shifts.<br/>"
            "• <b>Automated Watermark & P&L Ledgers:</b> Exact Decimal fee attribution (High-Water Marks, Hurdle Rates, Performance Fees) calculated to zero rounding drift.<br/>"
            "• <b>Global Kill-Switch Mesh:</b> The Master Risk Governor retains sub-millisecond authority to liquidate, throttle, or halt any tenant strategy that breaches systemic risk parameters.",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<b>Institutional Invariant:</b> Tenant strategies can never communicate directly with brokers. All orders pass through the unified "
            "Pre-Trade Risk Governor and Smart Order Router (SOR).",
            styles["WhitepaperBodyBold"],
        ),
    ]
    story.append(
        build_card(p4_content, bg_color=BG_CARD_LIGHT, border_color=PRIMARY_NAVY, padding=8)
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 10: INSTITUTIONAL ROADMAP & GATES
    # ==========================================
    story.append(Paragraph("SECTION 9 : EXECUTION MILESTONES", styles["DocSuperTitle"]))
    story.append(
        Paragraph("Institutional Phased Roadmap & Governance Gates", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    story.append(
        Paragraph(
            "QuantOS executes against a rigorous, multi-year chronological roadmap. Each phase is bound to mandatory "
            "verification gates that must pass clean independent Red Team adjudication before capital allocation expands:",
            styles["WhitepaperBody"],
        )
    )

    # Roadmap Milestone Table
    road_data = [
        [
            Paragraph("<b>Phase & Timeline</b>", styles["TableHead"]),
            Paragraph("<b>Strategic Objective</b>", styles["TableHead"]),
            Paragraph("<b>Core Deliverables & Verification Criteria</b>", styles["TableHead"]),
            Paragraph("<b>Status</b>", styles["TableHead"]),
        ],
        [
            Paragraph("<b>Phase I</b><br/>2026 Q3–Q4", styles["TableCellBold"]),
            Paragraph("Foundation & Scientific Governance", styles["TableCellBold"]),
            Paragraph(
                "• Implement 12 vertical release slices.<br/>• Exact Decimal ledger, Upstox V3 ingestion, and content-addressed evidence store.<br/>• Multiplicity accounting engine and Deflated Sharpe ratio implementation.<br/>• 1,519 repository unit/integration tests passing at 100%.",
                styles["TableCell"],
            ),
            Paragraph(
                "<font color='#047857'><b>COMPLETED<br/>(P5 RC READY)</b></font>",
                styles["TableCellBold"],
            ),
        ],
        [
            Paragraph("<b>Phase II</b><br/>2027 Q1–Q2", styles["TableCellBold"]),
            Paragraph("Cross-Sectional Alpha & Options Surface", styles["TableCellBold"]),
            Paragraph(
                "• Multi-instrument cross-sectional dataset contract.<br/>• Full Black-Scholes Greeks and Implied Volatility surface arbitrage models.<br/>• Corporate Action automated validation and demerger value-continuity engine.<br/>• Multi-agent LLM advisory consensus integration.",
                styles["TableCell"],
            ),
            Paragraph(
                "<font color='#1D4ED8'><b>ACTIVE<br/>DEVELOPMENT</b></font>",
                styles["TableCellBold"],
            ),
        ],
        [
            Paragraph("<b>Phase III</b><br/>2027 Q3–Q4", styles["TableCellBold"]),
            Paragraph("Microsecond Execution Core & Colo Pilot", styles["TableCellBold"]),
            Paragraph(
                "• Compile native C++20 / Rust order state machine.<br/>• Integrate Solarflare FPGA network cards for sub-5&mu;s tick processing.<br/>• Deploy pilot hardware in NSE BKC Mumbai co-location rack.<br/>• Launch verified Shadow Paper Trading across 1,000 live sessions.",
                styles["TableCell"],
            ),
            Paragraph(
                "<font color='#B45309'><b>ENGINEERING<br/>PLANNING</b></font>",
                styles["TableCellBold"],
            ),
        ],
        [
            Paragraph("<b>Phase IV</b><br/>2028", styles["TableCellBold"]),
            Paragraph("Multi-Asset Expansion & T4 Live Routing", styles["TableCellBold"]),
            Paragraph(
                "• Formal T4 compliance audit for institutional live-money broker routing.<br/>• Expand into US Equities (NYSE/NASDAQ) and MCX Commodities.<br/>• Cross-market lead-lag arbitrage between Indian ADRs and NSE stocks.<br/>• Dynamic portfolio covariance optimizer with real-time regime detection.",
                styles["TableCell"],
            ),
            Paragraph(
                "<font color='#64748B'><b>STRATEGIC<br/>HORIZON</b></font>", styles["TableCellBold"]
            ),
        ],
        [
            Paragraph("<b>Phase V</b><br/>2029–2030", styles["TableCellBold"]),
            Paragraph("Autonomous Multi-Agent Capital Fund OS", styles["TableCellBold"]),
            Paragraph(
                "• Launch decentralized quant sandbox with zero-knowledge alpha execution.<br/>• Full multi-agent AI research swarms generating and auditing live models.<br/>• Institutional scale: Managing Rs. 1,000+ Crore ($120M+ AUM) under automated risk bounds.<br/>• Real-time cryptographically auditable investor performance ledgers.",
                styles["TableCell"],
            ),
            Paragraph(
                "<font color='#64748B'><b>MOONSHOT<br/>TARGET</b></font>", styles["TableCellBold"]
            ),
        ],
    ]

    road_table = Table(road_data, colWidths=[65 * pt, 115 * pt, 240 * pt, 75 * pt])
    road_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD_LIGHT]),
                ("ALIGN", (3, 1), (3, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(road_table)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph("The Institutional Governance Assurance Matrix", styles["SubSectionHeader"])
    )
    story.append(
        Paragraph(
            "Prior to each phase transition, QuantOS requires an independent audit by a clean-clone Verifier. "
            "The verifier operates in an isolated environment, rebuilding all artifacts from raw Git revisions to prove that "
            "no cached state, private environment variables, or developer interventions influenced the result.",
            styles["WhitepaperBody"],
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 11: EPILOGUE & MANIFESTO
    # ==========================================
    story.append(
        Paragraph("SECTION 10 : THE QUANTOS MANIFESTO & REFERENCES", styles["DocSuperTitle"])
    )
    story.append(
        Paragraph("Epilogue, Legal Boundaries & Scientific Citations", styles["SectionHeader"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=PRIMARY_NAVY, spaceAfter=8, spaceBefore=2)
    )

    # The Manifesto Card
    manifesto_content = [
        Paragraph("THE QUANTOS MANIFESTO : OUR COMMITMENT TO TRUTH", styles["TeaserHeadline"]),
        Paragraph(
            '<i>"In the financial markets, truth is the rarest commodity. The financial software industry is built upon a conspiracy '
            "of false comfort: vendors sell backtesters that conceal transaction costs, quants publish papers with unpurged lookahead bias, "
            "and funds market inflated Sharpe ratios manufactured through invisible multiple testing.</i>",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<i>QuantOS rejects this paradigm completely. We believe that true institutional alpha is rare, fragile, and fiercely defended "
            "by the laws of market micro-structure. We believe that an operating system that proves our hypotheses are wrong is infinitely "
            "more valuable than one that lies to make us feel like geniuses.</i>",
            styles["WhitepaperBody"],
        ),
        Paragraph(
            "<i>We commit to exact accounting. We commit to point-in-time reality. We commit to recording every failed trial. "
            "We commit to building the most mathematically rigorous, technologically flawless quantitative operating system on Earth. "
            'Capital will not be risked on hope; it will be deployed only on immutable, unyielding truth."</i>',
            styles["WhitepaperBodyBold"],
        ),
    ]
    story.append(
        build_card(manifesto_content, bg_color=BG_LIGHT_BLUE, border_color=PRIMARY_NAVY, padding=9)
    )
    story.append(Spacer(1, 10))

    story.append(
        Paragraph("Institutional Boundaries & Formal Disclosures", styles["SubSectionHeader"])
    )
    story.append(
        Paragraph(
            "<b>Notice of Release Boundary:</b> QuantOS is currently certified as Tier 2 (T2) / Phase 5 (P5) Release Candidate software. "
            "<b>Live-money order routing is strictly and deliberately excluded.</b> All execution surfaces operate in deterministic paper "
            "or shadow mode with <code>broker_orders_submitted</code> mathematically enforced as zero. Any future deployment of live capital "
            "requires a separate Tier 4 (T4) compliance certification, regulatory licensing from SEBI, and broker execution mandate. "
            "Past backtested performance, deflated Sharpe ratios, and simulation outputs are not guarantees of future investment returns.",
            styles["WhitepaperBody"],
        )
    )
    story.append(Spacer(1, 6))

    story.append(Paragraph("Key Academic & Scientific Citations", styles["SubSectionHeader"]))
    story.append(
        Paragraph(
            "1. <b>Bailey, D. H., & López de Prado, M. (2014).</b> The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. <i>Journal of Portfolio Management</i>, 40(5), 94-107.<br/>"
            "2. <b>Harvey, C. R., Liu, Y., & Zhu, H. (2016).</b> ... and the Cross-Section of Expected Returns. <i>The Review of Financial Studies</i>, 29(1), 5-68.<br/>"
            "3. <b>López de Prado, M. (2018).</b> <i>Advances in Financial Machine Learning</i>. John Wiley & Sons, Inc., Hoboken, NJ.<br/>"
            "4. <b>Bouchaud, J. P., Gefen, Y., Potters, M., & Wyart, M. (2004).</b> Fluctuations and response in financial markets: the subtle nature of 'random' price changes. <i>Quantitative Finance</i>, 4(2), 176-185.",
            styles["WhitepaperBody"],
        )
    )
    story.append(Spacer(1, 10))

    colophon = Paragraph(
        "<font size='7' color='#64748B'><b>COLOPHON:</b> This monograph was compiled programmatically by the QuantOS Documentation & Architecture Engine. "
        "Typeset in Helvetica, Helvetica-Bold, and Courier. Layout computed with ReportLab A4 vector primitives. "
        "Repository commit revision: <code>256a6f65a98f95d1cdf916408db47303ee5ad03e</code>. © 2026 QuantOS Research Labs. All rights reserved.</font>",
        styles["WhitepaperBody"],
    )
    story.append(colophon)

    # Build Document with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] QuantOS Moonshot Strategic Whitepaper generated at: {filename}")


if __name__ == "__main__":
    out_file = (
        sys.argv[1] if len(sys.argv) > 1 else "docs/QuantOS_Moonshot_Strategic_Whitepaper.pdf"
    )
    build_pdf(out_file)
