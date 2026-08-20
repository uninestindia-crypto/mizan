"""Unit tests for arXiv quantitative research client and QuantPaperRAG semantic engine."""

from datetime import datetime

from quant_system.alpha.ai_advisor import ClaudeCLIAdvisor, MultiAgentConsensusEngine
from quant_system.core.domain import Side
from quant_system.research.arxiv_client import ArxivClient, PaperMetadata
from quant_system.research.rag_engine import QuantPaperRAG


def test_paper_metadata_citation() -> None:
    paper = PaperMetadata(
        arxiv_id="1801.01831",
        title="Advances in Financial Machine Learning",
        summary="Triple-barrier labeling and purged cross validation.",
        authors=["Marcos López de Prado"],
        published=datetime(2018, 1, 6),
        pdf_url="https://arxiv.org/pdf/1801.01831.pdf",
        primary_category="q-fin.CP",
    )
    citation = paper.citation
    assert "López de Prado" in citation
    assert "1801.01831" in citation
    assert "q-fin.CP" in citation


def test_arxiv_client_parse_atom_feed() -> None:
    client = ArxivClient()
    mock_atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Order Flow Imbalance and Microstructure Alpha</title>
        <summary>We study high-frequency order flow imbalance in limit order books.</summary>
        <published>2023-01-15T12:00:00Z</published>
        <author><name>Alice Smith</name></author>
        <link title="pdf" href="http://arxiv.org/pdf/2301.12345v1" />
        <arxiv:primary_category term="q-fin.TR" />
      </entry>
    </feed>
    """
    papers = client.parse_atom_feed(mock_atom_xml)
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2301.12345v1"
    assert papers[0].title == "Order Flow Imbalance and Microstructure Alpha"
    assert papers[0].authors == ["Alice Smith"]
    assert papers[0].primary_category == "q-fin.TR"


def test_quant_paper_rag_semantic_search() -> None:
    rag = QuantPaperRAG()

    # Query about Deflated Sharpe Ratio / Overfitting
    result = rag.query(
        "How to prevent backtest overfitting and correct Sharpe ratio bias?", top_k=2
    )
    assert len(result.top_papers) > 0
    top_paper = result.top_papers[0][0]
    assert "Sharpe" in top_paper.title or "Machine Learning" in top_paper.title
    assert len(result.citations) > 0
    assert len(result.synthesized_context) > 50

    # Query about Limit Order Books & Microstructure
    lob_result = rag.query("limit order book optimal bid ask spread market making", top_k=2)
    assert len(lob_result.top_papers) > 0
    top_lob_paper = lob_result.top_papers[0][0]
    assert "Avellaneda" in top_lob_paper.authors[0] or "order book" in top_lob_paper.title.lower()


def test_ai_advisor_with_rag_grounding() -> None:
    rag = QuantPaperRAG()
    advisor = ClaudeCLIAdvisor(rag_engine=rag)

    opinion = advisor.evaluate_opportunity(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.72,
        technical_summary={"rsi": 58.0, "atr_normalized": 0.02},
    )

    assert opinion.action_bias == "BULLISH"
    assert opinion.confidence >= 0.70
    assert opinion.metadata.get("rag_grounding_used") is True

    # Test Consensus with RAG
    consensus = MultiAgentConsensusEngine(rag_engine=rag)
    consensus_opinion = consensus.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.70,
        technical_summary={"rsi": 58.0, "atr_normalized": 0.02},
    )
    assert consensus_opinion.action_bias == "BULLISH"
    assert consensus_opinion.weight_multiplier > 0.0
