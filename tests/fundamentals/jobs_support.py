"""A job spawner that holds the work until a test runs it: no threads, no sleeps."""

from __future__ import annotations

from collections.abc import Callable


class Held:
    """Spawns nothing by itself: the test runs the held task when it wants the job to run."""

    def __init__(self) -> None:
        self.tasks: list[Callable[[], None]] = []

    def __call__(self, task: Callable[[], None]) -> None:
        self.tasks.append(task)

    def run(self) -> None:
        self.tasks.pop(0)()
