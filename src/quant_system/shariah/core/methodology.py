"""The words that travel with every verdict: which rules produced it and what it leaves out.

One place owns them, so a screen, the Copilot and `docs/HALAL_METHODOLOGY.md` all say the same thing.
"""

#: Changed only when a rule, a threshold or a data source changes, and noted in the methodology document.
METHODOLOGY_VERSION = "shariah-screen-v1"

#: What a verdict does not cover, in plain sentences a person can read as they are.
NOT_COVERED: tuple[str, ...] = (
    "No scholar has reviewed these rules or this result.",
    "The figures are a hand-entered sample, not read from audited filings.",
    "Not every income line has been reviewed, so a company's real mix of income may differ from what is counted here.",
    "This is a screening aid, not a fatwa and not financial advice.",
)
