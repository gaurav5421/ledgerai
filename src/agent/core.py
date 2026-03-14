"""Agent Core — main orchestration for LedgerAI.

Single agent with modular components. The flow:
1. Scope Guard → is this in-scope?
2. Context Assembly → retrieve data + attach metric defs, domain rules
3. Pre-LLM Confidence Check → bail out or retry if confidence too low
4. LLM Reasoning → API call (optional — works without it)
5. Faithfulness Validation → cross-reference LLM claims against source data
6. Confidence Scoring → structured evaluation (final)
7. Response Formatting → structured output
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src.agent.response import AgentResponse, build_refusal_response
from src.agent.retrieval import (
    calculate_derived_metric,
    fetch_latest_metric,
    fetch_metric_trend,
    get_available_metrics_for_company,
    get_db,
    get_latest_period,
)
from src.context.domain_rules import (
    get_company_industry,
    get_comparison_warnings,
    get_seasonality_notes,
)
from src.context.entity_context import (
    format_company_context,
    get_company_context,
)
from src.context.metric_registry import (
    format_metric_context,
    get_all_metric_ids,
    get_metric,
    is_applicable_to_company,
)
from src.guardrails.confidence import (
    ConfidenceLevel,
    ConfidenceScore,
    compute_confidence,
    score_ambiguity,
    score_calculation_complexity,
    score_comparability,
    score_data_availability,
    score_temporal_relevance,
)
from src.guardrails.provenance import ProvenanceRecord, build_fiscal_label
from src.guardrails.scope_guard import ScopeLevel, ScopeResult, check_scope
from src.guardrails.validation import validate_faithfulness
from src.investigation.decomposition import (
    DecompositionResult,
    decompose_metric_change,
    has_decomposition,
)
from src.investigation.follow_ups import generate_contextual_follow_ups
from src.investigation.session import InvestigationDepth, InvestigationSession

logger = logging.getLogger(__name__)

load_dotenv()


@dataclass
class ContextPackage:
    """All assembled context for a query — the explicit input to LLM and confidence scoring."""

    context_parts: list[str] = field(default_factory=list)
    data_context: str = ""
    provenance: ProvenanceRecord = field(default_factory=ProvenanceRecord)
    retrieved_metrics: list[str] = field(default_factory=list)
    relevant_metrics: list[str] = field(default_factory=list)
    comparison_warnings: list[str] = field(default_factory=list)
    decomposition_result: DecompositionResult | None = None
    tickers: list[str] = field(default_factory=list)
    scope: ScopeResult | None = None
    depth: InvestigationDepth = InvestigationDepth.SUMMARY
    is_trend: bool = False

    @property
    def answer_metrics(self) -> list[str]:
        return self.relevant_metrics or self.retrieved_metrics

    def build_system_prompt(self) -> str:
        context_str = "\n\n".join(self.context_parts)
        return SYSTEM_PROMPT.format(context=context_str)


SYSTEM_PROMPT = """\
You are LedgerAI, a financial analysis agent that answers questions \
about public company financials using SEC EDGAR filing data.

## Your Capabilities
- Answer questions about financial metrics (revenue, margins, EPS, cash flow, etc.)
- Analyze trends across quarters and years
- Compare companies (with appropriate caveats)
- Explain what metrics mean and how they're calculated
- Decompose why a metric changed

## Your Rules
1. ONLY use the data provided in the context below. Never make up numbers.
2. Always show your methodology — state the formula and the inputs.
3. If data is missing or incomplete, say so explicitly. Never guess.
4. When comparing companies across industries, flag that the comparison may be misleading.
5. Do NOT provide investment advice, stock recommendations, or price predictions.
6. Use the metric definitions and caveats provided — they exist for a reason.
7. Keep answers concise but complete. Lead with the answer, then explain.
8. When relevant, suggest follow-up questions the user might find useful.

## Response Format
Structure your response as:
- **Answer**: The direct answer to the question
- **Methodology**: How you calculated it (formula + inputs)
- **Caveats**: Any important caveats from the metric definitions or domain rules
- **Follow-ups**: 2-3 relevant follow-up questions (if applicable)

{context}
"""


def _try_init_llm():
    """Try to initialize an LLM client. Returns (client, provider) or (None, None)."""
    # Try Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai

            client = genai.Client(api_key=gemini_key)
            return client, "gemini"
        except ImportError:
            pass

    # Try Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your-api-key-here":
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=anthropic_key)
            return client, "anthropic"
        except ImportError:
            pass

    return None, None


class LedgerAIAgent:
    """Main agent class — orchestrates the full query pipeline.

    Works in two modes:
    - With LLM API: natural language answers enhanced by retrieved data
    - Without LLM API: structured data-driven answers with full provenance
    """

    def __init__(self, db_path: Path | None = None):
        self.conn = get_db(db_path)
        self.llm_client, self.llm_provider = _try_init_llm()
        self.session = InvestigationSession()
        if self.llm_client:
            logger.info(f"LLM enabled: {self.llm_provider}")
        else:
            logger.info("Running without LLM — using data-driven responses")

    def new_session(self) -> None:
        """Start a fresh investigation session."""
        self.session = InvestigationSession()

    def _classify_query_intent(self, query: str) -> dict:
        """Classify query intent using LLM when keyword matching fails.

        Returns dict with:
            is_trend: bool — does the query ask for multi-period data?
            target_metrics: list[str] — metric IDs to retrieve
        """
        if not self.llm_client:
            return {"is_trend": False, "target_metrics": []}

        system = (
            "You classify financial queries. Respond with ONLY a JSON object, "
            "no markdown, no explanation.\n\n"
            "Determine:\n"
            "1. is_trend: true if the query asks for data across multiple "
            "periods/quarters/years, comparisons over time, historical data, "
            "or breakdown by quarter/year. false if asking about a single "
            "point-in-time value.\n"
            "2. target_metrics: list of metric IDs from this set that the "
            "query is asking about: revenue, net_income, gross_profit, "
            "gross_margin, operating_income, operating_margin, net_margin, "
            "eps_basic, eps_diluted, operating_cash_flow, capex, "
            "free_cash_flow, total_assets, total_equity, long_term_debt, "
            "current_ratio, debt_to_equity, rd_expense, sga_expense, "
            "net_interest_income, shares_outstanding\n\n"
            'Example: {"is_trend": true, "target_metrics": ["revenue"]}'
        )

        try:
            import json

            raw = self._call_llm(system, query)
            if raw:
                # Strip markdown code fences if present
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
                return json.loads(raw.strip())
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Intent classification failed: {e}")

        return {"is_trend": False, "target_metrics": []}

    def _call_llm(self, system: str, user_query: str) -> str | None:
        """Call the LLM if available. Returns response text or None."""
        if not self.llm_client:
            return None

        try:
            if self.llm_provider == "gemini":
                response = self.llm_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"{system}\n\n---\n\nUser question: {user_query}",
                )
                return response.text
            elif self.llm_provider == "anthropic":
                message = self.llm_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=system,
                    messages=[{"role": "user", "content": user_query}],
                )
                return message.content[0].text
        except Exception as e:
            logger.warning(f"LLM call failed ({e}), falling back to data-driven response")
            return None

    def query(self, user_query: str) -> AgentResponse:
        """Process a user query through the full pipeline."""
        logger.info(f"Processing query: {user_query}")

        # Check if user is selecting a follow-up by number
        follow_up_idx = self.session.is_follow_up_selection(user_query)
        if follow_up_idx is not None:
            last_follow_ups = self.session.get_last_follow_ups()
            if follow_up_idx < len(last_follow_ups):
                selected = last_follow_ups[follow_up_idx]
                user_query = selected.split(" [")[0]
                logger.info(f"Follow-up selected: {user_query}")

        # Step 1: Scope Guard
        scope = check_scope(user_query)
        logger.info(f"Scope: {scope.level.value} — {scope.reason}")

        if scope.level == ScopeLevel.OUT_OF_SCOPE:
            return build_refusal_response(scope.reason, scope.suggestion)

        if scope.level == ScopeLevel.PARTIAL and not scope.detected_tickers:
            return build_refusal_response(scope.reason, scope.suggestion)

        # Step 2: Context Assembly (retrieval + enrichment → ContextPackage)
        ctx = self._assemble_context(user_query, scope)

        # Step 3: Pre-LLM Confidence Check — bail out or retry if too low
        confidence = self._compute_confidence(ctx)

        if not confidence.should_answer:
            logger.info(f"Confidence REFUSE ({confidence.score:.2f}) — bailing out")
            return AgentResponse(
                answer=(
                    "I don't have sufficient data to answer this reliably. "
                    f"{confidence.summary} "
                    "Try asking about a specific metric (revenue, margins, EPS, etc.) "
                    "for one of these companies: AAPL, MSFT, GOOGL, AMZN, JPM."
                ),
                confidence=confidence,
                is_refusal=True,
                warnings=ctx.comparison_warnings,
            )

        # If LOW confidence due to poor data availability, retry with broader metrics
        data_factor = next((f for f in confidence.factors if f.name == "data_availability"), None)
        if confidence.level == ConfidenceLevel.LOW and data_factor and data_factor.score < 0.3:
            logger.info("Low data availability — retrying with broader default metrics")
            ctx = self._assemble_context(user_query, scope, force_broad_metrics=True)
            confidence = self._compute_confidence(ctx)

        # Step 4: LLM Call (optional) or build data-driven answer
        system = ctx.build_system_prompt()
        llm_response = self._call_llm(system, user_query)
        used_llm = False

        if llm_response:
            answer_text = llm_response
            used_llm = True
        else:
            metrics = ctx.answer_metrics or ctx.retrieved_metrics
            answer_text = self._build_data_answer(
                user_query,
                ctx.tickers,
                metrics,
                ctx.data_context,
                ctx.provenance,
                is_trend=ctx.is_trend,
            )

        # Step 5: Faithfulness Validation (LLM responses only)
        if used_llm:
            faith = validate_faithfulness(answer_text, ctx.provenance)
            if not faith.is_valid:
                logger.warning(
                    f"Faithfulness check failed: {faith.errors} — "
                    "falling back to data-driven answer"
                )
                metrics = ctx.answer_metrics or ctx.retrieved_metrics
                answer_text = self._build_data_answer(
                    user_query, ctx.tickers, metrics, ctx.data_context, ctx.provenance
                )
            elif faith.warnings:
                answer_text += "\n\n**Verification Notes**\n" + "\n".join(
                    f"- {w}" for w in faith.warnings
                )

        # Step 6: Add uncertainty disclaimer for LOW confidence
        if confidence.level == ConfidenceLevel.LOW:
            answer_text = (
                "**Note: This answer has significant uncertainty.** "
                f"{confidence.summary}\n\n{answer_text}"
            )

        # Step 7: Follow-ups and session recording
        follow_ups = generate_contextual_follow_ups(
            self.conn, ctx.tickers, ctx.answer_metrics, user_query
        )
        self.session.record_turn(
            query=user_query,
            tickers=ctx.tickers,
            metrics=ctx.answer_metrics,
            depth=ctx.depth,
            follow_ups=follow_ups,
            decomposition_metric=(
                ctx.decomposition_result.metric_id if ctx.decomposition_result else None
            ),
        )

        return AgentResponse(
            answer=answer_text,
            methodology=ctx.provenance.format_calculations() if ctx.provenance else None,
            sources=ctx.provenance.format_sources() if ctx.provenance else None,
            confidence=confidence,
            follow_ups=follow_ups,
            warnings=ctx.comparison_warnings,
            decomposition=ctx.decomposition_result,
        )

    def _assemble_context(
        self,
        user_query: str,
        scope: ScopeResult,
        force_broad_metrics: bool = False,
    ) -> ContextPackage:
        """Retrieve data and assemble all context into a ContextPackage.

        Explicit dependency: retrieval → assembly → (LLM + confidence).
        """
        tickers = scope.detected_tickers
        context_parts = []
        query_lower = user_query.lower()

        # Company context
        for ticker in tickers:
            ctx = format_company_context(ticker)
            context_parts.append(f"## Company: {ticker}\n{ctx}")

            available = get_available_metrics_for_company(self.conn, ticker)
            context_parts.append(f"Available metrics for {ticker}: {', '.join(available)}")

            latest = get_latest_period(self.conn, ticker)
            if latest:
                context_parts.append(f"Latest data for {ticker}: period ending {latest}")

        # Retrieve financial data
        data_context, provenance, retrieved_metrics, is_trend = self._retrieve_data(
            user_query, tickers, force_broad=force_broad_metrics
        )
        if data_context:
            context_parts.append(f"## Financial Data\n{data_context}")

        # Metric definitions for any mentioned metrics
        all_metric_ids = get_all_metric_ids()
        relevant_metrics = []
        for mid in all_metric_ids:
            m = get_metric(mid)
            if m and (mid in query_lower or m.name.lower() in query_lower):
                relevant_metrics.append(mid)
                context_parts.append(f"## Metric: {m.name}\n{format_metric_context(mid)}")

        # Comparison warnings
        comparison_warnings = []
        if len(tickers) > 1:
            comparison_warnings = get_comparison_warnings(
                tickers, relevant_metrics or retrieved_metrics
            )
            if comparison_warnings:
                context_parts.append(
                    "## Comparison Warnings\n" + "\n".join(f"- {w}" for w in comparison_warnings)
                )

        # Seasonality notes
        for ticker in tickers:
            notes = get_seasonality_notes(ticker)
            if notes:
                note_text = "\n".join(
                    f"- Q{n.quarter} ({n.effect}): {n.description}" for n in notes
                )
                context_parts.append(f"## Seasonality for {ticker}\n{note_text}")

        # Investigation context from prior turns
        session_context = self.session.build_context_summary()
        if session_context:
            context_parts.append(session_context)

        # Decomposition (if query asks "why" about a metric)
        depth = self.session.classify_depth(
            user_query, tickers, relevant_metrics or retrieved_metrics
        )
        decomposition_result = None
        if depth == InvestigationDepth.DECOMPOSITION:
            decomp_metrics = relevant_metrics or retrieved_metrics
            for metric_id in decomp_metrics:
                if has_decomposition(metric_id):
                    result = decompose_metric_change(self.conn, tickers[0], metric_id)
                    if result:
                        decomposition_result = result
                        context_parts.append(f"## Decomposition Analysis\n{result.format_text()}")
                        break

        return ContextPackage(
            context_parts=context_parts,
            data_context=data_context,
            provenance=provenance,
            retrieved_metrics=retrieved_metrics,
            relevant_metrics=relevant_metrics,
            comparison_warnings=comparison_warnings,
            decomposition_result=decomposition_result,
            tickers=tickers,
            scope=scope,
            depth=depth,
            is_trend=is_trend,
        )

    def _compute_confidence(self, ctx: ContextPackage) -> ConfidenceScore:
        """Compute confidence score from assembled context."""
        available_for_first = (
            get_available_metrics_for_company(self.conn, ctx.tickers[0]) if ctx.tickers else []
        )
        latest = get_latest_period(self.conn, ctx.tickers[0]) if ctx.tickers else None

        metrics = ctx.relevant_metrics or ctx.retrieved_metrics
        factors = [
            score_data_availability(metrics, available_for_first),
            score_calculation_complexity(
                is_direct_lookup=len(ctx.relevant_metrics) <= 1
                and not any(
                    m_id in ("gross_margin", "operating_margin", "net_margin", "debt_to_equity")
                    for m_id in metrics
                ),
                num_components=sum(
                    len(get_metric(m).components) for m in ctx.relevant_metrics if get_metric(m)
                ),
                requires_cross_period=bool(ctx.retrieved_metrics)
                and any(get_metric(m) is not None for m in ctx.retrieved_metrics),
                requires_cross_company=len(ctx.tickers) > 1,
            ),
            score_temporal_relevance(
                data_period_end=ctx.provenance.data_freshness if ctx.provenance else None,
                latest_available=latest,
            ),
            score_comparability(ctx.tickers, ctx.comparison_warnings),
            score_ambiguity(
                has_single_interpretation=ctx.scope is not None
                and ctx.scope.level == ScopeLevel.IN_SCOPE,
                metric_count=len(ctx.relevant_metrics) if ctx.relevant_metrics else 1,
            ),
        ]
        return compute_confidence(factors)

    def _build_data_answer(
        self,
        query: str,
        tickers: list[str],
        metrics: list[str],
        data_context: str,
        provenance: ProvenanceRecord,
        is_trend: bool = False,
    ) -> str:
        """Build a structured answer from retrieved data without LLM."""
        parts = []
        is_comparison = len(tickers) > 1

        for ticker in tickers:
            company_ctx = get_company_context(ticker)
            company_name = company_ctx.name if company_ctx else ticker

            for metric_id in metrics:
                m = get_metric(metric_id)
                metric_name = m.name if m else metric_id

                industry = get_company_industry(ticker)
                if not is_applicable_to_company(metric_id, industry):
                    parts.append(
                        f"{metric_name} is not a standard metric for {industry} companies "
                        f"like {company_name}."
                    )
                    if metric_id == "gross_margin" and industry == "banking":
                        parts.append("For banks, net interest margin is the more relevant metric.")
                    continue

                if is_trend:
                    rows = fetch_metric_trend(self.conn, ticker, metric_id, quarters=8)
                    if rows:
                        parts.append(f"**{company_name} ({ticker}) — {metric_name} Trend:**")
                        for row in rows:
                            label = build_fiscal_label(
                                row["fiscal_year"],
                                row.get("fiscal_quarter"),
                                bool(row["is_quarterly"]),
                            )
                            val_str = _fmt_val(row["value"], row["unit"])
                            parts.append(f"  {label} ({row['period_end']}): {val_str}")

                        # Add simple trend analysis
                        if len(rows) >= 2:
                            latest_val = rows[0]["value"]
                            oldest_val = rows[-1]["value"]
                            if oldest_val != 0:
                                change = (latest_val - oldest_val) / abs(oldest_val) * 100
                                direction = "increased" if change > 0 else "decreased"
                                old_str = _fmt_val(oldest_val, rows[-1]["unit"])
                                new_str = _fmt_val(latest_val, rows[0]["unit"])
                                parts.append(
                                    f"\n  Overall: {metric_name} has {direction} "
                                    f"{abs(change):.1f}% from {old_str} "
                                    f"to {new_str} over {len(rows)} quarters."
                                )
                        # YoY comparison for the latest quarter
                        if len(rows) >= 5:
                            yoy_change = (
                                (rows[0]["value"] - rows[4]["value"]) / abs(rows[4]["value"]) * 100
                            )
                            parts.append(
                                f"  YoY change (latest vs same quarter last year): "
                                f"{yoy_change:+.1f}%"
                            )
                        parts.append("")
                    else:
                        # Try computing derived metric trend from components
                        trend_data = self._compute_derived_trend(ticker, metric_id, quarters=8)
                        if trend_data:
                            unit = m.unit if m else "ratio"
                            parts.append(f"**{company_name} ({ticker}) — {metric_name} Trend:**")
                            for label, period_end, value in trend_data:
                                if unit == "percentage":
                                    parts.append(f"  {label} ({period_end}): {value*100:.1f}%")
                                elif unit == "ratio":
                                    parts.append(f"  {label} ({period_end}): {value:.2f}")
                                else:
                                    parts.append(
                                        f"  {label} ({period_end}): {_fmt_val(value, unit)}"
                                    )
                            if len(trend_data) >= 2:
                                latest_val = trend_data[0][2]
                                oldest_val = trend_data[-1][2]
                                if unit == "percentage":
                                    change_pp = (latest_val - oldest_val) * 100
                                    direction = "expanded" if change_pp > 0 else "contracted"
                                    parts.append(
                                        f"\n  Overall: {metric_name} has {direction} "
                                        f"{abs(change_pp):.1f} percentage points over "
                                        f"{len(trend_data)} quarters."
                                    )
                            parts.append("")
                        else:
                            parts.append(f"No trend data available for {ticker} {metric_name}.")
                else:
                    row = fetch_latest_metric(self.conn, ticker, metric_id)
                    if row:
                        label = build_fiscal_label(
                            row["fiscal_year"], row.get("fiscal_quarter"), bool(row["is_quarterly"])
                        )
                        val_str = _fmt_val(row["value"], row["unit"])
                        parts.append(
                            f"**{company_name} ({ticker}) — {metric_name}:** "
                            f"{val_str} ({label}, period ending {row['period_end']})"
                        )

                        # Add metric caveats
                        if m and m.caveats:
                            parts.append(f"  Note: {m.caveats[0]}")

                        # Add seasonality context
                        if row.get("fiscal_quarter"):
                            notes = get_seasonality_notes(ticker, row["fiscal_quarter"])
                            for n in notes:
                                parts.append(f"  Seasonality: {n.description}")
                    else:
                        # Try derived
                        result = calculate_derived_metric(self.conn, ticker, metric_id)
                        if result:
                            value, _ = result
                            if m and m.unit == "percentage":
                                parts.append(
                                    f"**{company_name} ({ticker}) — {metric_name}:** "
                                    f"{value*100:.1f}%"
                                )
                            elif m and m.unit == "ratio":
                                parts.append(
                                    f"**{company_name} ({ticker}) — {metric_name}:** "
                                    f"{value:.2f}"
                                )
                            else:
                                parts.append(
                                    f"**{company_name} ({ticker}) — {metric_name}:** "
                                    f"{_fmt_val(value, m.unit if m else 'USD')}"
                                )
                        else:
                            parts.append(f"Data for {ticker} {metric_name} is not available.")

        # Add comparison warnings inline
        if is_comparison and len(tickers) > 1:
            warnings = get_comparison_warnings(tickers, metrics)
            for w in warnings:
                parts.append(f"\n**Comparison Note:** {w}")

        if not parts:
            parts.append(
                f"I found data for {', '.join(tickers)} but couldn't match specific metrics "
                f"to your question. Try asking about revenue, margins, EPS, cash flow, or debt."
            )

        return "\n".join(parts)

    def _compute_derived_trend(
        self, ticker: str, metric_id: str, quarters: int = 8
    ) -> list[tuple[str, str, float]]:
        """Compute a derived metric across multiple quarters.

        Returns list of (fiscal_label, period_end, value) sorted newest first.
        """
        # Map derived metrics to their component formulas
        derivations = {
            "gross_margin": ("gross_profit", "revenue", lambda a, b: a / b if b else None),
            "operating_margin": ("operating_income", "revenue", lambda a, b: a / b if b else None),
            "net_margin": ("net_income", "revenue", lambda a, b: a / b if b else None),
            "fcf_margin": (None, None, None),  # Needs special handling
            "free_cash_flow": ("operating_cash_flow", "capex", lambda a, b: a - b),
        }

        if metric_id not in derivations:
            return []

        if metric_id == "fcf_margin":
            # Three components
            ocf_rows = fetch_metric_trend(self.conn, ticker, "operating_cash_flow", quarters)
            capex_rows = fetch_metric_trend(self.conn, ticker, "capex", quarters)
            rev_rows = fetch_metric_trend(self.conn, ticker, "revenue", quarters)
            if not (ocf_rows and capex_rows and rev_rows):
                return []
            capex_by_period = {r["period_end"]: r["value"] for r in capex_rows}
            rev_by_period = {r["period_end"]: r["value"] for r in rev_rows}
            results = []
            for row in ocf_rows:
                pe = row["period_end"]
                if pe in capex_by_period and pe in rev_by_period and rev_by_period[pe] != 0:
                    fcf = row["value"] - capex_by_period[pe]
                    val = fcf / rev_by_period[pe]
                    label = build_fiscal_label(
                        row["fiscal_year"], row.get("fiscal_quarter"), bool(row["is_quarterly"])
                    )
                    results.append((label, pe, val))
            return results

        numerator_metric, denominator_metric, calc_fn = derivations[metric_id]
        num_rows = fetch_metric_trend(self.conn, ticker, numerator_metric, quarters)
        den_rows = fetch_metric_trend(self.conn, ticker, denominator_metric, quarters)

        if not num_rows or not den_rows:
            return []

        den_by_period = {r["period_end"]: r["value"] for r in den_rows}

        results = []
        for row in num_rows:
            pe = row["period_end"]
            if pe in den_by_period:
                val = calc_fn(row["value"], den_by_period[pe])
                if val is not None:
                    label = build_fiscal_label(
                        row["fiscal_year"], row.get("fiscal_quarter"), bool(row["is_quarterly"])
                    )
                    results.append((label, pe, val))

        return results

    def _retrieve_data(
        self, query: str, tickers: list[str], force_broad: bool = False
    ) -> tuple[str, ProvenanceRecord, list[str], bool]:
        """Retrieve relevant financial data based on the query."""
        provenance = ProvenanceRecord()
        data_lines = []
        retrieved_metrics = []
        query_lower = query.lower()

        # Determine which metrics to fetch based on query keywords
        metric_keywords = {
            "revenue": ["revenue", "sales", "top line", "top-line"],
            "net_income": ["net income", "earnings", "profit", "bottom line"],
            "gross_profit": ["gross profit"],
            "gross_margin": ["gross margin"],
            "operating_income": ["operating income", "operating profit"],
            "operating_margin": ["operating margin"],
            "net_margin": ["net margin", "profit margin"],
            "eps_basic": ["eps", "earnings per share"],
            "eps_diluted": ["diluted eps", "diluted earnings"],
            "operating_cash_flow": ["operating cash flow", "cash from operations"],
            "capex": ["capex", "capital expenditure"],
            "free_cash_flow": ["free cash flow", "fcf"],
            "total_assets": ["total assets", "assets"],
            "total_equity": ["equity", "book value"],
            "long_term_debt": ["debt", "long term debt"],
            "current_ratio": ["current ratio", "liquidity"],
            "debt_to_equity": ["debt to equity", "leverage", "d/e"],
            "rd_expense": ["r&d", "research and development", "r & d"],
            "sga_expense": ["sga", "selling general"],
            "net_interest_income": ["net interest income", "nii"],
            "shares_outstanding": ["shares outstanding", "share count"],
        }

        target_metrics = []
        if not force_broad:
            for metric_id, keywords in metric_keywords.items():
                if any(kw in query_lower for kw in keywords):
                    target_metrics.append(metric_id)

        # If no specific metric found (or force_broad), provide a broad overview
        if not target_metrics:
            target_metrics = [
                "revenue",
                "net_income",
                "eps_diluted",
                "gross_margin",
                "operating_income",
                "operating_cash_flow",
            ]

        # Determine if trend or single period — keyword fast path
        trend_keywords = [
            "trend",
            "over time",
            "last",
            "quarters",
            "history",
            "trended",
            "by quarter",
            "quarterly",
            "each quarter",
            "per quarter",
            "q1",
            "q2",
            "q3",
            "q4",
        ]
        is_trend = any(kw in query_lower for kw in trend_keywords)

        # LLM fallback: if keywords didn't match for either metrics or trend,
        # ask the LLM to classify the intent
        if not is_trend or not target_metrics:
            intent = self._classify_query_intent(query)
            if not is_trend:
                is_trend = intent.get("is_trend", False)
            if not target_metrics and intent.get("target_metrics"):
                target_metrics = [
                    m for m in intent["target_metrics"] if m in metric_keywords or force_broad
                ]
            if not target_metrics:
                target_metrics = [
                    "revenue",
                    "net_income",
                    "eps_diluted",
                    "gross_margin",
                    "operating_income",
                    "operating_cash_flow",
                ]

        for ticker in tickers:
            for metric_id in target_metrics:
                industry = get_company_industry(ticker)
                if not is_applicable_to_company(metric_id, industry):
                    data_lines.append(
                        f"{ticker}: {metric_id} is not applicable for {industry} companies"
                    )
                    continue

                if is_trend:
                    rows = fetch_metric_trend(self.conn, ticker, metric_id, quarters=8)
                    if rows:
                        retrieved_metrics.append(metric_id)
                        data_lines.append(f"\n{ticker} — {metric_id} (last {len(rows)} quarters):")
                        for row in rows:
                            label = build_fiscal_label(
                                row["fiscal_year"],
                                row.get("fiscal_quarter"),
                                bool(row["is_quarterly"]),
                            )
                            data_lines.append(
                                f"  {label} ({row['period_end']}): "
                                f"{_fmt_val(row['value'], row['unit'])}"
                            )
                            provenance.add_source(
                                ticker=ticker,
                                filing_type="10-Q" if row["is_quarterly"] else "10-K",
                                period_end=row["period_end"],
                                fiscal_label=label,
                                metric=metric_id,
                                value=row["value"],
                                unit=row["unit"],
                            )
                    else:
                        # Derived metrics (margins, ratios) aren't stored directly
                        derived = self._compute_derived_trend(ticker, metric_id)
                        if derived:
                            retrieved_metrics.append(metric_id)
                            n = len(derived)
                            data_lines.append(
                                f"\n{ticker} — {metric_id} " f"(last {n} periods, calculated):"
                            )
                            for label, period_end, val in derived:
                                data_lines.append(f"  {label} ({period_end}): {val:.4f}")
                                provenance.add_source(
                                    ticker=ticker,
                                    filing_type="10-K/10-Q",
                                    period_end=period_end,
                                    fiscal_label=label,
                                    metric=metric_id,
                                    value=val,
                                    unit="ratio",
                                )
                else:
                    row = fetch_latest_metric(self.conn, ticker, metric_id)
                    if row:
                        retrieved_metrics.append(metric_id)
                        label = build_fiscal_label(
                            row["fiscal_year"], row.get("fiscal_quarter"), bool(row["is_quarterly"])
                        )
                        data_lines.append(
                            f"{ticker} — {metric_id}: {_fmt_val(row['value'], row['unit'])} "
                            f"({label}, {row['period_end']})"
                        )
                        provenance.add_source(
                            ticker=ticker,
                            filing_type="10-Q" if row["is_quarterly"] else "10-K",
                            period_end=row["period_end"],
                            fiscal_label=label,
                            metric=metric_id,
                            value=row["value"],
                            unit=row["unit"],
                        )
                    else:
                        result = calculate_derived_metric(self.conn, ticker, metric_id)
                        if result:
                            value, calc_prov = result
                            retrieved_metrics.append(metric_id)
                            provenance.sources.extend(calc_prov.sources)
                            provenance.calculations.extend(calc_prov.calculations)
                            if calc_prov.data_freshness:
                                provenance.data_freshness = calc_prov.data_freshness
                            data_lines.append(f"{ticker} — {metric_id} (calculated): {value:.4f}")

        return "\n".join(data_lines), provenance, list(set(retrieved_metrics)), is_trend

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _fmt_val(value: float, unit: str) -> str:
    if unit in ("USD",):
        if abs(value) >= 1e12:
            return f"${value/1e12:.2f}T"
        elif abs(value) >= 1e9:
            return f"${value/1e9:.1f}B"
        elif abs(value) >= 1e6:
            return f"${value/1e6:.1f}M"
        return f"${value:,.0f}"
    elif unit == "USD/share":
        return f"${value:.2f}/share"
    elif unit == "shares":
        return f"{value/1e9:.2f}B shares"
    return f"{value:,.2f} {unit}"
