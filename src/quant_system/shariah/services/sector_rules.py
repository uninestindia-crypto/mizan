"""The sector rules: which lines of business a company is screened out for, and the word that decided it.

The rules are a table, so the screener, the explanation of a verdict and `docs/HALAL_METHODOLOGY.md` read the
same list. A rule matches by plain text search over the sector, the industry and the business summary, so a
word inside a longer word can also match.
"""

from dataclasses import dataclass

from quant_system.shariah.schemas.screening import SectorRuleResult

INTEREST_REASON = "Conventional banking and interest lending (Riba)"


@dataclass(frozen=True)
class SectorRule:
    rule: str
    reason: str
    keywords: tuple[str, ...]
    sector_names: tuple[str, ...] = ()


#: Checked in this order. The first rule with a hit decides.
SECTOR_RULES: tuple[SectorRule, ...] = (
    SectorRule(
        rule="interest_based_finance",
        reason=INTEREST_REASON,
        sector_names=("financial services", "banking", "insurance"),
        keywords=(
            "commercial bank",
            "retail lending",
            "housing finance",
            "nbfc - consumer lending",
            "life insurance",
            "general insurance",
        ),
    ),
    SectorRule(
        rule="alcohol",
        reason="Commercial manufacturing and distribution of liquor and beer (Khamr)",
        keywords=(
            "distilleries, breweries",
            "alcoholic beverages",
            "liquor",
            "spirits",
            "brewery",
            "distillery",
            "beer",
            "imfl",
        ),
    ),
    SectorRule(
        rule="tobacco",
        reason="Manufacturing or distribution of tobacco and nicotine products (Dharar)",
        keywords=("cigarettes, tobacco", "cigarette", "tobacco", "cigars", "gutkha"),
    ),
    SectorRule(
        rule="gambling",
        reason="Operation of gambling or gaming ventures (Maysir/Qimar)",
        keywords=(
            "casinos, gaming",
            "casino",
            "gambling",
            "lottery",
            "real-money gaming",
            "real money gaming",
        ),
    ),
    SectorRule(
        rule="cinema",
        reason="Commercial cinema theater exhibition of unscreened non-halal media",
        keywords=("cinema", "film exhibition"),
    ),
)

#: A company in these sectors passes the sector test unless its text mentions one of the blocking words.
IT_SECTOR_NAMES = ("information technology", "it")
IT_BLOCKING_WORDS = ("casino", "gambling", "betting")


def _first_hit(rule: SectorRule, sector: str, text: str) -> str | None:
    """The sector name or keyword that made this rule fire, or None."""
    if sector in rule.sector_names:
        return sector
    return next((word for word in rule.keywords if word in text), None)


def explain_sector_compliance(
    sector: str, industry: str, business_summary: str = ""
) -> SectorRuleResult:
    """Decide the sector test and say which rule fired and on which word."""
    sector_name = sector.strip().lower()
    text = f"{sector_name} {industry.strip().lower()} {business_summary.strip().lower()}"
    if sector_name in IT_SECTOR_NAMES and not any(word in text for word in IT_BLOCKING_WORDS):
        return SectorRuleResult(compliant=True)
    for rule in SECTOR_RULES:
        hit = _first_hit(rule, sector_name, text)
        if hit is not None:
            return SectorRuleResult(
                compliant=False, rule=rule.rule, matched_keyword=hit, reason=rule.reason
            )
    return SectorRuleResult(compliant=True)
