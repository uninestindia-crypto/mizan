"""The Copilot's broker tool: off until allowed, a short summary when on, and nothing that identifies the person."""

from __future__ import annotations

import json
from typing import Any

import pytest

from quant_system.broker_view import messages
from quant_system.broker_view.service import BrokerViewError
from quant_system.broker_view.summary import MAX_HOLDINGS, SUMMARY_KEYS
from quant_system.copilot.registry import ToolContext, UserFacingError
from quant_system.copilot.rules import AnswerContext, answer_without_ai
from quant_system.copilot.tools import default_registry
from tests.broker_fakes import SENTINEL, Rig, all_replies, holding, make_rig
from tests.copilot_fakes import make_context


def context_for(rig: Rig) -> ToolContext:
    def broker() -> dict[str, Any]:
        try:
            return rig.view.assistant_summary()
        except BrokerViewError as error:
            raise UserFacingError(error.message) from error

    base = make_context()
    base.broker = broker
    return base


def connected_rig(**kwargs: Any) -> Rig:
    rig = make_rig(**kwargs)
    rig.view.refresh(force=True)
    return rig


def test_the_tool_exists_and_its_name_cannot_trade() -> None:
    registry = default_registry(make_context())
    assert "broker_account" in registry.names()
    spec = next(s for s in registry.catalog() if s["name"] == "broker_account")
    assert spec["label"] == "My broker account" and "never trade" in spec["help"]


def test_without_a_broker_connection_wired_the_tool_says_it_is_not_available() -> None:
    result = default_registry(make_context()).call("broker_account", {})
    assert not result.ok and result.error == messages.NOT_AVAILABLE


def test_off_by_default_the_assistant_is_told_how_to_allow_it_and_sees_no_figures() -> None:
    rig = connected_rig()
    result = default_registry(context_for(rig)).call("broker_account", {})
    assert not result.ok and result.error == messages.ASSISTANT_OFF
    assert "TCS" not in result.for_prompt() and "35005" not in result.for_prompt()


def test_once_allowed_the_assistant_gets_a_short_summary_with_the_time_it_was_fetched() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    result = default_registry(context_for(rig)).call("broker_account", {})
    assert result.ok
    assert set(result.data) <= SUMMARY_KEYS
    assert "10:30" in result.data["source"] and "06 Oct 2026" in result.data["source"]
    assert result.data["totals"]["value"] == 64805.0 and result.data["cash_available"] == 12000.5
    assert [h["symbol"] for h in result.data["holdings"]] == ["TCS", "INFY"]
    assert "never suggest otherwise" in result.data["note"]


def test_the_summary_holds_no_key_name_email_identifier_or_company() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    result = default_registry(context_for(rig)).call("broker_account", {})
    prompt = result.for_prompt()
    for leak in (SENTINEL, "Invented", "invented@", "INE467B01029", "NSE_EQ", "instrument", "isin"):
        assert leak not in prompt
    assert result.untrusted is False


def test_each_holding_in_the_summary_carries_only_these_fields() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    data = default_registry(context_for(rig)).call("broker_account", {}).data
    assert set(data["holdings"][0]) == {
        "symbol",
        "quantity",
        "average_price",
        "last_price",
        "pnl",
        "pnl_pct",
        "weight_pct",
    }
    assert set(data["positions"][0]) == {"symbol", "product", "quantity", "pnl"}


def test_a_big_account_is_cut_to_the_most_valuable_holdings_and_says_how_many_were_left_out() -> (
    None
):
    rows = [
        holding(f"S{i}", last_price=100.0 + i, average_price=100.0) for i in range(MAX_HOLDINGS + 5)
    ]
    rig = connected_rig(replies=all_replies(holdings=rows))
    rig.view.set_assistant_access(True)
    data = default_registry(context_for(rig)).call("broker_account", {}).data
    assert len(data["holdings"]) == MAX_HOLDINGS and data["holdings_not_shown"] == 5
    assert data["holdings"][0]["symbol"] == f"S{MAX_HOLDINGS + 4}"


def test_after_the_sign_in_ends_the_summary_still_comes_with_a_warning_about_its_age() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    rig.clock.advance(18 * 3600)
    data = default_registry(context_for(rig)).call("broker_account", {}).data
    assert "sign-in has since ended" in data["source"] and "hours ago" in data["source"]


def test_never_connected_and_allowed_the_assistant_is_told_what_to_click() -> None:
    rig = make_rig(key=None)
    rig.view.set_assistant_access(True)
    result = default_registry(context_for(rig)).call("broker_account", {})
    assert not result.ok and result.error == messages.NOT_CONNECTED


def test_an_agent_that_was_not_given_the_tool_cannot_use_it() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    registry = default_registry(context_for(rig))
    assert not registry.call("broker_account", {}, allowed={"find_stock"}).ok


def test_the_assistant_answers_a_broker_question_without_an_ai_key() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    registry = default_registry(context_for(rig))
    reply = answer_without_ai("what is in my broker account?", registry, AnswerContext()).reply
    assert "Your broker account (view only)" in reply and "TCS" in reply
    assert "Nothing can be bought, sold or changed through QuantOS." in reply


def test_a_broker_question_with_the_switch_off_says_how_to_allow_it() -> None:
    rig = connected_rig()
    registry = default_registry(context_for(rig))
    result = answer_without_ai("show my positions", registry, AnswerContext())
    assert messages.ASSISTANT_OFF in result.reply
    assert "/settings/broker" in [p.path for p in result.proposals if p.kind == "navigate"]


def test_the_menu_mentions_the_broker_account() -> None:
    registry = default_registry(make_context())
    reply = answer_without_ai("hello there", registry, AnswerContext()).reply
    assert "Your broker account" in reply


def test_what_the_assistant_reads_serialises_cleanly() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    data = rig.view.assistant_summary()
    assert json.loads(json.dumps(data)) == data


def test_switching_it_off_again_takes_the_figures_away_from_the_assistant() -> None:
    rig = connected_rig()
    rig.view.set_assistant_access(True)
    rig.view.set_assistant_access(False)
    with pytest.raises(BrokerViewError):
        rig.view.assistant_summary()
