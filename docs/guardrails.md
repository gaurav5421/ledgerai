# Guardrails Design

## Philosophy

The most impressive thing an agent can do is admit it doesn't know something. LedgerAI's guardrails are not an afterthought — they are the core product differentiator.

## Scope Guard

### In Scope
- Questions about financial metrics for covered companies and periods
- Trend analysis across quarters/years
- Cross-company comparisons (with appropriate caveats)
- Metric decomposition (why did a metric change?)

### Out of Scope
- Stock price predictions or investment advice
- Non-financial questions
- Companies not in the dataset
- Future projections or forecasts
- Non-public or insider information

### Graceful Refusal
When the agent cannot answer, it:
1. Explains *why* it can't answer
2. Suggests what it *can* help with instead
3. Never fabricates an answer to stay "helpful"

## Confidence Scoring

| Level | Score | Meaning | Agent Behavior |
|-------|-------|---------|----------------|
| High | 0.8-1.0 | Direct data retrieval, simple calculation | States answer directly with source |
| Medium | 0.5-0.79 | Derived calculation, some interpretation | States answer with caveats and methodology |
| Low | 0.2-0.49 | Incomplete data, requires assumptions | Flags uncertainty, explains what's missing |
| Refuse | 0.0-0.19 | Cannot answer reliably | Explains why and suggests alternatives |

### Confidence Factors
- **Data availability** — is the required data present and complete?
- **Calculation complexity** — direct lookup vs. multi-step derivation?
- **Temporal relevance** — how recent is the data?
- **Comparability** — are cross-company comparisons valid?
- **Ambiguity** — does the question have multiple valid interpretations?

## Provenance Tracking

Every claim includes:
- Source filing (e.g., "AAPL 10-Q, Q3 2024, filed 2024-08-02")
- Specific location within filing
- Data freshness
- Calculation chain (if derived)

## Output Validation

- Sanity checks: is this margin within a plausible range?
- Cross-reference: does the cited data match the database?
- Consistency: are multiple numbers in the same response internally consistent?
