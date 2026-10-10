"""Independent second opinions: several AI models read the same facts about a stock, each in its own call.

Independence is built in, not hoped for. Each model is asked separately and never sees another's answer. Three
questions are asked of every model: a *blind* one (the facts only, and the one that counts), an *informed* one that
adds the platform's own pick (to measure anchoring), and a *recheck* of the blind question with the facts in a
different order (to measure stability). What comes back is summarised by :mod:`verify_summary`.

Nothing here can place an order or change a setting; a model only ever returns text that is read and sanitised.

A check can be stopped part-way (``VerifyOptions.cancelled``). Calls still waiting for their turn are then never made.
A call that is already out with an AI service cannot be recalled: it runs to its end and its answer is ignored.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from quant_system.copilot.factpack import FactPack
from quant_system.copilot.llm import ChatModel
from quant_system.copilot.messages import CANCELLED_TEXT
from quant_system.copilot.verify_opinion import (
    Opinion,
    Question,
    ask_for_opinion,
    build_chained_question,
    build_question,
)
from quant_system.copilot.verify_summary import ModelVerdict, VerificationResult, summarise

__all__ = ["MAX_MODELS", "VerifyOptions", "verify_stock"]

MAX_MODELS = 6
MAX_PARALLEL = (
    6  # AI calls out at the same time; the rest wait their turn, and can still be stopped
)
NOT_REORDERABLE = (
    "The facts could not be shown in a different order, so whether the AI models hold their reading "
    "when the facts are reordered was not checked."
)
NO_MODELS = (
    "No AI models were chosen. Pick at least one, or set one up: open Settings, then AI assistants."
)


@dataclass(frozen=True, slots=True)
class VerifyOptions:
    pick_context: str | None = (
        None  # the platform's own note about why it picked the stock; adds the informed arm
    )
    recheck: bool = True
    timeout: float = 60.0
    # Asked before every call that has not started yet. When it says True the call is not made. A call already in
    # flight cannot be recalled, so it still finishes.
    cancelled: Callable[[], bool] | None = None
    chained: bool = False  # Sequential critique & recheck pipeline
    max_models: int | None = None  # None allows unlimited / infinite models


@dataclass(frozen=True, slots=True)
class _Job:
    model_index: int
    question: Question


def _jobs(count: int, pack: FactPack, options: VerifyOptions) -> list[_Job]:
    facts, reordered = pack.render(), pack.render(reverse=True)

    def ask(arm: str, text: str) -> Question:
        return Question(arm, text, options.timeout)

    jobs: list[_Job] = []
    for index in range(count):
        jobs.append(_Job(index, ask("blind", build_question(pack.symbol, facts))))
        if options.pick_context:
            informed = build_question(pack.symbol, facts, pick_context=options.pick_context)
            jobs.append(_Job(index, ask("informed", informed)))
        if options.recheck and pack.reorderable:
            jobs.append(_Job(index, ask("recheck", build_question(pack.symbol, reordered))))
    return jobs


def _ask(model: ChatModel, question: Question, cancelled: Callable[[], bool]) -> Opinion:
    """One call, unless the person has stopped the check by the time its turn comes."""
    if cancelled():
        return Opinion(model.provider, model.model, question.arm, False, error=CANCELLED_TEXT)
    return ask_for_opinion(model, question)


def _run_panel(
    panel: Sequence[ChatModel],
    jobs: list[_Job],
    on_opinion: Callable[[Opinion], None] | None,
    cancelled: Callable[[], bool],
) -> dict[tuple[int, str], Opinion]:
    done: dict[tuple[int, str], Opinion] = {}
    with ThreadPoolExecutor(max_workers=min(len(jobs), MAX_PARALLEL)) as pool:
        futures = {
            pool.submit(_ask, panel[job.model_index], job.question, cancelled): job for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            opinion = future.result()
            done[(job.model_index, job.question.arm)] = opinion
            if on_opinion:
                on_opinion(opinion)
    return done


def _run_chained_pipeline(
    panel: Sequence[ChatModel],
    pack: FactPack,
    options: VerifyOptions,
    on_opinion: Callable[[Opinion], None] | None,
    cancelled: Callable[[], bool],
) -> dict[tuple[int, str], Opinion]:
    done: dict[tuple[int, str], Opinion] = {}
    facts = pack.render()
    prior_opinions: list[Opinion] = []
    total = len(panel)

    for index, model in enumerate(panel):
        if cancelled():
            opinion = Opinion(
                model.provider,
                model.model,
                "blind",
                False,
                error=CANCELLED_TEXT,
            )
            done[(index, "blind")] = opinion
            if on_opinion:
                on_opinion(opinion)
            continue

        q_text = build_chained_question(
            pack.symbol,
            facts,
            prior_opinions,
            pick_context=options.pick_context,
            stage_index=index + 1,
            total_stages=total,
        )
        question = Question("blind", q_text, options.timeout)
        opinion = _ask(model, question, cancelled)
        done[(index, "blind")] = opinion
        prior_opinions.append(opinion)
        if on_opinion:
            on_opinion(opinion)

    return done


def _verdicts(count: int, done: dict[tuple[int, str], Opinion]) -> list[ModelVerdict]:
    return [
        ModelVerdict(done[(i, "blind")], done.get((i, "informed")), done.get((i, "recheck")))
        for i in range(count)
    ]


def _nothing(pack: FactPack, why: str) -> VerificationResult:
    """No AI was asked, so none failed: no one is counted as asked, and the headline alone says what to do."""
    result = summarise(pack, [], 0, [])
    result.headline = why
    return result


def _no_facts(symbol: str) -> str:
    return (
        f"I could not find price facts for {symbol}, so no AI was asked. "
        "Check the symbol, or connect market data: open Settings, then Market data."
    )


def verify_stock(
    models: Sequence[ChatModel],
    pack: FactPack,
    options: VerifyOptions | None = None,
    on_opinion: Callable[[Opinion], None] | None = None,
) -> VerificationResult:
    """Ask each model in priority order and summarise. Supports infinite models and sequential chained rechecks.

    When there is nothing to show (no price facts) or no one to ask, nobody is asked and the result says why.
    Once ``options.cancelled`` says True, calls that have not started are skipped; calls already out cannot be recalled.
    """
    options = options or VerifyOptions()
    limit = (
        options.max_models
        if options.max_models is not None
        else (None if options.chained else MAX_MODELS)
    )
    panel = list(models)[:limit] if limit is not None else list(models)
    if not pack.usable:
        return _nothing(pack, _no_facts(pack.symbol))
    if not panel:
        return _nothing(pack, NO_MODELS)
    cut = (
        [f"Only the first {limit} AI models were asked."]
        if limit is not None and len(models) > limit
        else []
    )
    if options.recheck and not pack.reorderable and not options.chained:
        cut.append(NOT_REORDERABLE)
    cancelled = options.cancelled or (lambda: False)
    if options.chained:
        done = _run_chained_pipeline(panel, pack, options, on_opinion, cancelled)
    else:
        done = _run_panel(panel, _jobs(len(panel), pack, options), on_opinion, cancelled)
    return summarise(pack, _verdicts(len(panel), done), len(panel), cut)
