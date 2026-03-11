# LedgerAI: Production-Ready AI Agent for Financial Services
## Complete Implementation, Publishing & Content Plan

---

## Project Overview

**What:** A reference implementation of a production-ready AI agent that answers questions about public company financials using SEC EDGAR filings — demonstrating the reliability, guardrails, and grounding architecture that most AI agent projects lack.

**Why it matters:** This project serves three purposes simultaneously:
1. **Portfolio piece** — tangible proof you can build agents that work in regulated, data-heavy domains
2. **Lead generation** — the GitHub repo and blog post attract prospects who have the exact problem you solve
3. **Product discovery** — the patterns you build here become the foundation for a productized offering

**Use case:** An agent that answers questions about public company financials (revenue trends, margin analysis, segment breakdowns) with full provenance, confidence scoring, and graceful failure handling.

**Target dataset:** SEC EDGAR 10-Q and 10-K filings for 10–15 well-known public companies (Apple, Microsoft, JPMorgan, etc.)

---

## Architecture Decision Records (ADRs)

### ADR-001: Single Agent vs. Multi-Agent System

**Decision:** Single agent with modular internal components and tool-calling.

**Context:** The system performs multiple functions — query understanding, data retrieval (SQL + vector), calculation, guardrail checking, confidence scoring, response formatting, and follow-up suggestions. This raises the question of whether these should be separate agents coordinating with each other.

**Why single agent:**

- **Debuggability.** When something goes wrong in a multi-agent system, you have to trace which agent failed, what it passed downstream, and whether the failure was in the handoff or the execution. A single agent with modular internal components lets you trace every decision through one call chain. For a project whose entire thesis is reliability and auditability, this is critical.
- **Latency.** Every agent-to-agent handoff is another LLM round trip. A multi-agent answer to "What was Apple's gross margin?" could take 8–12 seconds across multiple LLM calls. A single agent with deterministic tooling does it in 2–3 seconds. For demos, this difference is visceral.
- **The complexity is in context, not coordination.** The hard problems here are metric definitions, guardrail logic, and confidence scoring. These are context problems, not delegation problems. Adding more agents doesn't make the metric registry better — it just adds communication overhead.
- **Scope discipline.** Multi-agent systems are seductive to build but brutal to ship. You'd spend weeks on inter-agent protocols, shared state management, and failure handling between agents — engineering effort with zero content or business value for this project.

**What single agent with tools looks like:**

The LLM gets called once (or occasionally twice for complex decomposition), but it's surrounded by deterministic code:

```
User Query
    → Scope Guard (Python — is this in-scope?)
    → Query Router (Python — SQL, vector, or both?)
    → Retrieval Layer (SQL + vector search)
    → Context Assembler (attach metric definitions, domain rules, entity context)
    → LLM Call (single, well-constructed prompt with everything it needs)
    → Output Validation (Python — sanity checks, consistency)
    → Confidence Scoring (Python — structured evaluation, not vibes)
    → Structured Response
```

Most of the intelligence is in the code around the LLM, not in multiple LLMs talking to each other.

**When to reconsider:** If you productize this and need genuinely autonomous subtasks (one agent researching while another analyzes industry trends, a third synthesizing both) or agents with different security boundaries (write-access agent separate from user-facing agent), multi-agent becomes justified. That's a v2 decision.

**Blog post angle:** "Why we chose single-agent over multi-agent" is a strong section in the blog post. It goes against current hype and shows you're making architecture decisions based on the problem, not the trend.

---

### ADR-002: No Agent Framework (No ADK, LangGraph, CrewAI, etc.)

**Decision:** Build directly on LLM API calls (Anthropic Python SDK) with custom Python orchestration. No agent framework.

**Context:** The current landscape includes Google ADK, LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, and others. These frameworks provide abstractions for agent orchestration, tool management, state handling, and multi-agent coordination. The question is whether using one would accelerate this project.

**Why no framework:**

- **Transparency is the product.** Your whole thesis is "I understand what makes agents reliable in production." If you wrap that in a framework, the framework makes the architecture decisions, not you. A prospect looking at your repo should see your guardrail design, your confidence scoring, your metric registry — not ADK configuration files. Every piece should be visible, explainable, and intentional.
- **Orthogonal learning curve.** Time spent learning ADK's event-driven runtime, session management patterns, or LangGraph's graph-based state machines is time not spent on the metric registry, confidence scoring, and failure catalog. That's framework overhead with zero content or business value.
- **Dependency risk.** Agent frameworks are evolving rapidly. ADK's developer experience is still early-stage. If the framework changes its API, your reference implementation breaks. Direct API calls to Claude or GPT are stable and well-documented.
- **Portability.** Your target clients might be on Azure, AWS, GCP, or their own infrastructure. A project built on Google ADK signals "Google ecosystem." A project built on direct API calls with clean Python signals "I can work with whatever you have." This matters for consulting and sales.
- **The orchestration is simple.** Your agent's flow is: classify query → retrieve data → assemble context → call LLM → validate output → score confidence → format response. That's ~100-150 lines of orchestration code. A framework adds abstraction around something that doesn't need abstracting.

**What the stack looks like:**

```
anthropic Python SDK (LLM calls)
    + Python functions (tools: SQL queries, metric lookups, vector search)
    + Your guardrail logic (scope checking, validation, confidence)
    + Your response formatting
    + FastAPI (API layer)
    + Chainlit (demo UI)
```

No framework in between. Every decision is visible in the code.

**What frameworks solve that you don't need:**
- Multi-agent coordination → you have one agent
- Complex state machines with branching/looping → your flow is linear
- Managed deployment to cloud → you're deploying a Chainlit demo
- Session persistence across millions of users → you're demoing to prospects

**When to reconsider:** If you productize this into a platform with multiple agent configurations per client, persistent sessions, cloud deployment at scale, and multi-agent coordination — then LangGraph or ADK earns its weight. Evaluate frameworks based on actual production needs at that point, not speculative ones now.

**Blog post angle:** Another strong section — "Why we skipped every agent framework" — that demonstrates first-principles thinking. Show the 100-line orchestration core and let readers see how simple the actual coordination is when you strip away unnecessary abstraction.

---

## Phase 0: Foundation & Setup (Week 1)

### 0.1 — IP Boundary Checklist
- [ ] Review your Equifax employment agreement's IP assignment clause
- [ ] Confirm: all work happens on personal machine, personal GitHub, personal cloud accounts
- [ ] Confirm: zero overlap with Equifax data, schemas, LookML code, or internal documentation
- [ ] Choose a sub-domain clearly distinct from your Equifax work (public company financials vs. credit analytics)

### 0.2 — Repository Setup
- [ ] Create GitHub repo: `ledgerai` (or similar — short, memorable, descriptive)
- [ ] Initialize with a clear README that frames the "why" before the "how"
- [ ] Set up the project structure:

```
ledgerai/
├── README.md
├── LICENSE                    # MIT recommended for max visibility
├── .env.example               # Template for API keys (never commit .env)
├── .gitignore
├── requirements.txt
├── pyproject.toml
│
├── docs/
│   ├── architecture.md        # System design overview
│   ├── adrs/
│   │   ├── 001-single-agent.md    # Why single agent, not multi-agent
│   │   └── 002-no-framework.md    # Why no ADK/LangGraph/CrewAI
│   ├── guardrails.md          # Guardrail design philosophy & catalog
│   ├── failure-catalog.md     # Documented failure modes and how agent handles them
│   └── metrics-dictionary.md  # All metric definitions the agent knows
│
├── data/
│   ├── raw/                   # Raw SEC filings (gitignored, downloaded via script)
│   ├── processed/             # Parsed and structured financial data
│   └── context/               # Metric definitions, domain rules, guardrail configs
│
├── src/
│   ├── ingestion/
│   │   ├── edgar_client.py    # SEC EDGAR API client
│   │   ├── filing_parser.py   # Extract structured data from filings
│   │   └── data_store.py      # SQLite storage layer
│   │
│   ├── context/
│   │   ├── metric_registry.py # Metric definitions, formulas, caveats
│   │   ├── domain_rules.py    # Business rules and domain constraints
│   │   └── entity_context.py  # Company-specific context (fiscal year timing, segments, etc.)
│   │
│   ├── agent/
│   │   ├── core.py            # Main agent orchestration
│   │   ├── retrieval.py       # RAG pipeline for filing content
│   │   ├── reasoning.py       # Chain-of-thought and calculation logic
│   │   └── response.py        # Response formatting and structuring
│   │
│   ├── guardrails/
│   │   ├── scope_guard.py     # Prevents out-of-domain answers
│   │   ├── confidence.py      # Confidence scoring and thresholds
│   │   ├── provenance.py      # Source attribution and data lineage
│   │   └── validation.py      # Output validation and sanity checks
│   │
│   ├── investigation/
│   │   ├── workflows.py       # Structured follow-up paths
│   │   └── decomposition.py   # Metric decomposition logic
│   │
│   └── api/
│       ├── main.py            # FastAPI application
│       └── models.py          # Request/response schemas
│
├── ui/
│   └── app.py                 # Chainlit demo interface
│
├── tests/
│   ├── test_guardrails.py     # Guardrail unit tests (critical — test what the agent refuses)
│   ├── test_confidence.py     # Confidence scoring tests
│   ├── test_calculations.py   # Financial calculation accuracy tests
│   └── test_scenarios.py      # End-to-end scenario tests
│
├── eval/
│   ├── test_cases.json        # Curated evaluation set
│   ├── run_eval.py            # Evaluation harness
│   └── results/               # Eval run outputs
│
└── scripts/
    ├── download_filings.py    # Fetch filings from EDGAR
    ├── seed_data.py           # Initial data processing pipeline
    └── demo.py                # Quick demo script
```

### 0.3 — Environment & Dependencies
- [ ] Python 3.11+
- [ ] Core dependencies: `fastapi`, `uvicorn`, `anthropic` (or `openai`), `sqlite3` (stdlib), `httpx`
- [ ] Retrieval: `chromadb` or `qdrant-client` (local mode)
- [ ] Parsing: `beautifulsoup4`, `lxml` for EDGAR HTML filings
- [ ] UI: `chainlit`
- [ ] Testing: `pytest`, `pytest-asyncio`
- [ ] Set up pre-commit hooks (black, ruff, mypy)

### 0.4 — README v1 (Write This First)
The README is your most important marketing asset. Write it before the code. Structure:

1. **Hook** — One paragraph: "Most AI agents fail in production because they lack domain context, guardrails, and the ability to say 'I don't know.' This project demonstrates what a production-ready agent looks like in financial services."
2. **What it does** — 3-4 bullet points showing the agent's capabilities
3. **What makes it different** — Emphasize the reliability layer, not the RAG pipeline
4. **Architecture decisions** — "Why single agent, no framework" — link to ADRs. This signals first-principles thinking immediately
5. **Quick demo** — Screenshot or GIF of the agent in action (add this in Week 7)
6. **Architecture** — Link to docs/architecture.md
7. **Getting started** — Simple setup instructions
8. **The failure catalog** — Link to the most interesting part: how the agent handles what it can't do

---

## Phase 1: Data Ingestion & Storage (Week 2)

### 1.1 — SEC EDGAR Client
- [ ] Build `edgar_client.py` to fetch 10-Q and 10-K filings via the EDGAR FULL-TEXT SEARCH API
- [ ] Respect SEC rate limits (10 requests/second with User-Agent header)
- [ ] Target companies: Start with 5 (AAPL, MSFT, JPM, AMZN, GOOGL), expand to 10-15 later
- [ ] Fetch last 8 quarters of 10-Q filings and last 2 annual 10-K filings per company

### 1.2 — Filing Parser
- [ ] Parse XBRL/HTML filings to extract structured financial data
- [ ] Extract key financial statements: income statement, balance sheet, cash flow
- [ ] Normalize line items across companies (different companies label things differently)
- [ ] Store raw text sections for RAG retrieval (MD&A, risk factors, notes to financials)

### 1.3 — Data Storage
- [ ] SQLite database with tables for: companies, filings, financial_line_items, filing_sections
- [ ] Schema designed for the queries the agent will need to answer (think backward from the use case)
- [ ] Indexing for fast lookups by company + period + metric
- [ ] Vector store populated with filing text chunks for retrieval (MD&A sections, footnotes, etc.)

### 1.4 — Data Quality Checks
- [ ] Verify: do balance sheets balance? Do income statement items sum correctly?
- [ ] Log and flag any parsing anomalies — these become interesting test cases later
- [ ] Create a simple data summary report: which companies, which periods, which metrics are available

**Milestone:** You can query `SELECT revenue FROM financial_line_items WHERE company='AAPL' AND period='2024-Q3'` and get correct results.

---

## Phase 2: Context Layer (Weeks 3–4)

This is the core differentiator. Most agent projects skip this entirely.

### 2.1 — Metric Registry
- [ ] Define 20-30 financial metrics in a structured format:

```python
# Example metric definition
{
    "id": "gross_margin",
    "name": "Gross Margin",
    "formula": "(revenue - cost_of_revenue) / revenue",
    "unit": "percentage",
    "components": ["revenue", "cost_of_revenue"],
    "caveats": [
        "Definition of COGS varies by industry — tech companies may exclude different items than manufacturers",
        "One-time charges can distort single-quarter margins",
        "Compare within industry, not across industries"
    ],
    "related_metrics": ["operating_margin", "net_margin", "revenue_growth"],
    "typical_range": {"tech": [0.50, 0.80], "banking": [null, null]},
    "requires_normalization_for_comparison": true
}
```

- [ ] Cover: revenue, revenue growth, gross margin, operating margin, net margin, EPS, free cash flow, debt-to-equity, ROE, current ratio, and 15-20 more
- [ ] Each definition includes: formula, components, caveats, comparability notes, typical ranges

### 2.2 — Domain Rules
- [ ] Fiscal year mapping (Apple's fiscal year ends in September, not December)
- [ ] Industry classification and comparability rules
- [ ] Seasonality awareness (Q4 is holiday quarter for retail, etc.)
- [ ] Rules for when YoY vs QoQ comparisons are appropriate
- [ ] Rules for when TTM vs. quarterly metrics should be used

### 2.3 — Entity Context
- [ ] Per-company context: segments, recent major events (acquisitions, spin-offs), reporting quirks
- [ ] Relationship mapping: which companies are meaningful comparables?
- [ ] Temporal context: which periods are available, any restatements or accounting changes?

### 2.4 — Context Integration
- [ ] Build the interface between the context layer and the agent: when the agent encounters a metric, it should automatically pull the definition, caveats, and relevant domain rules
- [ ] Test: ask the agent about gross margin for Apple vs. JPMorgan — it should flag that this comparison is misleading

**Milestone:** The metric registry contains 20+ well-defined metrics, each with caveats and comparability rules, and the agent can look up any metric's definition and constraints programmatically.

---

## Phase 3: Guardrails & Confidence (Weeks 4–5)

This is the section that will get the most attention in your blog post and demos.

### 3.1 — Scope Guard
- [ ] Define the agent's domain boundary explicitly:
  - **In scope:** Questions about financial metrics, trends, comparisons for covered companies and periods
  - **Out of scope:** Stock price predictions, investment advice, non-financial questions, companies not in the dataset, future projections
- [ ] Implement classification: given a user query, determine if it's in-scope, partially in-scope, or out-of-scope
- [ ] Design graceful refusal responses that explain *why* the agent can't answer and *what* it can help with instead

```
Example:
User: "Should I buy Apple stock?"
Agent: "I can't provide investment advice or stock recommendations.
What I can do is help you analyze Apple's financial fundamentals —
revenue trends, margin analysis, cash flow health — so you have
better data for your own decision. Want to start there?"
```

### 3.2 — Confidence Scoring System
- [ ] Define confidence levels with clear thresholds:

| Level | Score | Meaning | Agent Behavior |
|-------|-------|---------|----------------|
| High | 0.8-1.0 | Direct data retrieval, simple calculation | States answer directly with source |
| Medium | 0.5-0.79 | Derived calculation, some interpretation needed | States answer with caveats and methodology |
| Low | 0.2-0.49 | Incomplete data, requires assumptions | Flags uncertainty, explains what's missing |
| Refuse | 0.0-0.19 | Cannot answer reliably | Explains why and suggests alternatives |

- [ ] Confidence factors to evaluate:
  - Data availability: is the required data present and complete?
  - Calculation complexity: direct lookup vs. multi-step derivation?
  - Temporal relevance: how recent is the data?
  - Comparability: are cross-company comparisons valid?
  - Ambiguity: does the question have multiple valid interpretations?

### 3.3 — Provenance Tracking
- [ ] Every claim in the agent's response gets tagged with:
  - Source filing (e.g., "AAPL 10-Q, Q3 2024, filed 2024-08-02")
  - Specific location within filing (e.g., "Condensed Consolidated Statement of Operations")
  - Data freshness (when was this data last updated in our system?)
  - Calculation chain (if derived: "gross_margin = (revenue - cogs) / revenue = (94.9B - 41.3B) / 94.9B = 56.5%")

### 3.4 — Output Validation
- [ ] Sanity checks on calculated values: is this margin within a plausible range? Is this growth rate realistic?
- [ ] Cross-reference checks: does the data the agent is citing match what's in the database?
- [ ] Consistency checks: if the agent cites two numbers in the same response, are they internally consistent?

### 3.5 — Guardrail Test Suite
- [ ] Write tests for at least 30 scenarios:
  - 10 in-scope questions the agent should answer well
  - 10 out-of-scope questions the agent should refuse gracefully
  - 10 edge cases (partial data, ambiguous questions, cross-industry comparisons)
- [ ] This test suite becomes a key asset — it demonstrates the rigor of the system

**Milestone:** The agent refuses out-of-scope questions gracefully, tags every response with confidence and provenance, and passes all 30 guardrail test cases.

---

## Phase 4: Agent Core & Retrieval (Week 5)

### 4.1 — Retrieval Pipeline
- [ ] Hybrid retrieval: structured SQL queries for numerical data + vector search for qualitative content
- [ ] Query routing: determine whether a question needs numbers (SQL), text (RAG), or both
- [ ] Context assembly: combine retrieved data with metric definitions, domain rules, and entity context before sending to the LLM

### 4.2 — Agent Orchestration
- [ ] System prompt design: inject metric definitions, domain rules, and guardrail instructions
- [ ] Multi-step reasoning: for complex questions, break into sub-queries
- [ ] Calculation verification: agent shows its math, system validates the arithmetic
- [ ] Response structuring: consistent format with answer, methodology, sources, confidence, and follow-up suggestions

### 4.3 — Response Formatting
Design a response structure that demonstrates production readiness:

```
┌─────────────────────────────────────────────┐
│ Answer                                       │
│ Apple's gross margin was 46.5% in Q3 2024,  │
│ up from 44.3% in Q3 2023.                   │
├─────────────────────────────────────────────┤
│ Methodology                                  │
│ Gross Margin = (Revenue - COGS) / Revenue   │
│ Q3 2024: ($85.8B - $45.9B) / $85.8B        │
│ Q3 2023: ($81.8B - $45.6B) / $81.8B        │
├─────────────────────────────────────────────┤
│ Sources                                      │
│ • AAPL 10-Q, Q3 2024, filed 2024-08-02     │
│ • AAPL 10-Q, Q3 2023, filed 2023-08-04     │
├─────────────────────────────────────────────┤
│ Confidence: HIGH (0.92)                      │
│ Direct calculation from reported line items  │
├─────────────────────────────────────────────┤
│ Explore Further                              │
│ → Quarterly margin trend (last 8 quarters)  │
│ → Margin by product segment                 │
│ → Compare to MSFT, GOOGL margins            │
└─────────────────────────────────────────────┘
```

**Milestone:** The agent answers basic financial questions with full provenance, shows its calculations, and returns structured responses.

---

## Phase 5: Investigation Workflows (Week 6)

### 5.1 — Metric Decomposition
- [ ] When a metric changes, the agent offers to decompose *why*:
  - Revenue dropped → break into segments, geographies, volume vs. price
  - Margin compressed → COGS increase vs. revenue decline
  - EPS changed → net income change vs. share count change
- [ ] Each decomposition path is predefined in the metric registry (not improvised by the LLM)

### 5.2 — Structured Follow-ups
- [ ] After answering any question, the agent suggests 2-3 relevant follow-up paths
- [ ] Follow-ups are contextual (not generic): they depend on what the data actually shows
- [ ] Example: if the agent notices margin declined, it proactively offers decomposition

### 5.3 — Multi-turn Investigation
- [ ] Maintain conversation state: the agent remembers what was already discussed
- [ ] Progressive depth: start with summary, drill into detail, compare across entities
- [ ] Bookmarkable state: each point in the investigation could be shared or revisited

**Milestone:** The agent supports a 3-4 turn investigation flow, decomposing metrics and offering structured follow-ups at each step.

---

## Phase 6: Demo UI & Polish (Week 7)

### 6.1 — Chainlit Interface
- [ ] Clean, polished chat UI — the sophistication should be in the agent, not the interface
- [ ] Chat interface with rendered response cards (answer, methodology, sources, confidence)
- [ ] Visual confidence indicator (color-coded)
- [ ] Clickable follow-up suggestions (Chainlit Actions)
- [ ] Example questions panel for first-time users (Chainlit Starters)
- [ ] Custom theme/branding for a professional look

> **Upgrade path:** If the UI needs to evolve beyond Q&A into a full dashboard with charts, tables, and multi-page navigation, migrate to Next.js + Tailwind CSS.

### 6.2 — Demo Scenarios
Prepare 5 polished demo scenarios that showcase different capabilities:

1. **Simple lookup:** "What was Microsoft's revenue in Q2 2024?" → Shows accurate retrieval + provenance
2. **Trend analysis:** "How has Apple's gross margin trended over the last 2 years?" → Shows multi-period analysis + visualization
3. **Comparison:** "Compare operating margins for AAPL, MSFT, and GOOGL" → Shows comparability awareness + caveats
4. **Graceful refusal:** "Should I invest in Tesla?" → Shows scope guardrails + helpful redirection
5. **Investigation workflow:** "Why did JPMorgan's net income drop last quarter?" → Shows decomposition + structured follow-ups

### 6.3 — Screenshots and GIF
- [ ] Record a GIF/video walkthrough of Demo Scenario 5 (the investigation workflow)
- [ ] Take clean screenshots of each response type (high-confidence, low-confidence, refusal)
- [ ] Add these to the README

**Milestone:** A demo-ready Chainlit app with 5 polished scenarios and visual assets for the README and blog post.

---

## Phase 7: Evaluation & Testing (Week 7–8)

### 7.1 — Evaluation Set
- [ ] Curate 50+ test cases across categories:
  - Factual accuracy (do the numbers match the filings?)
  - Guardrail compliance (does it refuse when it should?)
  - Confidence calibration (are high-confidence answers actually correct more often?)
  - Response quality (methodology, provenance, follow-ups present?)

### 7.2 — Run Evals and Publish Results
- [ ] Run the evaluation suite and document results
- [ ] Be honest about failures — a project that shows 85% accuracy with clear analysis of the 15% failure modes is more credible than one claiming 99%
- [ ] Include eval results in the repo (eval/results/)

### 7.3 — Failure Catalog (Key Differentiator)
- [ ] Document every interesting failure mode you encountered:
  - Agent hallucinated a number → how you fixed it
  - Agent gave a confident wrong answer → how confidence scoring caught it
  - Agent couldn't distinguish between GAAP and non-GAAP metrics → how you added that context
  - Cross-company comparison was misleading → how domain rules flagged it
- [ ] This becomes `docs/failure-catalog.md` and a major section of the blog post

**Milestone:** Published eval results, a thorough failure catalog, and honest documentation of what works and what doesn't.

---

## Phase 8: GitHub Publishing (Week 8)

### 8.1 — Repository Polish
- [ ] Final README with: project overview, architecture decisions (ADRs), architecture diagram, demo GIF, quick start, eval results, failure catalog link
- [ ] All docs/ files complete and well-written, including both ADRs (001-single-agent.md, 002-no-framework.md)
- [ ] Clean commit history (squash messy development commits)
- [ ] `.env.example` with clear instructions for API keys
- [ ] One-command setup: `pip install -r requirements.txt && python scripts/seed_data.py && chainlit run ui/app.py`

### 8.2 — Architecture Diagram
- [ ] Create a clear diagram showing the flow: User Query → Scope Guard → Query Router → Retrieval (SQL + Vector) → Context Assembly → LLM Reasoning → Output Validation → Confidence Scoring → Structured Response
- [ ] Use Mermaid, Excalidraw, or similar for a clean, reproducible diagram
- [ ] Include in README and docs/architecture.md

### 8.3 — Licensing & Attribution
- [ ] MIT License (maximizes visibility and reuse)
- [ ] Clear attribution for SEC EDGAR data (public domain, but good practice)
- [ ] Note which LLM APIs the project uses and that users need their own API keys

### 8.4 — Discoverability
- [ ] Add GitHub topics: `ai-agent`, `financial-services`, `guardrails`, `rag`, `sec-edgar`, `llm`, `production-ready`
- [ ] Create a GitHub release with a changelog
- [ ] Add a "star this repo" call-to-action in the README (subtle but effective)

**Milestone:** The repo is polished, discoverable, and a prospect could clone it and run the demo in under 10 minutes.

---

## Phase 9: Blog Post (Week 8–9)

### 9.1 — Blog Post Structure

**Title options (pick one):**
- "What 'Production-Ready' Actually Means for AI Agents in Financial Services"
- "The Reliability Layer: What Everyone Skips When Building AI Agents"
- "Why Your AI Agent Fails in Production (And How to Fix It)"

**Target length:** 3,000–4,000 words

**Outline:**

#### Section 1: The Problem (400 words)
- Most AI agents work in demos but fail in production
- The gap isn't in the LLM or the retrieval — it's in the context, guardrails, and failure handling
- In regulated industries (financial services, insurance, compliance), this gap is existential
- Frame: "I built a reference implementation to show what the missing layer looks like"

#### Section 2: Why Single Agent, No Framework (500 words)
- Address the two most common questions upfront: "Shouldn't this be multi-agent?" and "Why not use LangGraph/ADK/CrewAI?"
- Single agent: the complexity is in context, not coordination. Show the linear flow diagram
- No framework: the orchestration is ~100 lines of Python. Show the actual code. Let readers see how simple coordination is when you strip away abstraction
- Key insight: "Frameworks solve coordination problems. My problem was a context problem. Using a framework would have hidden the very thing I was trying to demonstrate."
- This section will generate strong engagement because it's contrarian to current hype

#### Section 3: The Architecture (600 words)
- Walk through the system design: context layer, guardrails, confidence, investigation workflows
- Architecture diagram from the repo
- Key insight: the reliability layer is not an afterthought — it's the core product
- Compare: "Here's what most agent architectures look like vs. what a production architecture needs"

#### Section 4: The Context Layer — Teaching the Agent What Metrics Mean (500 words)
- The metric registry concept: structured definitions, formulas, caveats, comparability rules
- Example: show how the agent handles "gross margin" differently for a tech company vs. a bank
- Domain rules and entity context — the agent knows Apple's fiscal year ends in September
- Insight: "LLMs don't know what they don't know about your domain. You have to tell them, explicitly and structurally."

#### Section 5: Guardrails That Actually Work (500 words)
- Scope guard: how the agent knows what it can and can't answer
- Confidence scoring: not a vibe check — a structured evaluation
- Show the refusal example: "Should I buy Apple stock?" → graceful redirect
- Insight: "The most impressive thing an agent can do is admit it doesn't know something"

#### Section 6: The Failure Catalog (600 words)
- This is the most valuable section — share real failures you encountered
- 3-4 detailed examples: what went wrong, why, how you fixed it
- Each failure teaches a generalizable lesson about agent reliability
- Be honest and specific — this builds more credibility than any success story

#### Section 7: What I'd Do Differently & What's Next (400 words)
- Lessons learned from the build
- Where the architecture could be improved
- How this pattern applies to other verticals (insurance, compliance, healthcare)
- Soft CTA: "If your team is building AI agents for regulated industries, I'd love to talk about what we've learned"

### 9.2 — Publishing Strategy
- [ ] Primary: Publish on your personal blog or Medium
- [ ] Cross-post to: LinkedIn (summary + link), Hacker News, relevant Subreddits (r/MachineLearning, r/LLMDevs), dbt Slack community
- [ ] Twitter/X thread: distill the 5 key insights into a thread with a link to the full post
- [ ] Timing: publish on Tuesday or Wednesday morning (best engagement for technical content)

### 9.3 — Supporting Content
- [ ] LinkedIn post (shorter, more professional framing): "Here's what I learned building a production-ready AI agent for financial services"
- [ ] Twitter thread: "Most AI agents fail in production. Here are 5 things the successful ones get right 🧵"
- [ ] 2-3 follow-up posts diving deeper into specific topics (confidence scoring, the failure catalog, investigation workflows)

**Milestone:** Blog post published, cross-posted to 3+ platforms, and generating engagement.

---

## Phase 10: Ongoing Leverage (Weeks 9+)

### 10.1 — Content Flywheel
- [ ] Every 2 weeks: publish a shorter post diving into one specific aspect (guardrail design, confidence calibration, metric decomposition)
- [ ] Use questions from GitHub issues and social media comments as prompts for new content
- [ ] Contribute to relevant open-source projects and reference your work in context

### 10.2 — Community Building
- [ ] Engage in discussions on HN, Reddit, and LinkedIn about AI agent reliability
- [ ] Comment on other people's agent projects with specific, helpful feedback (builds visibility)
- [ ] Offer to give a lightning talk at a local meetup or virtual conference

### 10.3 — Sales Pipeline
- [ ] Track inbound interest from the blog post and GitHub repo
- [ ] Follow up with anyone who stars the repo and has a company email
- [ ] Use the demo as a conversation starter: "I built this for public data — imagine what this looks like with your internal data"

---

## Weekly Time Budget (8–10 hours/week)

| Activity | Hours/Week | Notes |
|----------|-----------|-------|
| Coding | 5-6 | Core implementation work |
| Documentation | 1-2 | README, docs, code comments |
| Content writing | 1-2 | Blog post drafting, LinkedIn posts |
| Research / learning | 0.5-1 | SEC EDGAR API, new techniques |

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Scope creep — building too many features | Cap at 5 question types, 10-15 companies, 20-30 metrics. Ship narrow, iterate later |
| EDGAR parsing complexity | Start with XBRL structured data only; skip unstructured HTML parsing initially |
| Burnout from side project + full-time job | Timebox strictly to 8-10 hrs/week. Skip weeks when needed. Progress > perfection |
| IP concerns with Equifax | Different domain (public financials vs. credit), personal accounts only, no proprietary data |
| Agent accuracy isn't good enough | The failure catalog turns failures into content. Honest 85% accuracy > fake 99% |
| Nobody reads the blog post | Cross-post aggressively. The GitHub repo has independent value regardless of blog traffic |

---

## Success Criteria

After 9 weeks, you should have:
- [ ] A working demo agent that handles 5 types of financial questions with full provenance and guardrails
- [ ] A polished GitHub repo with 20+ stars (organic, not bought)
- [ ] A published blog post with 1,000+ views
- [ ] 3-5 inbound conversations with people interested in the problem space
- [ ] A clear thesis on whether this should become a product, a consultancy, or both
