# RAG retrieval-quality check (Phase 1 de-risking spike)

**Date:** 2026-06-12
**Author:** Kautilya
**Index:** Vertex AI Vector Search, ~934 articles / ~2,500 chunks (full D360 corpus)
**Method:** 5 known employee questions from the ticket-audit "top D360 article
needs" run through the live retrieval path (`embed_query` with `RETRIEVAL_QUERY`
→ nearest-neighbour, top-5). Judgment call per question, no automated eval.
Script: `scripts/spikes/rag_retrieval_check.ipynb` (logic also in
`sync-job/sync_job/rag_retrieval_check.py`).

Note on scores: index uses DOT_PRODUCT on normalised embeddings (≈ cosine).
**Higher distance = more similar.** Absolute values aren't comparable across
different queries; what matters is rank and the gap between #1 and the rest.

## Verdicts

| # | Question | Verdict | Top hit | Notes |
|---|----------|---------|---------|-------|
| 1 | How do I reset my Google password? | **MISS** | Google 2-Step Verification (0.61) | Right article (Google/Gmail password reset) not in top 5. Surfaced 2SV, *social media* password, *resident portal* password instead. |
| 2 | How do I connect to the office printer? | **MISS** | Accessing the VPN (0.57) | No printer article anywhere in top 5. VPN, Entrata password, desk reservations, lock-sync. |
| 3 | How do I request access in Entrata? | **PARTIAL** | Geokey sync from Entrata (0.74) | All hits Entrata-flavoured (category routing works) but none is an access/permissions-request doc — got password-reset + portal-setup content. |
| 4 | How do I process a refund or reversal in Entrata? | **HIT** | Entrata: How to Void or Refund a Payment (0.77) | Correct article at #1 with a clear margin. |
| 5 | Resident can't log into the resident portal? | **HIT** | Entrata: How to Reset a Resident's Portal Password (0.70) | Correct, plus relevant portal/registration articles fill the rest. |

**Tally: 2 hit / 1 partial / 2 miss.**

## Key finding: misses are content gaps, not pipeline failures

The three weak results (Q1 Google password, Q2 printer, Q3 Entrata access) are
**exactly** the articles the ticket audit flagged as not yet existing in D360
(`exists_in_d360: N — needs creating`):

- *Google password reset and account recovery* — audit's single highest-impact
  IT article (29 tickets). Not found.
- *Connecting to office printers* (17 tickets). Not found.
- *Entrata: requesting access* (116 tickets — the biggest Ops cluster). Not found.

Where the target article **does** exist (Q4 refund, Q5 portal login), retrieval
finds it convincingly at #1 with a healthy score margin. So the embedding +
chunking + search pipeline is working; retrieval quality is currently **gated on
content coverage**, not on the retrieval mechanism. The knowledge base has holes
precisely where the audit predicted them.

Implication: the highest-leverage next step for retrieval quality is **content
creation by the SMEs** (the audit's article list), not retrieval tuning.

## Secondary observations (follow-ups, not blockers)

- **Title-only `::0` chunks** repeatedly appear as top hits. These are the
  article title/intro as a standalone short chunk; they match on title keywords
  but carry little body content. Candidate fix: prepend the article title /
  parent heading to each body chunk so context isn't isolated in a weak stub.
  Capture as a **Phase 1 chunking follow-up** — do not rebuild now.
- **Semantic collision among "password" articles.** Q1 surfaced social-media,
  2SV, and resident-portal password articles for a *Google* password query.
  There are many password-adjacent articles; nearest-neighbour alone can't
  disambiguate intent. Phase 2 mitigations: metadata filtering by category, or a
  re-ranking step, or letting the LLM disambiguate from several candidates.
- **Metadata is clean.** Titles, URLs, and section headings are correct and
  populated across all results. No metadata defects found. (Citation links will
  work in Phase 2.)
- **Chunk sizing looks reasonable.** No obviously-truncated or giant chunks in
  the sample; sections map sensibly to headings.

## Go / no-go for Phase 2 prompt chain

**Conditional GO.** Build the Phase 2 prompt chain on this retrieval layer — the
pipeline is sound, metadata supports citations, and where content exists,
retrieval is good. Two conditions:

1. **Treat content coverage as the #1 retrieval-quality lever.** Prioritise the
   SME-authored articles from the audit (Google password reset, printers, Entrata
   access first — highest ticket volume). Until they exist, Molli will miss the
   top IT/Ops questions regardless of prompt quality.
2. **Plan for disambiguation in the prompt chain.** Pass top-k (not top-1) to the
   LLM and let it choose / synthesise, since nearest-neighbour surfaces several
   plausibly-relevant chunks (esp. for password-type queries). A category-filtered
   retrieval or re-rank is a likely Phase 2 addition.

Do **not** block Phase 2 on retrieval tuning. The chunking and collision issues
are real but incremental; they don't change the architecture and are better
addressed once there's a prompt chain and real answers to evaluate against.

## Phase 1 follow-up tickets to file

- [ ] Chunking: prepend title/heading context to body chunks; re-evaluate
      title-only `::0` chunk behaviour.
- [ ] Flag content gaps to SMEs: Google password reset, office printers, Entrata
      access-request articles do not exist / are not retrievable. (Ties to the
      audit's article-creation list.)
- [ ] Phase 2 design note: pass top-k to the LLM; consider category-filtered
      retrieval or re-ranking for disambiguation.
