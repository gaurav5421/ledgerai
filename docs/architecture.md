# Architecture

## Overview

LedgerAI is a single-agent system with modular internal components. The agent answers questions about public company financials using SEC EDGAR filings, with full provenance, confidence scoring, and guardrails.

**Key design principle:** Most of the intelligence is in the code *around* the LLM, not in the LLM itself. The LLM gets called once with a well-constructed prompt containing all the context it needs. Everything else — scope checking, data retrieval, metric definitions, confidence scoring, decomposition — is deterministic Python.

## System Flow

```mermaid
flowchart TD
    Q[User Query] --> FS{Follow-up\nselection?}
    FS -->|"1/2/3"| EX[Expand to\nfull query]
    FS -->|No| SG
    EX --> SG[Scope Guard]
    SG -->|Out of scope| R[Graceful Refusal\nwith suggestions]
    SG -->|In scope| CA[Context Assembly\nContextPackage]
    CA --> RET[Data Retrieval]
    RET --> KW{Keyword\nmatch?}
    KW -->|Yes| SQL[(SQLite)]
    KW -->|No| IC[LLM Intent\nClassifier]
    IC --> SQL
    CA --> MR[Metric Registry]
    CA --> DR[Domain Rules]
    CA --> EC[Entity Context]
    CA --> SC[Session Context\nprior turns]
    CA --> DEC2{Decomposition\nquery?}
    DEC2 -->|Yes| DEC[Metric Decomposition]
    DEC2 -->|No| CS
    DEC --> CS[Pre-LLM\nConfidence Check]
    CS -->|REFUSE| BAIL[Insufficient Confidence\nRefusal]
    CS -->|LOW + poor data| RETRY[Retry with\nbroader metrics]
    RETRY --> CS2[Recompute\nConfidence]
    CS -->|OK| LLM
    CS2 --> LLM[LLM Call\nor Deterministic Fallback]
    LLM --> FV{Faithfulness\nValidation}
    FV -->|Mismatch > 20%| FALLBACK[Fall back to\ndata-driven answer]
    FV -->|OK| DISC{LOW\nconfidence?}
    FALLBACK --> DISC
    DISC -->|Yes| WARN[Prepend uncertainty\ndisclaimer]
    DISC -->|No| FU
    WARN --> FU[Follow-up Generation]
    FU --> SR[Structured Response]

    style R fill:#f44,color:#fff
    style BAIL fill:#f44,color:#fff
    style SR fill:#4a4,color:#fff
```

### ASCII Flow (for non-Mermaid renderers)

```
User Query
    │
    ▼
┌──────────────┐
│  Scope Guard │ ── Out of scope? → Graceful refusal with alternatives
└──────┬───────┘
       │ In scope
       ▼
┌──────────────────────────────────────┐
│    Context Assembly → ContextPackage │
│  ┌─────────────────────────────────┐ │
│  │     Retrieval Layer             │ │
│  │  SQLite ←── keywords + LLM     │ │
│  │             intent classifier   │ │
│  └─────────────┬───────────────────┘ │
│  + Metric definitions & formulas     │
│  + Domain rules (fiscal years, etc.) │
│  + Entity context (segments, events) │
│  + Comparability rules               │
│  + Investigation session context     │
│  + Decomposition analysis (if "why") │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│    Pre-LLM Confidence Scoring        │
│  + Data availability       (35%)     │
│  + Calculation complexity  (20%)     │
│  + Temporal relevance      (15%)     │
│  + Comparability validity  (15%)     │
│  + Query ambiguity         (15%)     │
│                                      │
│  REFUSE (< 0.2) → bail out          │
│  LOW + poor data → retry broader     │
│  LOW/MEDIUM/HIGH → proceed           │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         LLM Reasoning                │
│  Single call with ContextPackage     │
│  (Gemini / Anthropic Claude)         │
│  OR deterministic fallback           │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│    Faithfulness Validation           │
│  Extract $amounts and %ages from     │
│  LLM output, cross-reference vs     │
│  provenance source data              │
│                                      │
│  > 20% mismatch → fall back to      │
│    data-driven answer                │
│  5-20% mismatch → append warning    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       Investigation Layer            │
│  + LOW confidence → uncertainty      │
│    disclaimer prepended              │
│  + Contextual follow-up generation   │
│  + Session state recording           │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       Structured Response            │
│  + Answer (with disclaimer if LOW)   │
│  + Methodology (show the math)       │
│  + Sources (filing references)       │
│  + Confidence level & score          │
│  + Verification notes (if flagged)   │
│  + Decomposition (if triggered)      │
│  + Follow-up suggestions             │
└──────────────────────────────────────┘
```

## Key Components

### Data Layer
- **SQLite** — structured financial data (5,592 line items) extracted from SEC filings
- **ChromaDB** — vector store for filing text (MD&A, risk factors, footnotes) for qualitative questions

### Context Layer
- **Metric Registry** (`src/context/metric_registry.py`) — 25 financial metrics with formulas, components, caveats, typical ranges, and comparability rules
- **Domain Rules** (`src/context/domain_rules.py`) — fiscal year mappings, seasonality notes, cross-industry comparison warnings
- **Entity Context** (`src/context/entity_context.py`) — per-company knowledge: business segments, reporting quirks, major events, comparable companies

### Guardrails
- **Scope Guard** (`src/guardrails/scope_guard.py`) — classifies queries as in-scope, partial, or out-of-scope using regex patterns
- **Confidence Scoring** (`src/guardrails/confidence.py`) — 5-factor weighted evaluation producing calibrated scores. Now runs *before* the LLM call with bail-out paths: REFUSE returns an explicit insufficient-confidence refusal; LOW with poor data availability retries with broader metrics; LOW after retry adds an uncertainty disclaimer
- **Faithfulness Validation** (`src/guardrails/validation.py`) — extracts dollar amounts and percentages from LLM output, cross-references against provenance source data. Mismatches >20% trigger fallback to data-driven answer; 5-20% mismatches append verification notes
- **Provenance Tracking** (`src/guardrails/provenance.py`) — tags every claim with source filing and calculation chain

### Investigation Layer
- **Metric Decomposition** (`src/investigation/decomposition.py`) — predefined decomposition paths for 10+ metrics; identifies primary driver of changes
- **Contextual Follow-ups** (`src/investigation/follow_ups.py`) — data-driven suggestions based on actual retrieved values, not templates
- **Session State** (`src/investigation/session.py`) — multi-turn conversation tracking with depth classification (summary → detail → comparison → decomposition)

### Agent Core
- **Orchestration** (`src/agent/core.py`) — pipeline logic connecting all components via `ContextPackage` dataclass. The `_assemble_context()` method makes the retrieval → assembly → LLM dependency chain explicit
- **ContextPackage** (`src/agent/core.py`) — dataclass holding all assembled context (data, provenance, metrics, warnings, decomposition, tickers, scope) — the single input to both confidence scoring and LLM
- **Retrieval** (`src/agent/retrieval.py`) — SQL queries for financial data, derived metric calculations, with `force_broad` mode for low-confidence retries
- **Intent Classification** (`src/agent/core.py:_classify_query_intent`) — lightweight LLM fallback when keyword matching doesn't identify trend/metric intent; keywords remain as a zero-latency fast path
- **Response** (`src/agent/response.py`) — structured output formatting

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | Gemini / Anthropic Claude | Supports both; deterministic fallback without either |
| Structured Data | SQLite | Zero infrastructure, portable, sufficient for demo scale |
| Vector Store | ChromaDB (local) | Embedded mode, no server needed |
| API | FastAPI | Async, auto-docs, Pydantic integration |
| UI | Chainlit | Polished chat UI with actions, starters, sidebar elements |
| Parsing | BeautifulSoup + lxml | SEC filings are HTML/XML |
| Tests | pytest | 187 unit + integration tests |
| Eval | Custom suite | 53 cases across 5 categories |

## Design Constraints

1. **No framework** — orchestration is explicit Python, not abstracted behind a framework
2. **Single agent** — one LLM call per query (occasionally two for decomposition or intent classification)
3. **Deterministic when possible** — metric calculations, decomposition, follow-ups are all Python, not LLM-generated
4. **Portable** — no cloud services required; everything runs locally with SQLite and ChromaDB
5. **Honest** — confidence scoring, refusals, and the failure catalog exist to show where the system works and where it doesn't
