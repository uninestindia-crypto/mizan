"""The Research screen's engine room: search, the saved library, and the one-click set-up of EmbeddingGemma 2.

No network and no model download: a pretend downloader, a pretend arXiv and a pretend embedder stand in for them.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from quant_system.research import embedding_gemma, embedding_onnx, research_service
from quant_system.research.arxiv_client import PaperMetadata
from quant_system.research.embedding_gemma import EmbeddingGemmaProvider
from quant_system.research.embedding_onnx import ModelSetupError
from quant_system.research.research_service import (
    ResearchError,
    ResearchService,
    build_arxiv_query,
    paper_view,
)


def synthetic(_: Path) -> EmbeddingGemmaProvider:
    return EmbeddingGemmaProvider(mode="synthetic")


def make_service(tmp_path: Path, **kwargs: Any) -> ResearchService:
    kwargs.setdefault("provider_factory", synthetic)
    return ResearchService(tmp_path / "model", tmp_path / "research" / "papers.json", **kwargs)


def new_paper(
    arxiv_id: str = "2610.00001", title: str = "Hedging transaction costs in option portfolios"
) -> PaperMetadata:
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=title,
        summary="We study how transaction costs change optimal hedging for option books on NSE index options.",
        authors=["A. Trader", "B. Quant"],
        published=datetime(2026, 9, 30),
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        primary_category="q-fin.RM",
    )


class FakeOnnxEmbedder:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float((sum(map(ord, t)) + i * 31) % 17 + 1) for i in range(768)] for t in texts]


@pytest.fixture
def real_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Makes the downloaded-model route work without any model file."""
    monkeypatch.setattr(embedding_onnx, "OnnxEmbedder", FakeOnnxEmbedder)


# ----------------------------------------------------------------------------- search


def test_a_question_finds_the_paper_that_answers_it(tmp_path: Path) -> None:
    result = make_service(tmp_path).search(
        "How do I avoid backtest overfitting with the Sharpe ratio?"
    )
    assert result["results"], "the built-in library always has something to show"
    top = result["results"][0]
    assert "Deflated Sharpe" in top["title"]
    assert set(top) == {
        "id",
        "title",
        "authors",
        "more_authors",
        "year",
        "field",
        "summary",
        "link",
        "match_percent",
    }
    assert 0 < top["match_percent"] <= 100 and top["field"] == "Statistical finance"
    assert result["library"]["papers"] == 5


def test_the_answer_says_it_used_keyword_matching_when_the_model_is_not_there(
    tmp_path: Path,
) -> None:
    result = make_service(tmp_path).search("order book spread")
    assert result["engine"]["by_meaning"] is False
    assert result["engine"]["label"].startswith("Built-in keyword matching")


def test_the_answer_says_it_matched_by_meaning_once_the_model_runs(
    tmp_path: Path, real_engine: None
) -> None:
    service = make_service(
        tmp_path, provider_factory=lambda d: EmbeddingGemmaProvider(mode="onnx", model_dir=d)
    )
    result = service.search("order book spread")
    assert result["engine"] == {
        "by_meaning": True,
        "label": "EmbeddingGemma 2 (running on this computer)",
    }


@pytest.mark.parametrize(
    ("question", "code"),
    [("", "EMPTY_QUESTION"), ("   ", "EMPTY_QUESTION"), ("x" * 501, "QUESTION_TOO_LONG")],
)
def test_a_bad_question_gets_a_plain_sentence(tmp_path: Path, question: str, code: str) -> None:
    with pytest.raises(ResearchError) as caught:
        make_service(tmp_path).search(question)
    assert caught.value.code == code and caught.value.status == 422
    assert not any(
        word in caught.value.message.lower() for word in ("api", "json", "schema", "endpoint")
    )


def test_how_many_results_is_kept_to_a_sensible_range(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    assert len(service.search("risk", top_k=0)["results"]) == 1
    assert len(service.search("risk", top_k=99)["results"]) <= 5  # only five papers exist


def test_a_paper_is_shown_with_a_short_author_list() -> None:
    many = PaperMetadata(
        arxiv_id="1",
        title="T",
        summary="S",
        authors=[f"A{i}" for i in range(9)],
        published=datetime(2020, 1, 2),
        pdf_url="https://x/1.pdf",
        primary_category="q-fin.XX",
    )
    view = paper_view(many, 0.5)
    assert view["authors"] == [f"A{i}" for i in range(6)] and view["more_authors"] == 3
    assert (
        view["year"] == 2020 and view["field"] == "Finance research" and view["match_percent"] == 50
    )
    assert (
        paper_view(many, 1.7)["match_percent"] == 100 and paper_view(many, -1)["match_percent"] == 0
    )


# ----------------------------------------------------------------------------- looking on arXiv


def test_the_arxiv_search_is_built_from_the_words_of_the_question() -> None:
    query = build_arxiv_query("How do I hedge option transaction costs?")
    assert query is not None
    assert (
        "all:hedge" in query
        and "all:option" in query
        and "all:transaction" in query
        and "cat:q-fin.RM" in query
    )
    assert build_arxiv_query("the and of") is None


def test_new_papers_from_arxiv_are_added_shown_and_remembered(tmp_path: Path) -> None:
    asked: list[str] = []

    def fetcher(query: str, count: int) -> list[PaperMetadata]:
        asked.append(query)
        return [new_paper()]

    service = make_service(tmp_path, fetcher=fetcher)
    result = service.search("hedging option transaction costs", online=True)
    assert result["results"][0]["title"].startswith("Hedging transaction costs")
    assert result["notes"] == ["Added 1 new paper from arXiv to your library."]
    assert result["library"]["papers"] == 6 and asked

    # a fresh start finds it again with no internet
    again = make_service(
        tmp_path, fetcher=lambda q, c: (_ for _ in ()).throw(AssertionError("must not ask"))
    )
    assert again.search("hedging option transaction costs")["results"][0]["id"] == "2610.00001"
    assert again.status()["library"]["papers"] == 6


def test_no_internet_is_said_plainly_and_the_saved_papers_still_answer(tmp_path: Path) -> None:
    def offline(query: str, count: int) -> list[PaperMetadata]:
        raise ResearchError(
            503,
            "NO_INTERNET",
            "Could not reach arXiv. Check your internet connection. Your saved papers still work.",
        )

    result = make_service(tmp_path, fetcher=offline).search("deflated sharpe", online=True)
    assert result["results"] and "Could not reach arXiv" in result["notes"][0]


def test_papers_already_in_the_library_are_not_added_twice(tmp_path: Path) -> None:
    first = new_paper()
    service = make_service(tmp_path, fetcher=lambda q, c: [first])
    service.search("hedging option costs", online=True)
    second = service.search("hedging option costs", online=True)
    assert second["notes"] == ["arXiv had no new papers for this question."]
    assert second["library"]["papers"] == 6
    assert len(json.loads((tmp_path / "research" / "papers.json").read_text(encoding="utf-8"))) == 1


def test_a_question_with_no_usable_words_does_not_go_online(tmp_path: Path) -> None:
    service = make_service(
        tmp_path, fetcher=lambda q, c: (_ for _ in ()).throw(AssertionError("must not ask"))
    )
    assert "more words" in service.search("it is the", online=True)["notes"][0]


def test_a_damaged_library_file_is_ignored_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "research" / "papers.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert make_service(tmp_path).search("sharpe")["library"]["papers"] == 5
    path.write_text(json.dumps([{"arxiv_id": "only-this"}, "junk", None]), encoding="utf-8")
    assert make_service(tmp_path).search("sharpe")["library"]["papers"] == 5


# ----------------------------------------------------------------------------- the one-click set-up


def wait(service: ResearchService) -> dict[str, Any]:
    service.wait(5)
    return service.setup_snapshot()


def test_status_before_anything_is_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    status = make_service(tmp_path).status()
    assert status["engine"]["state"] == "NEEDS_DOWNLOAD" and status["engine"]["by_meaning"] is False
    assert status["engine"]["download_mb"] == 330
    assert (
        status["engine"]["label"]
        == "Built-in keyword matching (EmbeddingGemma 2 has not been downloaded yet)"
    )
    assert status["library"]["papers"] == 5 and status["setup"]["state"] == "IDLE"


def test_setup_downloads_then_prepares_then_switches_search_to_meaning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real_engine: None
) -> None:
    states = iter(["NEEDS_DOWNLOAD", "NEEDS_DOWNLOAD", "READY", "READY", "READY"])
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: next(states, "READY")
    )
    seen: list[dict[str, Any]] = []

    def downloader(model_dir: Path, *, progress: Any, cancelled: Any) -> None:
        progress(100 * 1024 * 1024, 330 * 1024 * 1024)
        seen.append(service.setup_snapshot())
        progress(330 * 1024 * 1024, 330 * 1024 * 1024)

    service = make_service(
        tmp_path,
        downloader=downloader,
        provider_factory=lambda d: EmbeddingGemmaProvider(mode="onnx", model_dir=d),
    )
    assert service.start_setup()["state"] == "DOWNLOADING"
    final = wait(service)
    assert (
        seen[0]["state"] == "DOWNLOADING"
        and seen[0]["percent"] == 30
        and "100 of 330 MB" in seen[0]["message"]
    )
    assert final["state"] == "DONE" and final["percent"] == 100 and final["error"] is None
    assert "matches by meaning" in final["message"]
    assert service.search("order book spread")["engine"]["by_meaning"] is True


def test_asking_to_start_twice_runs_one_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    release = threading.Event()
    calls: list[int] = []

    def downloader(model_dir: Path, *, progress: Any, cancelled: Any) -> None:
        calls.append(1)
        release.wait(5)
        raise ModelSetupError("NO_INTERNET", "x")

    service = make_service(tmp_path, downloader=downloader)
    service.start_setup()
    second = service.start_setup()
    assert second["state"] == "DOWNLOADING"
    release.set()
    wait(service)
    assert calls == [1]


def test_a_failed_download_says_why_in_plain_words_and_can_be_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    attempts = {"n": 0}

    def downloader(model_dir: Path, *, progress: Any, cancelled: Any) -> None:
        attempts["n"] += 1
        raise ModelSetupError(
            "NO_INTERNET",
            "Could not reach the download site. Check your internet connection and try again.",
        )

    service = make_service(tmp_path, downloader=downloader)
    service.start_setup()
    failed = wait(service)
    assert failed["state"] == "FAILED"
    assert failed["error"] == {
        "code": "NO_INTERNET",
        "message": "Could not reach the download site. Check your internet connection and try again.",
    }
    service.start_setup()
    wait(service)
    assert attempts["n"] == 2
    # search still works the whole time
    assert service.search("sharpe")["results"]


def test_cancelling_is_reported_as_cancelled_not_as_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    started = threading.Event()

    def downloader(model_dir: Path, *, progress: Any, cancelled: Any) -> None:
        started.set()
        for _ in range(500):
            if cancelled():
                raise ModelSetupError(
                    "CANCELLED", "The download was cancelled. You can start it again later."
                )
            threading.Event().wait(0.01)

    service = make_service(tmp_path, downloader=downloader)
    service.start_setup()
    started.wait(2)
    service.cancel_setup()
    final = wait(service)
    assert (
        final["state"] == "CANCELLED"
        and final["error"] is None
        and "start it again" in final["message"]
    )


def test_setup_when_the_model_is_already_there_does_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(research_service, "real_model_status", lambda model_dir=None: "READY")
    service = make_service(
        tmp_path,
        downloader=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not download")),
    )
    assert service.start_setup()["state"] == "DONE"


def test_a_download_that_cannot_start_is_never_announced_as_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    service = make_service(
        tmp_path, downloader=lambda model_dir, **k: None
    )  # "finishes", but the factory gives the substitute
    service.start_setup()
    final = wait(service)
    assert final["state"] == "FAILED" and final["error"]["code"] == "ENGINE_START_FAILED"
    assert "could not start" in final["message"] and "keyword matching" in final["message"]


def test_a_copy_of_the_app_without_the_runtime_says_so_without_instructions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NOT_INSTALLED"
    )
    monkeypatch.setattr(embedding_onnx, "runtime_available", lambda: False)
    with pytest.raises(ResearchError) as caught:
        make_service(tmp_path).start_setup()
    assert caught.value.code == "NOT_AVAILABLE" and caught.value.status == 409
    assert "not available in this copy" in caught.value.message
    assert not any(
        word in caught.value.message.lower() for word in ("pip", "install", "terminal", "command")
    )


def test_an_unexpected_error_in_setup_is_logged_and_shown_as_a_plain_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        research_service, "real_model_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )

    def downloader(model_dir: Path, *, progress: Any, cancelled: Any) -> None:
        raise RuntimeError("Traceback (most recent call last): secret path C:\\Users\\x")

    service = make_service(tmp_path, downloader=downloader)
    service.start_setup()
    final = wait(service)
    assert final["state"] == "FAILED" and final["error"]["code"] == "SETUP_FAILED"
    assert "Traceback" not in final["message"] and "C:\\" not in final["message"]


def test_the_provider_status_helper_is_the_one_the_screen_reads() -> None:
    assert research_service.real_model_status is embedding_gemma.real_model_status
