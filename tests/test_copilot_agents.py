"""Saved agents, the ready-made recipes, and running their steps: bounded, tool-limited and plain-spoken."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from quant_system.copilot.agent_store import (
    MAX_AGENTS,
    MAX_STEPS,
    AgentDraft,
    AgentRejectedError,
    AgentStore,
    Problem,
    SavedAgent,
    validate,
)
from quant_system.copilot.llm import ChatReply
from quant_system.copilot.recipes import RECIPES, Recipe, recipe
from quant_system.copilot.registry import ToolRegistry
from quant_system.copilot.tools import default_registry
from quant_system.copilot.workflow import RunOptions, run_workflow
from tests.copilot_fakes import FakeNews, StubModel, make_context

TOOLS = default_registry(make_context()).names()
GOOD = AgentDraft(
    "My check", "d", "Keep it short.", ("stock_facts",), ("Show the facts about {symbol}.",)
)


def _store(tmp_path: Path) -> AgentStore:
    return AgentStore(tmp_path / "copilot.sqlite")


def _registry() -> ToolRegistry:
    return default_registry(make_context(news=FakeNews()))


def _saved(draft: AgentDraft) -> SavedAgent:
    """A saved agent without a database, for running."""
    return SavedAgent(
        "x", draft.name, draft.description, draft.instructions, draft.tools, draft.steps, "", ""
    )


def _recipe(recipe_id: str) -> Recipe:
    found = recipe(recipe_id)
    assert found is not None
    return found


def _fields(problems: list[Problem]) -> list[str]:
    return [p.field for p in problems]


# ------------------------------------------------------------------------------------- the store


def test_an_agent_can_be_saved_listed_changed_and_deleted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    saved = store.create(GOOD, TOOLS)
    assert [a.id for a in store.agents()] == [saved.id] and saved.needs_symbol
    changed = store.update(saved.id, replace(GOOD, name="Renamed", steps=("One", "Two")), TOOLS)
    assert changed is not None and changed.name == "Renamed" and changed.steps == ("One", "Two")
    assert changed.created_at == saved.created_at
    assert (
        store.delete(saved.id) is True and store.agents() == [] and store.delete(saved.id) is False
    )


def test_agents_survive_a_restart(tmp_path: Path) -> None:
    saved = _store(tmp_path).create(GOOD, TOOLS)
    assert _store(tmp_path).get(saved.id) == saved


def test_text_is_trimmed_and_stored_literally(tmp_path: Path) -> None:
    draft = replace(GOOD, name="  Bobby'); DROP TABLE agents;--  ", steps=("  Show {symbol}  ",))
    saved = _store(tmp_path).create(draft, TOOLS)
    assert saved.name == "Bobby'); DROP TABLE agents;--" and saved.steps == ("Show {symbol}",)


def test_changing_or_deleting_a_missing_agent_says_nothing_was_found(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.update("nope", GOOD, TOOLS) is None and store.get("nope") is None


def test_an_agent_may_keep_its_own_name_when_edited_but_not_take_anothers(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.create(GOOD, TOOLS)
    other = store.create(replace(GOOD, name="Second"), TOOLS)
    assert store.update(first.id, replace(GOOD, description="new"), TOOLS) is not None
    with pytest.raises(AgentRejectedError) as raised:
        store.update(other.id, replace(GOOD, name="MY CHECK"), TOOLS)
    assert _fields(raised.value.problems) == ["name"]


def test_there_is_a_limit_on_how_many_agents_a_person_keeps(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for_each = [replace(GOOD, name=f"Agent {number}") for number in range(MAX_AGENTS)]
    assert len([store.create(draft, TOOLS) for draft in for_each]) == MAX_AGENTS
    with pytest.raises(AgentRejectedError) as raised:
        store.create(replace(GOOD, name="One too many"), TOOLS)
    assert "Delete one first" in raised.value.problems[0].message


@pytest.mark.parametrize(
    ("draft", "field", "needle"),
    [
        (replace(GOOD, name="   "), "name", "Give your agent a name"),
        (replace(GOOD, name="x" * 61), "name", "shorter"),
        (replace(GOOD, description="x" * 201), "description", "shorter"),
        (replace(GOOD, instructions="x" * 1501), "instructions", "shorter"),
        (replace(GOOD, steps=()), "steps", "at least one step"),
        (replace(GOOD, steps=("ok",) * (MAX_STEPS + 1)), "steps", f"at most {MAX_STEPS}"),
        (replace(GOOD, steps=("ok", "  ")), "steps", "Step 2 is empty"),
        (replace(GOOD, steps=("x" * 501,)), "steps", "Step 1 is too long"),
        (
            replace(GOOD, steps=("Use {price} here",)),
            "steps",
            "only fill-in you can use is {symbol}",
        ),
        (replace(GOOD, tools=()), "tools", "Tick at least one"),
        (replace(GOOD, tools=("launch_missiles",)), "tools", "not available"),
    ],
)
def test_each_form_problem_names_its_field_and_says_what_to_do(
    draft: AgentDraft, field: str, needle: str
) -> None:
    problems = validate(draft, TOOLS)
    assert [p.field for p in problems] == [field] and needle in problems[0].message


def test_a_good_draft_has_no_problems_and_every_message_is_plain_words() -> None:
    assert validate(GOOD, TOOLS) == []
    bad = AgentDraft("", "x" * 999, "x" * 9999, ("zzz",), ("{a}", "", "x" * 999))
    text = " ".join(p.message for p in validate(bad, TOOLS))
    assert not re.search(
        r"terminal|command|\.env|environment variable|JSON|API\b|token", text, re.I
    )


def test_problems_reach_the_screen_as_field_and_message() -> None:
    assert Problem("name", "Give your agent a name.").as_dict() == {
        "field": "name",
        "message": "Give your agent a name.",
    }


# ------------------------------------------------------------------------------------- recipes


def test_the_recipes_are_valid_agents_so_copy_and_edit_always_saves() -> None:
    for_each = [
        AgentDraft(r.name, r.description, r.instructions, r.tools, r.steps) for r in RECIPES
    ]
    assert [validate(draft, TOOLS) for draft in for_each] == [[] for _ in RECIPES]


def test_recipe_ids_are_unique_and_found_and_marked_built_in() -> None:
    ids = [r.id for r in RECIPES]
    assert len(set(ids)) == len(ids) and recipe(ids[0]) is RECIPES[0] and recipe("nope") is None
    assert all(r.as_dict()["built_in"] for r in RECIPES)


@pytest.mark.parametrize("item", RECIPES, ids=[r.id for r in RECIPES])
def test_recipes_only_use_the_fill_in_the_form_allows(item: Recipe) -> None:
    assert all(set(re.findall(r"\{(.*?)\}", step)) <= {"symbol"} for step in item.steps)


# ------------------------------------------------------------------------------------- running, no AI key


def test_a_recipe_runs_with_no_ai_key_from_the_built_in_answers() -> None:
    result = run_workflow(_recipe("recipe-check-stock"), _registry(), RunOptions(symbol="aaa"))
    assert (
        result.completed
        and result.symbol == "AAA"
        and [s.number for s in result.steps] == [1, 2, 3, 4]
    )
    replies = [s.reply for s in result.steps]
    assert (
        "Last close" in replies[0]
        and "AAOIFI" in replies[1]
        and "Alpha wins a large order" in replies[2]
    )
    assert not any("choose an AI" in r.lower() for r in replies)  # said once, in the note
    assert "No AI is set up" in str(result.note)
    assert {p.kind for p in result.proposals} == {"second_opinion", "navigate"}


def test_a_step_only_uses_the_tools_the_agent_was_given() -> None:
    narrow = replace(GOOD, tools=("stock_facts",), steps=("Is {symbol} halal?",))
    agent = _saved(narrow)
    result = run_workflow(agent, _registry(), RunOptions(symbol="AAA"))
    assert "not set up to look that up" in result.steps[0].reply
    assert [s.ok for s in result.steps[0].looked_at if s.tool == "shariah_check"] == [False]


def test_a_stock_is_required_when_the_steps_need_one_and_must_look_like_a_symbol() -> None:
    agent = _saved(GOOD)
    assert "which stock" in str(run_workflow(agent, _registry(), RunOptions()).note).lower()
    bad = run_workflow(agent, _registry(), RunOptions(symbol="AAA; DROP"))
    assert bad.steps == [] and "stock symbol" in str(bad.note)


def test_an_agent_that_needs_an_ai_is_refused_without_one_and_offered_the_next_click() -> None:
    result = run_workflow(
        _recipe("recipe-watchlist-review"), _registry(), RunOptions(needs_ai=True)
    )
    assert result.steps == [] and "needs an AI to work" in str(result.note)
    assert result.proposals[0].path == "/settings/ai"


# ------------------------------------------------------------------------------------- running, with an AI


def _final(text: str) -> str:
    return json.dumps({"final": text})


def test_with_an_ai_each_step_is_a_conversation_that_remembers_the_steps_before_it() -> None:
    model = StubModel(
        "p0", lambda _s, user: _final("answer to: " + user.split("Person: ")[-1].split("\n")[0])
    )
    agent = _saved(
        replace(
            GOOD, steps=("First {symbol}", "Second {symbol}"), instructions="Be brief on {symbol}."
        )
    )
    result = run_workflow(agent, _registry(), RunOptions(symbol="AAA", model=model))
    assert result.completed and [s.reply for s in result.steps] == [
        "answer to: First AAA",
        "answer to: Second AAA",
    ]
    assert (
        "answer to: First AAA" in model.calls[1][1]
    )  # the second step saw the first step's answer
    assert (
        "Be brief on AAA." in model.calls[0][0]
        and result.model == "p0-model"
        and result.note is None
    )


def test_with_an_ai_a_step_cannot_use_a_tool_the_agent_was_not_given() -> None:
    def respond(_s: str, user: str) -> str:
        if "Tool results so far" in user:
            return _final("done")
        return json.dumps({"tool": "shariah_check", "args": {"symbol": "AAA"}})

    agent = _saved(replace(GOOD, tools=("stock_facts",), steps=("Check {symbol}",)))
    result = run_workflow(
        agent, _registry(), RunOptions(symbol="AAA", model=StubModel("p0", respond))
    )
    assert [s.ok for s in result.steps[0].looked_at] == [False]


def test_a_provider_failure_stops_the_run_with_a_plain_reason_and_keeps_what_finished() -> None:
    replies = [_final("first ok"), ChatReply(None, 401, "HTTP 401 bad key")]
    model = StubModel("p0", lambda _s, _u: replies.pop(0))
    agent = _saved(replace(GOOD, steps=("One", "Two", "Three")))
    result = run_workflow(agent, _registry(), RunOptions(symbol="AAA", model=model))
    assert [s.number for s in result.steps] == [1, 2] and not result.completed
    assert result.steps[0].error is None and "key" in str(result.steps[1].error).lower()
    assert "HTTP" not in result.steps[1].reply


def test_a_slow_run_stops_between_steps() -> None:
    ticks = iter([0.0, 0.0, 999.0, 999.0, 999.0])
    agent = _saved(replace(GOOD, steps=("One", "Two")))
    options = RunOptions(
        symbol="AAA",
        model=StubModel("p0", _final("ok")),
        deadline_seconds=60.0,
        clock=lambda: next(ticks),
    )
    result = run_workflow(agent, _registry(), options)
    assert (
        [s.number for s in result.steps] == [1]
        and "too long" in str(result.note)
        and not result.completed
    )


def test_no_more_than_the_step_limit_ever_runs_and_the_result_is_plain_data() -> None:
    agent = _saved(replace(GOOD, steps=tuple(f"Step {i}" for i in range(MAX_STEPS + 3))))
    result = run_workflow(
        agent, _registry(), RunOptions(symbol="AAA", model=StubModel("p0", _final("ok")))
    )
    assert len(result.steps) == MAX_STEPS
    assert json.loads(json.dumps(result.as_dict()))["completed"] is True
