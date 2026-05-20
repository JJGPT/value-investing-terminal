# AI And RAG Architecture

## Purpose

The AI system should help analysts reason with evidence, not produce shallow summaries. It should use Damodaran methodologies, qualitative investing frameworks, fund-letter reasoning, investment memos, valuation logic, filings, and financial data.

AI should be introduced after the core platform, data model, and valuation foundation exist.

## Knowledge Sources

The current `knowledge/` directory should be treated as the seed knowledge base:

- Valuation spreadsheets: WACC, FCFF, high-growth, stable-growth, revenue-growth, and multiples models.
- Damodaran books: valuation methodology, discount rates, lifecycle thinking, terminal value, risk premiums.
- Fund letters: owner-oriented reasoning, capital allocation, intrinsic value discipline, management quality.
- Sample analyses: memo structure, thesis development, industry analysis, valuation presentation.
- Qualitative checklist: moat, business model, competition, market size, scalability, and management prompts.

## RAG Pipeline

1. Register source document and metadata.
2. Extract text, tables, workbook formulas, and document structure.
3. Classify source type: book, filing, spreadsheet, memo, checklist, fund letter, news.
4. Chunk by semantic boundaries, not fixed page size only.
5. Attach metadata: source, author, page/sheet, section, company, method, language, topic tags.
6. Generate embeddings.
7. Store chunks, embeddings, and source offsets.
8. Retrieve with hybrid semantic plus keyword search.
9. Re-rank and package evidence for model calls.
10. Persist final AI outputs with evidence references.

## Chunking Strategy

- Books: chapter, section, paragraph clusters, definitions, formulas.
- Fund letters: topic-based chunks around capital allocation, risk, intrinsic value, management, float, compounding.
- Sample analyses: thesis, business overview, industry, financials, valuation, risks, recommendation.
- Checklists: one question or checklist item per chunk, grouped by analytical theme.
- Spreadsheets: sheet-level descriptions, input cells, output cells, formulas, assumptions, and diagnostics.
- Filings: item sections, risk factors, MD&A subsections, notes, and XBRL facts.

## Retrieval Strategy

Use custom retrieval for production:

- Structured filters for company, source type, period, document, method, and topic.
- Keyword search for exact financial terms and filing references.
- Vector search for conceptual similarity.
- Re-ranking before answer generation.
- Evidence packets with citations and source offsets.

Hosted file search can be useful for prototypes, but production needs richer metadata, provenance, and formula-aware retrieval.

## Embedding Strategy

- Use a high-quality embedding model for curated knowledge, filings, and research memos.
- Use a lower-cost embedding model for high-volume news and transient documents.
- Store embedding model, dimensions, chunk hash, source version, and extraction version.
- Re-embed only when source content or embedding configuration changes.

## AI Generation Rules

- No unsupported investment claims.
- No fake valuation calculations.
- Cite source chunks for qualitative claims.
- Cite formulas and data sources for quantitative claims.
- Separate facts, assumptions, interpretation, and recommendation language.
- Return uncertainty and missing-data warnings.

## Phase 1 AI Scope

Do not build full agents in Phase 1.

Phase 1 should prepare for AI by:

- designing document and evidence schemas;
- preserving provenance in financial data;
- storing research notes in a future-RAG-friendly shape;
- defining agent artifact contracts.

Phase 2 or 3 can add curated knowledge extraction and simple RAG question answering.
