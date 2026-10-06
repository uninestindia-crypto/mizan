"""Ready-made assistants a person can run as they are, or copy and change.

They live in code so they are always there and cannot be edited or deleted by accident. The steps are written so
each one is answered from the read-only tools even with no AI key; an AI key makes them richer, and the ones that
only make sense with an AI say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["RECIPES", "Recipe", "recipe"]

_HONEST = "Never tell me to buy or sell. Say how fresh each fact is, and say clearly when data is a sample."


@dataclass(frozen=True, slots=True)
class Recipe:
    id: str
    name: str
    description: str
    instructions: str
    tools: tuple[str, ...]
    steps: tuple[str, ...]
    needs_ai: bool = False

    @property
    def needs_symbol(self) -> bool:
        return any("{symbol}" in text for text in (*self.steps, self.instructions))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": list(self.tools),
            "steps": list(self.steps),
            "needs_symbol": self.needs_symbol,
            "needs_ai": self.needs_ai,
            "built_in": True,
        }


RECIPES: tuple[Recipe, ...] = (
    Recipe(
        id="recipe-check-stock",
        name="Check a stock, step by step",
        description="Price facts, halal screening, news and a button for an independent AI second opinion.",
        instructions=f"Be brief. Finish with two lines: what looks fine and what to double-check. {_HONEST}",
        tools=(
            "stock_facts",
            "shariah_check",
            "news_headlines",
            "suggest_second_opinion",
            "evidence_status",
        ),
        steps=(
            "Show the facts about {symbol}: returns, volatility and worst fall.",
            "Is {symbol} halal? Show both standards and every ratio, and say where the data comes from.",
            "Find the latest headlines on {symbol} and say whether the news tone looks positive, negative or mixed.",
            "Suggest an independent second opinion on {symbol}.",
        ),
    ),
    Recipe(
        id="recipe-news-brief",
        name="News brief",
        description="The latest headlines for a stock with a rough tone, linked so you can read them yourself.",
        instructions=f"List the headlines with their links and do not repeat them in other words. {_HONEST}",
        tools=("news_headlines",),
        steps=(
            "Find the latest headlines on {symbol} and say whether the news tone looks positive, negative or mixed.",
        ),
    ),
    Recipe(
        id="recipe-halal-explainer",
        name="Halal screening explained",
        description="Shows how the screener judged a stock, ratio by ratio, and where its data comes from.",
        instructions=(
            "Explain each ratio in plain words and why it matters. Quote the screener's verdict; never give your "
            f"own. Remind me it is a screening aid and not a fatwa. {_HONEST}"
        ),
        tools=("shariah_check", "fundamentals"),
        steps=(
            "Is {symbol} halal? Show both standards and every ratio, and say where the data comes from.",
        ),
    ),
    Recipe(
        id="recipe-watchlist-review",
        name="Watchlist review",
        description="Walks through everything on your watchlist and points out which stock moved most this month.",
        instructions=f"Keep it to a short list. {_HONEST}",
        tools=("watchlist", "stock_facts"),
        steps=(
            "Show my watchlist.",
            "For each stock on it, get the facts and tell me which one moved most over the last month.",
        ),
        needs_ai=True,
    ),
)


def recipe(recipe_id: str) -> Recipe | None:
    return next((r for r in RECIPES if r.id == recipe_id), None)
