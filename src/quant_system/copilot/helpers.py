"""A small team: the Copilot hands independent sub-questions to helpers who work at the same time.

Each helper is a separate run of the same bounded loop, with the same read-only lookup tools and nothing else: a helper
cannot ask for a change, cannot hand work on to other helpers, and does not see the other helpers' answers. Where the
person has set up more than one AI, the helpers use a different AI from the lead's first (as far as there are AIs), which
keeps their readings independent. Their answers come back to the lead as opinions to check, not as facts.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from quant_system.copilot.agent import CopilotAgent, Message
from quant_system.copilot.llm import ChatModel
from quant_system.copilot.registry import ToolRegistry

__all__ = ["HelperResult", "TeamOfHelpers"]

logger = logging.getLogger(__name__)

MAX_TASK_CHARS = 300
_FAILED = "This helper could not finish."


@dataclass(frozen=True, slots=True)
class HelperResult:
    task: str
    reply: str
    ok: bool
    model: str | None = None


class TeamOfHelpers:
    def __init__(
        self,
        models: Sequence[ChatModel],
        registry: ToolRegistry,
        *,
        slots: int,
        allowed: set[str] | None = None,
        shariah_mode: bool = False,
        page: str | None = None,
        max_steps: int = 4,
        call_timeout: float = 60.0,
        deadline_seconds: float = 120.0,
        cancelled: Callable[[], bool] | None = None,
        on_event: Callable[..., None] | None = None,
    ) -> None:
        if not models:
            raise ValueError("A team needs at least one AI to ask.")
        self._models = list(models)
        self._registry = registry
        self.slots = max(0, slots)
        self._allowed = allowed
        self._shariah = shariah_mode
        self._page = page
        self._max_steps = max_steps
        self._call_timeout = call_timeout
        self._deadline = deadline_seconds
        self._cancelled = cancelled or (lambda: False)
        self._on_event = on_event or (lambda *_a, **_k: None)

    def _model_for(self, index: int) -> ChatModel:
        """Helper 1 uses the person's second AI when there is one, helper 2 the third, then round again."""
        return self._models[(index + 1) % len(self._models)]

    def run(self, tasks: Sequence[str]) -> list[HelperResult]:
        """Every task answered, side by side, in the order given. Never raises."""
        chosen = [" ".join(str(t).split())[:MAX_TASK_CHARS] for t in tasks][: self.slots]
        chosen = [t for t in chosen if t]
        if not chosen or self._cancelled():
            return []
        for number, task in enumerate(chosen, start=1):
            self._on_event("helper", f"Helper {number} is looking into: {task}")
        with ThreadPoolExecutor(
            max_workers=len(chosen), thread_name_prefix="quantos-helper"
        ) as pool:
            futures = [pool.submit(self._one, i, task) for i, task in enumerate(chosen)]
            results = [future.result() for future in futures]
        for number, result in enumerate(results, start=1):
            self._on_event("helper_done", f"Helper {number} finished.", result.ok)
        return results

    def _one(self, index: int, task: str) -> HelperResult:
        model = self._model_for(index)
        try:
            agent = CopilotAgent(
                model,
                self._registry,
                max_steps=self._max_steps,
                call_timeout=self._call_timeout,
                deadline_seconds=self._deadline,
            )
            result = agent.run(
                [Message("user", task)],
                page=self._page,
                allowed=self._allowed,
                shariah_mode=self._shariah,
            )
        except Exception as error:  # a helper failing must not stop the others, or the lead
            logger.warning("A helper stopped unexpectedly (%s).", type(error).__name__)
            return HelperResult(task, _FAILED, False)
        return HelperResult(task, result.reply, result.error is None, result.model)
