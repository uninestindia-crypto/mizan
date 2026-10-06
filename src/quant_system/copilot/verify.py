"""Independent second opinions: several AI models read the same facts about a stock, each in its own call.

Independence is built in, not hoped for. Each model is asked separately and never sees another's answer. Three
questions are asked of every model: a *blind* one (the facts only, and the one that counts), an *informed* one that
adds the platform's own pick (to measure anchoring), and a *recheck* of the blind question with the facts in a
different order (to measure stability). What comes back is summarised by :mod:`verify_summary`.

Nothing here can place an order or change a setting; a model only ever returns text that is read and sanitised.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from quant_system.copilot.factpack import FactPack
from quant_system.copilot.llm import ChatModel
from quant_system.copilot.verify_opinion import Opinion, Question, ask_for_opinion, build_question
from quant_system.copilot.verify_summary import ModelVerdict, VerificationResult, summarise

__all__ = ["MAX_MODELS", "VerifyOptions", "verify_stock"]

MAX_MODELS = 6


@dataclass(frozen=True, slots=True)
class VerifyOptions:
    pick_context: str | None = (
        None  # the platform's own note about why it picked the stock; adds the informed arm
    )
    recheck: bool = True
    timeout: float = 60.0


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
        if options.recheck:
            jobs.append(_Job(index, ask("recheck", build_question(pack.symbol, reordered))))
    return jobs


def _run_panel(
    panel: Sequence[ChatModel],
    jobs: list[_Job],
    on_opinion: Callable[[Opinion], None] | None,
) -> dict[tuple[int, str], Opinion]:
    done: dict[tuple[int, str], Opinion] = {}
    with ThreadPoolExecutor(max_workers=min(len(jobs), MAX_MODELS)) as pool:
        futures = {
            pool.submit(ask_for_opinion, panel[job.model_index], job.question): job for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            opinion = future.result()
            done[(job.model_index, job.question.arm)] = opinion
            if on_opinion:
                on_opinion(opinion)
    return done


def _verdicts(count: int, done: dict[tuple[int, str], Opinion]) -> list[ModelVerdict]:
    return [
        ModelVerdict(done[(i, "blind")], done.get((i, "informed")), done.get((i, "recheck")))
        for i in range(count)
    ]


def _nothing(pack: FactPack, asked: int, why: str) -> VerificationResult:
    result = summarise(pack, [], asked, [why])
    result.headline = why
    return result


def verify_stock(
    models: Sequence[ChatModel],
    pack: FactPack,
    options: VerifyOptions | None = None,
    on_opinion: Callable[[Opinion], None] | None = None,
) -> VerificationResult:
    """Ask each model separately and summarise. Never raises; a model that fails is reported, not hidden."""
    options = options or VerifyOptions()
    panel = list(models)[:MAX_MODELS]
    if not pack.usable:
        return _nothing(
            pack,
            len(panel),
            f"I could not find price facts for {pack.symbol}, so there is nothing to check.",
        )
    if not panel:
        return _nothing(
            pack, 0, "No AI models were chosen. Pick at least one, or add an AI key in Settings."
        )
    cut = [f"Only the first {MAX_MODELS} models were asked."] if len(models) > MAX_MODELS else []
    done = _run_panel(panel, _jobs(len(panel), pack, options), on_opinion)
    return summarise(pack, _verdicts(len(panel), done), len(panel), cut)
