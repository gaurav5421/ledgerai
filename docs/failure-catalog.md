# Failure Catalog

Honest documentation of failure modes encountered during development, how they
were detected, and how they were addressed. Most AI agent projects don't show
you where they break — this is what separates a demo from a production system.

## Format

Each entry includes:
- **What happened** — the failure as observed
- **Root cause** — why it happened
- **How the agent handles it** — the mitigation or fix
- **Lesson** — the generalizable takeaway

---

## 1. Hallucinated Numbers Without Grounding

**What happened:** Early versions let the LLM answer financial questions with
only a general system prompt and no retrieved data. The model confidently
produced plausible-looking numbers that didn't match actual filings.

**Example:** "What was Apple's revenue in Q3 2024?" — The LLM returned a number
from its training data that was close but not exact, and didn't cite which
filing it came from.

**Root cause:** The LLM was asked to recall financial figures from parametric
memory rather than being given retrieved data.

**How the agent handles it:** The agent retrieves actual data from SQLite
*before* calling the LLM. The LLM receives exact numbers in its context and is
instructed to use only provided data. In deterministic mode (no LLM), numbers
come directly from the database with full provenance.

**Lesson:** Never trust an LLM to recall financial figures from memory. Always
retrieve-then-reason, never reason-then-retrieve.

---

## 2. Gross Margin Reported for Banks

**What happened:** When asked "What is JPMorgan's gross margin?", the agent
tried to calculate gross_profit / revenue for JPM. Banks don't report gross
profit — the concept doesn't apply to their business model.

**Root cause:** No industry-specific validation on which metrics are meaningful
for which business types.

**How the agent handles it:** The `applicable_to_banks` flag on every metric in
the registry, enforced by `is_applicable_to_company()`. The agent responds:
"Gross margin is not a standard metric for banking companies like JPMorgan. For
banks, net interest margin is the more relevant metric."

**Lesson:** Domain-specific validation prevents technically-correct-but-
misleading answers. The metric registry is the enforcement layer.

---

## 3. QoQ Comparison Masking Seasonality

**What happened:** "How did Apple's revenue change last quarter?" showed a QoQ
decline that looked alarming, but it was simply the seasonal pattern — Q1
(holiday) is always the highest revenue quarter, and Q2 always drops.

**Root cause:** Raw percentage changes without seasonal context.

**How the agent handles it:** `seasonal_sensitivity` flags on metrics and
`SeasonalityNote` entries per company per quarter. The agent includes seasonality
context and recommends YoY comparison for seasonal metrics. Domain rules generate
warnings when QoQ comparison is used on seasonally-sensitive metrics.

**Lesson:** Raw percentage changes without context are dangerous in financial
analysis. The agent must know *when* a change is expected vs. surprising.

---

## 4. Cross-Industry Margin Comparison

**What happened:** "Compare margins for AAPL and JPM" produced a side-by-side
that was technically accurate but deeply misleading. Apple's 45% gross margin
vs. JPM's non-existent gross margin — completely different business models.

**Root cause:** No industry-aware comparison guardrails.

**How the agent handles it:** `get_comparison_warnings()` checks industry pairs
and generates specific warnings. The confidence score is penalized through
`score_comparability`. The response includes visible warnings.

**Lesson:** Comparisons across industries need prominent caveats, not footnotes.
The agent should actively explain why a comparison may be misleading.

---

## 5. Fiscal Year Misalignment in Comparisons

**What happened:** Comparing "Q1 results" for Apple and Microsoft compared
different calendar periods. Apple's Q1 is Oct-Dec; Microsoft's Q1 is Jul-Sep.
The agent presented them as if they were the same time window.

**Root cause:** Fiscal quarter labels are company-specific, not universal.

**How the agent handles it:** `check_fiscal_year_alignment()` generates a warning
when comparing companies with different fiscal year ends. The agent shows actual
period_end dates alongside fiscal labels and suggests comparing by calendar
period instead.

**Lesson:** Always show actual calendar dates alongside fiscal labels. "Q1" means
different things for different companies.

---

## 6. Confident Wrong Answer on Derived Metrics

**What happened:** The agent calculated operating margin for a quarter where
operating income was from one period but revenue came from a different period
(data mismatch). The confidence score was HIGH because individual factors looked
good.

**Root cause:** Cross-period inputs in derived metric calculation.

**How the agent handles it:** `calculate_derived_metric()` tracks provenance for
each component and verifies period alignment. The provenance record shows exactly
which filing and period each input came from, making mismatches visible.
Confidence scoring penalizes cross-period calculations.

**Lesson:** Derived metrics need provenance at the component level, not just the
result level. A ratio is only valid if both inputs are from the same period.

---

## 7. EPS Inflated by Share Buybacks

**What happened:** The agent reported "EPS increased 15%" as positive, but net
income was flat. The EPS increase was entirely driven by reduced share count
from buybacks.

**Root cause:** Single-metric view without decomposition into drivers.

**How the agent handles it:** The EPS decomposition path breaks changes into net
income contribution vs. share count contribution. The metric registry caveat
notes: "Share buybacks reduce share count, inflating EPS even if net income is
flat."

**Lesson:** Single metrics can be misleading without decomposition. The
investigation workflow turns headline numbers into understood stories.

---

## 8. Generic Follow-ups Adding No Value

**What happened:** Early follow-up suggestions were generic templates: "Show more
data for AAPL", "Compare with peers." They didn't reflect what the data showed
and were never selected by users.

**Root cause:** Template-based generation with no awareness of actual data.

**How the agent handles it:** Replaced with data-driven contextual follow-ups
that check if a metric changed 5%+, detect QoQ vs YoY divergence, suggest
related metrics from the registry, and offer peer comparison with actual
comparable companies.

**Lesson:** Follow-ups should be driven by what the data shows. If revenue
dropped 20%, "Why did revenue drop?" is useful. "Show more data" is not.

---

## 9. Deterministic Mode Producing Raw Data Dumps

**What happened:** Without an LLM API key (deterministic fallback mode), answers
were raw data dumps — accurate but unreadable. No narrative, no context.

**Root cause:** Deterministic mode treated as an afterthought.

**How the agent handles it:** `_build_data_answer()` was enhanced with trend
analysis (overall change, YoY comparison), inline metric caveats and seasonality
context, readable number formatting ($119.6B, not 119575000000), comparison
warnings, and structured sections.

**Lesson:** Deterministic mode should be a first-class experience. Many users
run the demo without API keys first.

---

## 10. Missing Data Silently Producing Empty Results

**What happened:** When a metric wasn't available for a company, the agent
returned an empty answer with no explanation.

**Root cause:** No explicit handling for absent data paths.

**How the agent handles it:** Every data retrieval path has an explicit "not
available" branch. The confidence scoring penalizes missing data. The response
always contains something useful, even if it's telling the user what data exists
for that company.

**Lesson:** Absence of data is itself information. The agent should communicate
what it doesn't know as clearly as what it does know.

---

## Summary

| # | Failure Mode | Root Cause | Detection Method | Fix Layer |
|---|---|---|---|---|
| 1 | Hallucinated numbers | LLM memory vs. grounding | Spot-check vs. filings | Retrieval pipeline |
| 2 | Wrong metric for industry | Missing domain rules | Nonsensical output | Metric registry |
| 3 | Seasonality masking | No seasonal awareness | YoY vs QoQ divergence | Domain rules |
| 4 | Cross-industry comparison | No industry checks | Domain review | Comparison warnings |
| 5 | Fiscal year misalignment | Different FY calendars | Date mismatch | Domain rules |
| 6 | Mismatched period inputs | Cross-period derivation | Sanity check | Provenance tracking |
| 7 | Buyback-inflated EPS | Single metric view | Decomposition | Investigation module |
| 8 | Generic follow-ups | Template-based | User testing | Contextual follow-ups |
| 9 | Poor deterministic mode | Afterthought design | No-API testing | Data answer builder |
| 10 | Silent empty results | Missing error paths | Edge case testing | Explicit fallbacks |

Each failure informed a specific architectural decision. The system is designed
so that new failure modes can be addressed at the appropriate layer (metric
registry, domain rules, confidence scoring, or investigation workflows) without
restructuring the entire pipeline.
