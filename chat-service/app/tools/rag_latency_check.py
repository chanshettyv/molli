"""Latency + sanity harness for the RAG answer pipeline (manual, live GCP).

Runs ~20 real employee questions end-to-end (embed -> retrieve -> chunk store
-> Gemini -> cited answer) and reports per-query and aggregate latency against
the <30s first-response budget. Also prints each answer + citations so you can
eyeball grounding quality.

NOT a CI test — it needs live Vertex AI + Firestore + a populated index/store.
Run from chat-service:
    uv run python -m app.tools.rag_latency_check
"""

from __future__ import annotations

import statistics
import time

from app.tools.rag_answer import answer_with_citations

BUDGET_SECONDS = 30.0

# 20 real questions spanning the audit's top needs across IT / Ops / HR.
QUESTIONS = [
    "How do I reset my Google password?",
    "How do I recover my account if I'm locked out?",
    "How do I connect to the office printer?",
    "My computer won't find the printer, what do I do?",
    "How do I get added to an email distribution list?",
    "How do I request a new laptop?",
    "How do I request access in Entrata?",
    "How do I process a refund in Entrata?",
    "How do I reverse a payment in Entrata?",
    "Why do my scheduled charges keep expiring?",
    "How do I reset a resident's portal password?",
    "A resident can't log into the resident portal, what do I do?",
    "How do I switch a guarantor mid-lease?",
    "How do I correct an address on a renewal lease?",
    "How do I upload utility charges?",
    "What are my benefits options?",
    "How much PTO do I accrue?",
    "How do I connect to the VPN?",
    "How do I release a message held in Mimecast?",
    "How do I update office hours for a property?",
]


def main() -> None:
    latencies: list[float] = []
    hits = 0
    no_context = 0

    for i, q in enumerate(QUESTIONS, 1):
        t0 = time.perf_counter()
        ans = answer_with_citations(q)
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)

        flag = "OK " if elapsed <= BUDGET_SECONDS else "SLOW"
        if ans.no_context:
            no_context += 1
            status = "NO-CONTEXT"
        elif ans.citations:
            hits += 1
            status = f"{len(ans.citations)} citation(s)"
        else:
            status = "answer, no citations"

        print("=" * 80)
        print(f"[{i}/{len(QUESTIONS)}] {elapsed:5.2f}s  {flag}  {status}")
        print(f"Q: {q}")
        print(f"A: {ans.text[:300]}{'...' if len(ans.text) > 300 else ''}")
        for c in ans.citations:
            print(f"   [{c.number}] {c.title} -> {c.url}")
        print()

    print("=" * 80)
    print("SUMMARY")
    print(f"  queries:        {len(QUESTIONS)}")
    print(f"  with citations: {hits}")
    print(f"  no-context:     {no_context}")
    print(f"  min  latency:   {min(latencies):.2f}s")
    print(f"  mean latency:   {statistics.mean(latencies):.2f}s")
    print(f"  median latency: {statistics.median(latencies):.2f}s")
    print(f"  max  latency:   {max(latencies):.2f}s")
    over = [l for l in latencies if l > BUDGET_SECONDS]
    print(f"  over {BUDGET_SECONDS:.0f}s budget: {len(over)}")
    verdict = "PASS" if not over else f"FAIL ({len(over)} over budget)"
    print(f"  latency budget: {verdict}")


if __name__ == "__main__":
    main()
