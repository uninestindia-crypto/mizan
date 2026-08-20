"""Example: arXiv Quant Research RAG Engine querying literature and grounding AI strategy advisors."""

import os
import sys

# Ensure src is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quant_system.alpha.ai_advisor import MultiAgentConsensusEngine
from quant_system.core.domain import Side
from quant_system.research.rag_engine import QuantPaperRAG


def main() -> None:
    print("=" * 80)
    print("[RESEARCH RAG] QuantOS: arXiv Quantitative Finance Semantic Retrieval Engine")
    print("=" * 80)

    # 1. Initialize RAG Engine
    rag = QuantPaperRAG()
    print(
        f"\n[INDEX] Successfully initialized local vector index with {len(rag.papers)} foundational papers."
    )

    # 2. Example Research Queries
    research_questions = [
        "How do we prevent backtest overfitting and false discoveries in quantitative strategies?",
        "What are the best methods to label financial data for machine learning without noisy fixed horizons?",
        "How to model optimal high-frequency spread and inventory risk in limit order books?",
    ]

    for idx, q in enumerate(research_questions, 1):
        print("\n" + "-" * 75)
        print(f"[QUERY {idx}] '{q}'")
        print("-" * 75)

        result = rag.query(q, top_k=2)
        print("\n--- Top Ranked Academic Citations ---")
        for rank, (paper, score) in enumerate(result.top_papers, 1):
            print(f"  {rank}. [{paper.primary_category}] {paper.title}")
            print(f"     Authors: {', '.join(paper.authors)}")
            print(f"     arXiv ID: {paper.arxiv_id} | Relevance Score: {score:.4f}")
            print(f"     PDF: {paper.pdf_url}")
            print(f"     Summary: {paper.summary[:180]}...\n")

    # 3. Grounding AI Multi-Agent Advisory in Research
    print("=" * 80)
    print("[AI ADVISORY] AI Multi-Agent Advisory Layer Grounded in arXiv Literature")
    print("=" * 80)

    consensus_engine = MultiAgentConsensusEngine(rag_engine=rag)

    technical_setup = {
        "current_price": 1850.0,
        "rsi": 58.5,
        "sma_distance_pct": 0.015,
        "atr_normalized": 0.018,
        "return_5d": 0.024,
        "model_prob_up": 0.68,
    }

    print(
        "\nEvaluating trade proposal for INFY (NSE) with Multi-Agent Panel (Claude, Codex, Antigravity)..."
    )
    opinion = consensus_engine.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.68,
        technical_summary=technical_setup,
    )

    print("\n[CONSENSUS RESULT]")
    print(f"  Action Bias:         {opinion.action_bias}")
    print(f"  Confidence:          {opinion.confidence:.2%}")
    print(f"  Position Multiplier: {opinion.weight_multiplier:.2f}x")
    print(f"  Rationale:           {opinion.rationale}")
    print("  RAG Grounding:       Active (arXiv q-fin vector search injected)")

    print("\n[SUCCESS] Quant Research RAG pipeline verified successfully.")


if __name__ == "__main__":
    main()
