# Architecture

## Overview

LedgerAI is a single-agent system with modular internal components. The agent answers questions about public company financials using SEC EDGAR filings, with full provenance, confidence scoring, and guardrails.

## System Flow

```
User Query
    │
    ▼
┌──────────────┐
│  Scope Guard │ ── Out of scope? → Graceful refusal with alternatives
└──────┬───────┘
       │ In scope
       ▼
┌──────────────┐
│ Query Router │ ── Determines: SQL (numbers), Vector (text), or Both
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│         Retrieval Layer              │
│  ┌─────────┐     ┌────────────────┐ │
│  │   SQL   │     │ Vector Search  │ │
│  │ (SQLite)│     │  (ChromaDB)    │ │
│  └────┬────┘     └───────┬────────┘ │
└───────┼──────────────────┼──────────┘
        │                  │
        ▼                  ▼
┌──────────────────────────────────────┐
│       Context Assembly               │
│  + Metric definitions & formulas     │
│  + Domain rules (fiscal years, etc.) │
│  + Entity context (segments, events) │
│  + Comparability rules               │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         LLM Reasoning                │
│  Single call with full context       │
│  (Anthropic Claude API)              │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       Output Validation              │
│  + Sanity checks on values           │
│  + Cross-reference with database     │
│  + Internal consistency checks       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       Confidence Scoring             │
│  + Data availability                 │
│  + Calculation complexity            │
│  + Temporal relevance                │
│  + Comparability validity            │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       Structured Response            │
│  + Answer                            │
│  + Methodology (show the math)       │
│  + Sources (filing references)       │
│  + Confidence level & score          │
│  + Follow-up suggestions             │
└──────────────────────────────────────┘
```

## Key Components

### Data Layer
- **SQLite** — structured financial data (revenue, margins, EPS, etc.) extracted from SEC filings
- **ChromaDB** — vector store for filing text (MD&A, risk factors, footnotes) used for qualitative questions

### Context Layer
- **Metric Registry** — structured definitions for 20+ financial metrics with formulas, caveats, and comparability rules
- **Domain Rules** — fiscal year mappings, seasonality, comparison validity rules
- **Entity Context** — per-company context: segments, reporting quirks, major events

### Guardrails
- **Scope Guard** — classifies queries as in-scope, partially in-scope, or out-of-scope
- **Confidence Scoring** — evaluates answer reliability on multiple dimensions
- **Provenance Tracking** — tags every claim with source filing and calculation chain
- **Output Validation** — sanity checks on calculated values

### Agent Core
- **Query Router** — determines retrieval strategy (SQL, vector, or hybrid)
- **Context Assembler** — combines retrieved data with metric definitions and domain rules
- **LLM Reasoning** — single Anthropic API call with well-constructed prompt
- **Response Formatter** — structures output with answer, methodology, sources, confidence

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | Anthropic Claude (via Python SDK) | Strong reasoning, tool use support |
| Structured data | SQLite | Zero infrastructure, portable, sufficient for demo scale |
| Vector store | ChromaDB (local) | Embedded mode, no server needed |
| API | FastAPI | Async, auto-docs, Pydantic integration |
| UI | Streamlit | Fast to build, good enough for demos |
| Parsing | BeautifulSoup + lxml | SEC filings are HTML/XML |
