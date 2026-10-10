"""The Copilot can ask the signed-in AI app already on this computer (Claude Code, Codex, Gemini CLI) instead of a key.

The app is run with its tools switched off, the question goes in on standard input (never on the command line), and
anything unexpected fails closed with a plain sentence instead of being retried with the safety switches removed.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from quant_system.copilot.cli_chat import (
    CLI_FAILED,
    CLI_LABELS,
    CLI_NOT_FOUND,
    CLI_NOT_SIGNED_IN,
    CLI_UNSUPPORTED,
    MIN_TIMEOUT_SECONDS,
    CliChat,
    RunResult,
    build_command,
    cli_environment,
    run_cli,
)
from quant_system.copilot.messages import explain_failure

EXE = "/tools/agent"
Call = tuple[list[str], str, float, Mapping[str, str]]


class FakeRunner:
    """Stands in for the real program: records every call and hands back one fixed result."""

    def __init__(self, result: RunResult) -> None:
        self.result = result
        self.calls: list[Call] = []

    def __call__(
        self, argv: list[str], stdin: str, timeout: float, env: Mapping[str, str]
    ) -> RunResult:
        self.calls.append((argv, stdin, timeout, env))
        return self.result


def _claude_json(text: str, **extra: Any) -> str:
    return json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "result": text, **extra}
    )


def _claude_error(text: str) -> str:
    return json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": text})


def _chat(agent: str, runner: FakeRunner) -> CliChat:
    return CliChat(agent, EXE, runner=runner, environment={"PATH": "/bin"})


def _ask(
    chat: CliChat, system: str = "SYSTEM RULES", user: str = "USER QUESTION", **kwargs: Any
) -> Any:
    return chat.complete(system, user, **kwargs)


# --------------------------------------------------------------------------------------- the command


def test_claude_is_run_with_every_tool_switched_off() -> None:
    argv = build_command("claude", EXE)
    assert argv[0] == EXE and "-p" in argv
    assert argv[argv.index("--tools") + 1] == ""  # no file, shell or web tool
    assert "--strict-mcp-config" in argv  # and none of the person's own add-on tools
    assert argv[argv.index("--max-turns") + 1] == "1"


def test_codex_is_run_read_only_and_reads_the_question_from_standard_input() -> None:
    argv = build_command("codex", EXE)
    assert argv[1] == "exec" and argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[-1] == "-"


def test_gemini_gets_only_a_fixed_instruction_and_the_question_arrives_on_standard_input() -> None:
    argv = build_command("gemini", EXE)
    assert argv[1] == "-p" and "standard input" in argv[2]


def test_an_app_that_cannot_be_used_for_chat_is_refused() -> None:
    with pytest.raises(ValueError, match="chat"):
        build_command("antigravity", EXE)


# --------------------------------------------------------------------------------------- the environment


def test_the_app_is_given_only_what_it_needs_to_run_and_none_of_the_saved_keys() -> None:
    base = {
        "PATH": "/old",
        "USERPROFILE": "C:/Users/a",
        "APPDATA": "C:/Users/a/AppData",
        "OPENAI_API_KEY": "placeholder-1",  # pragma: allowlist secret - a dummy value
        "ANTHROPIC_API_KEY": "placeholder-2",  # pragma: allowlist secret - a dummy value
        "UPSTOX_ACCESS_TOKEN": "placeholder-3",  # pragma: allowlist secret - a dummy value
        "AWS_SECRET_ACCESS_KEY": "placeholder-4",  # pragma: allowlist secret - a dummy value
    }
    env = cli_environment(base, "/new/path")
    assert env["PATH"] == "/new/path" and env["USERPROFILE"] == "C:/Users/a"
    assert not [name for name in env if "KEY" in name or "TOKEN" in name or "SECRET" in name]


# --------------------------------------------------------------------------------------- a good answer


def test_the_question_goes_in_on_standard_input_and_never_on_the_command_line() -> None:
    runner = FakeRunner(RunResult(0, _claude_json("It is fine.")))
    _ask(_chat("claude", runner), system="SYSTEM RULES", user="USER QUESTION")
    argv, stdin, _timeout, _env = runner.calls[0]
    assert "SYSTEM RULES" in stdin and "USER QUESTION" in stdin
    assert not [part for part in argv if "SYSTEM RULES" in part or "USER QUESTION" in part]


def test_claudes_json_answer_is_unwrapped_and_names_the_model_it_used() -> None:
    result = RunResult(0, _claude_json("It is fine.", modelUsage={"claude-sonnet-x": {}}))
    reply = _ask(_chat("claude", FakeRunner(result)))
    assert (reply.text, reply.status, reply.model) == ("It is fine.", 200, "claude-sonnet-x")


@pytest.mark.parametrize("agent", ["codex", "gemini"])
def test_the_other_apps_plain_text_answer_is_used_as_it_is(agent: str) -> None:
    reply = _ask(_chat(agent, FakeRunner(RunResult(0, "  Plain answer.\n"))))
    assert (reply.text, reply.status) == ("Plain answer.", 200)


def test_the_model_is_identified_by_the_app_it_came_from() -> None:
    chat = _chat("codex", FakeRunner(RunResult(0, "x")))
    assert chat.provider == "cli:codex"


def test_a_very_long_answer_is_cut_not_passed_on_whole() -> None:
    reply = _ask(_chat("codex", FakeRunner(RunResult(0, "y" * 500_000))))
    assert reply.text is not None and 0 < len(reply.text) <= 30_000


def test_a_question_too_long_to_send_is_refused_without_running_anything() -> None:
    runner = FakeRunner(RunResult(0, "x"))
    reply = _ask(_chat("claude", runner), user="q" * 200_000)
    assert reply.status == 413 and runner.calls == []


# --------------------------------------------------------------------------------------- the wait


@pytest.mark.parametrize(("asked", "given"), [(60.0, MIN_TIMEOUT_SECONDS), (400.0, 400.0)])
def test_a_slow_start_gets_a_longer_wait_than_a_web_call(asked: float, given: float) -> None:
    runner = FakeRunner(RunResult(0, _claude_json("ok")))
    _ask(_chat("claude", runner), timeout=asked)
    assert runner.calls[0][2] == given


def test_running_out_of_time_is_a_timeout_not_a_crash() -> None:
    reply = _ask(_chat("claude", FakeRunner(RunResult(1, "", "", timed_out=True))))
    assert reply.text is None and reply.status == 408


# --------------------------------------------------------------------------------------- failing safely


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (RunResult(1, "", "error: unknown option '--tools'"), CLI_UNSUPPORTED),
        (RunResult(2, "", "Unrecognized arguments: --sandbox"), CLI_UNSUPPORTED),
        (RunResult(1, _claude_error("Invalid API key · Please run /login")), CLI_NOT_SIGNED_IN),
        (RunResult(1, "", "Not logged in. Run `codex login`."), CLI_NOT_SIGNED_IN),
        (RunResult(1, "", "401 Unauthorized"), CLI_NOT_SIGNED_IN),
        (RunResult(1, "", "something exploded"), CLI_FAILED),
        (RunResult(127, "", "", missing=True), CLI_NOT_FOUND),
        (RunResult(0, "   "), 502),
    ],
)
def test_a_failure_becomes_a_status_and_never_raises(result: RunResult, status: int) -> None:
    reply = _ask(_chat("claude", FakeRunner(result)))
    assert reply.text is None and reply.status == status and reply.error


def test_an_app_that_lacks_a_safety_switch_is_never_retried_without_it() -> None:
    runner = FakeRunner(RunResult(1, "", "error: unknown option '--tools'"))
    _ask(_chat("claude", runner))
    assert len(runner.calls) == 1


def test_a_runner_that_blows_up_is_still_a_plain_failure() -> None:
    def broken(*_args: Any) -> RunResult:
        raise OSError("disk on fire")

    reply = _ask(CliChat("claude", EXE, runner=broken, environment={}))
    assert reply.status == CLI_FAILED and "disk on fire" not in (reply.error or "")


@pytest.mark.parametrize("status", [CLI_NOT_FOUND, CLI_NOT_SIGNED_IN, CLI_UNSUPPORTED, CLI_FAILED])
def test_every_failure_has_a_sentence_that_names_the_next_click_and_no_code(status: int) -> None:
    sentence = explain_failure(status)
    assert "Settings" in sentence and str(status) not in sentence and "--" not in sentence


# --------------------------------------------------------------------------------------- the real runner


def test_the_real_runner_feeds_standard_input_and_returns_what_was_printed() -> None:
    code = "import sys; print(sys.stdin.read().upper())"
    result = run_cli([sys.executable, "-c", code], "hello", 30.0, {})
    assert result.code == 0 and result.out.strip() == "HELLO"


def test_the_real_runner_gives_the_program_only_the_environment_it_is_handed() -> None:
    code = "import os; print(os.environ.get('LEAK_CANARY', 'none'))"
    result = run_cli([sys.executable, "-c", code], "", 30.0, {"LEAK_CANARY": "set"})
    assert result.out.strip() == "set"
    other = run_cli([sys.executable, "-c", code], "", 30.0, {})
    assert other.out.strip() == "none"


def test_the_real_runner_works_in_an_empty_folder_not_the_project() -> None:
    code = "import os; print(os.getcwd()); print(len(os.listdir('.')))"
    result = run_cli([sys.executable, "-c", code], "", 30.0, {})
    lines = result.out.splitlines()
    assert Path(lines[0].strip()).resolve() != Path.cwd().resolve() and lines[1].strip() == "0"


def test_the_real_runner_stops_a_program_that_never_finishes() -> None:
    code = "import threading; threading.Event().wait(60)"
    result = run_cli([sys.executable, "-c", code], "", 1.0, {})
    assert result.timed_out is True


def test_the_real_runner_reports_a_program_that_is_not_there() -> None:
    assert run_cli(["/no/such/program-xyz"], "", 5.0, {}).missing is True


def test_the_names_a_person_sees_for_the_apps_do_not_use_the_developers_word() -> None:
    assert CLI_LABELS == {
        "claude": "Claude Code (your Claude sign-in)",
        "codex": "Codex (your ChatGPT sign-in)",
        "gemini": "Gemini (your Google sign-in)",
    }
