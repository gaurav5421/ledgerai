# LedgerAI

Most AI agents fail in production because they lack domain context, guardrails, and the ability to say "I don't know." This project demonstrates what a production-ready AI agent looks like in financial services.

## What It Does

- **Answers questions about public company financials** — revenue trends, margin analysis, segment breakdowns — using data from SEC EDGAR filings (10-Q and 10-K)
- **Shows its work** — every answer includes the calculation methodology, source filings, and a confidence score
- **Knows its limits** — refuses out-of-scope questions (investment advice, predictions) gracefully, explaining what it *can* help with instead
- **Supports investigation workflows** — when a metric changes, the agent offers to decompose *why* and suggests structured follow-up paths

## What Makes It Different

The reliability layer is the product, not an afterthought:

- **Metric Registry** — 20+ financial metrics with structured definitions, formulas, caveats, and comparability rules. The agent doesn't improvise what "gross margin" means — it looks it up.
- **Confidence Scoring** — not a vibe check. A structured evaluation based on data availability, calculation complexity, and comparability.
- **Provenance Tracking** — every claim is tagged with source filing, location, and calculation chain.
- **Failure Catalog** — documented failure modes and how the agent handles them. See [docs/failure-catalog.md](docs/failure-catalog.md).

## Architecture Decisions

This project makes two deliberate, contrarian architecture choices:

1. **Single agent, not multi-agent** — the complexity is in context, not coordination. [Read the ADR →](docs/adrs/001-single-agent.md)
2. **No agent framework** — no LangGraph, no ADK, no CrewAI. The orchestration is ~150 lines of Python. Every decision is visible in the code. [Read the ADR →](docs/adrs/002-no-framework.md)

## Architecture

```
User Query
    → Scope Guard (is this in-scope?)
    → Query Router (SQL, vector, or both?)
    → Retrieval Layer (structured data + filing text)
    → Context Assembly (metric definitions, domain rules, entity context)
    → LLM Reasoning (single, well-constructed prompt)
    → Output Validation (sanity checks, consistency)
    → Confidence Scoring (structured evaluation)
    → Structured Response (answer, methodology, sources, confidence, follow-ups)
```

See [docs/architecture.md](docs/architecture.md) for the full system design.

## Quick Start

```bash
# Clone and set up
git clone https://github.com/gaurav5421/ledgerai.git
cd ledgerai

# Create virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your Anthropic API key and EDGAR user agent

# Download and process SEC filings
python scripts/download_filings.py
python scripts/seed_data.py

# Launch the demo
chainlit run ui/app.py
```

## Covered Companies

AAPL, MSFT, GOOGL, AMZN, JPM (initial set — expanding to 10-15)

## Project Structure

```
src/
├── ingestion/     # SEC EDGAR client, filing parser, data storage
├── context/       # Metric registry, domain rules, entity context
├── agent/         # Core orchestration, retrieval, reasoning, response
├── guardrails/    # Scope guard, confidence, provenance, validation
├── investigation/ # Follow-up workflows, metric decomposition
└── api/           # FastAPI application
```

## Documentation

- [Architecture](docs/architecture.md)
- [ADR: Single Agent](docs/adrs/001-single-agent.md)
- [ADR: No Framework](docs/adrs/002-no-framework.md)
- [Guardrails Design](docs/guardrails.md)
- [Metrics Dictionary](docs/metrics-dictionary.md)
- [Failure Catalog](docs/failure-catalog.md)

## License

MIT — see [LICENSE](LICENSE).
