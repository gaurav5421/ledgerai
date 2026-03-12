"""Metric Decomposition — predefined paths to explain WHY a metric changed.

Each decomposition is deterministic: look at a metric's components, compare
periods, and identify which component(s) drove the change. The LLM doesn't
improvise — decomposition paths are defined here.
"""

import sqlite3
from dataclasses import dataclass

from src.agent.retrieval import fetch_metric_trend
from src.context.metric_registry import get_metric
from src.guardrails.provenance import ProvenanceRecord, build_fiscal_label

# ---- Decomposition trees ----
# Maps metric_id -> list of decomposition paths.
# Each path: (label, description, component_metrics)

DECOMPOSITION_PATHS: dict[str, list[tuple[str, str, list[str]]]] = {
    "revenue": [
        (
            "Segment Breakdown",
            "Break revenue into business segments to see which grew or shrank",
            ["revenue"],  # same metric, segmented — handled specially
        ),
    ],
    "gross_margin": [
        (
            "Margin Bridge",
            "Was the change driven by revenue growth or cost-of-revenue changes?",
            ["revenue", "gross_profit", "cost_of_revenue"],
        ),
    ],
    "operating_margin": [
        (
            "Expense Decomposition",
            "Which expense line drove the operating margin change?",
            ["revenue", "operating_income", "gross_profit", "rd_expense", "sga_expense"],
        ),
    ],
    "operating_income": [
        (
            "Expense Decomposition",
            "Break operating income into gross profit minus operating expenses",
            ["gross_profit", "rd_expense", "sga_expense"],
        ),
    ],
    "net_margin": [
        (
            "Income Bridge",
            "Was the change from operating performance or below-the-line items?",
            ["revenue", "operating_income", "net_income"],
        ),
    ],
    "net_income": [
        (
            "P&L Walk",
            "Walk from revenue to net income to find what changed",
            ["revenue", "gross_profit", "operating_income", "net_income"],
        ),
    ],
    "eps_diluted": [
        (
            "EPS Drivers",
            "Was the EPS change from net income or share count?",
            ["net_income", "shares_outstanding"],
        ),
    ],
    "eps_basic": [
        (
            "EPS Drivers",
            "Was the EPS change from net income or share count?",
            ["net_income", "shares_outstanding"],
        ),
    ],
    "free_cash_flow": [
        (
            "FCF Components",
            "Was the change from operating cash flow or capital expenditures?",
            ["operating_cash_flow", "capex"],
        ),
    ],
    "fcf_margin": [
        (
            "FCF Margin Bridge",
            "Decompose into FCF change vs. revenue change",
            ["operating_cash_flow", "capex", "revenue"],
        ),
    ],
}


def get_decomposition_paths(metric_id: str) -> list[tuple[str, str, list[str]]]:
    """Return available decomposition paths for a metric."""
    return DECOMPOSITION_PATHS.get(metric_id, [])


def has_decomposition(metric_id: str) -> bool:
    return metric_id in DECOMPOSITION_PATHS


def decompose_metric_change(
    conn: sqlite3.Connection,
    ticker: str,
    metric_id: str,
    path_index: int = 0,
    quarters: int = 4,
) -> "DecompositionResult | None":
    """Run a decomposition analysis on a metric.

    Compares the latest period to the prior period (QoQ) and same-quarter
    last year (YoY), breaking the change into component contributions.
    """
    paths = get_decomposition_paths(metric_id)
    if not paths or path_index >= len(paths):
        return None

    label, description, component_metrics = paths[path_index]
    provenance = ProvenanceRecord()

    # Fetch component data for last N quarters
    component_trends: dict[str, list[dict]] = {}
    for comp in component_metrics:
        rows = fetch_metric_trend(conn, ticker, comp, quarters=quarters + 4)
        if rows:
            component_trends[comp] = rows

    if not component_trends:
        return None

    # Build period-over-period changes for each component
    component_changes: list[ComponentChange] = []
    for comp_id, rows in component_trends.items():
        m = get_metric(comp_id)
        comp_name = m.name if m else comp_id

        if len(rows) < 2:
            continue

        latest = rows[0]
        prior = rows[1]
        provenance.add_source(
            ticker=ticker,
            filing_type="10-Q" if latest["is_quarterly"] else "10-K",
            period_end=latest["period_end"],
            fiscal_label=build_fiscal_label(
                latest["fiscal_year"], latest.get("fiscal_quarter"), bool(latest["is_quarterly"])
            ),
            metric=comp_id,
            value=latest["value"],
            unit=latest["unit"],
        )

        qoq_change = None
        if prior["value"] != 0:
            qoq_change = (latest["value"] - prior["value"]) / abs(prior["value"])

        # YoY: find same quarter last year (4 quarters back)
        yoy_change = None
        if len(rows) >= 5:
            yoy_prior = rows[4]
            if yoy_prior["value"] != 0:
                yoy_change = (latest["value"] - yoy_prior["value"]) / abs(yoy_prior["value"])

        component_changes.append(
            ComponentChange(
                metric_id=comp_id,
                metric_name=comp_name,
                latest_value=latest["value"],
                prior_value=prior["value"],
                unit=latest["unit"],
                qoq_change=qoq_change,
                yoy_change=yoy_change,
                latest_period=latest["period_end"],
                prior_period=prior["period_end"],
            )
        )

    if not component_changes:
        return None

    # Identify the primary driver (largest absolute change)
    driver = _identify_driver(component_changes, metric_id)

    return DecompositionResult(
        metric_id=metric_id,
        ticker=ticker,
        path_label=label,
        description=description,
        components=component_changes,
        driver=driver,
        provenance=provenance,
    )


def _identify_driver(changes: list["ComponentChange"], parent_metric: str) -> str:
    """Identify which component drove the parent metric's change.

    Uses heuristics based on the metric type.
    """
    if not changes:
        return "Insufficient data to identify driver."

    # For margin metrics, compare numerator vs denominator movement
    margin_metrics = {"gross_margin", "operating_margin", "net_margin", "fcf_margin"}
    if parent_metric in margin_metrics:
        # First component is typically revenue (denominator),
        # others are numerator-related
        by_abs_yoy = sorted(
            [c for c in changes if c.yoy_change is not None],
            key=lambda c: abs(c.yoy_change),
            reverse=True,
        )
        if by_abs_yoy:
            top = by_abs_yoy[0]
            direction = "increase" if (top.yoy_change or 0) > 0 else "decrease"
            return (
                f"Primary driver: {top.metric_name} "
                f"({direction} of {abs(top.yoy_change or 0) * 100:.1f}% YoY)"
            )

    # For absolute metrics, find the component with largest absolute $ change
    by_abs_change = sorted(
        [c for c in changes if c.prior_value != 0],
        key=lambda c: abs(c.latest_value - c.prior_value),
        reverse=True,
    )
    if by_abs_change:
        top = by_abs_change[0]
        delta = top.latest_value - top.prior_value
        direction = "increased" if delta > 0 else "decreased"
        pct = abs(top.qoq_change or 0) * 100
        return f"Primary driver: {top.metric_name} " f"({direction} {pct:.1f}% QoQ)"

    return "Multiple factors contributed — no single dominant driver."


# ---- Data Classes ----


@dataclass
class ComponentChange:
    metric_id: str
    metric_name: str
    latest_value: float
    prior_value: float
    unit: str
    qoq_change: float | None  # as decimal (0.05 = 5%)
    yoy_change: float | None
    latest_period: str
    prior_period: str


@dataclass
class DecompositionResult:
    metric_id: str
    ticker: str
    path_label: str
    description: str
    components: list[ComponentChange]
    driver: str
    provenance: ProvenanceRecord

    def format_text(self) -> str:
        """Format decomposition as readable text."""
        parts = [
            f"**Decomposition: {self.path_label}**",
            self.description,
            "",
        ]

        for comp in self.components:
            val_str = _fmt_decomp_val(comp.latest_value, comp.unit)
            prior_str = _fmt_decomp_val(comp.prior_value, comp.unit)
            line = f"  {comp.metric_name}: {val_str} (prior: {prior_str})"

            changes = []
            if comp.qoq_change is not None:
                changes.append(f"QoQ: {comp.qoq_change * 100:+.1f}%")
            if comp.yoy_change is not None:
                changes.append(f"YoY: {comp.yoy_change * 100:+.1f}%")
            if changes:
                line += f"  [{', '.join(changes)}]"
            parts.append(line)

        parts.append(f"\n{self.driver}")
        return "\n".join(parts)


def _fmt_decomp_val(value: float, unit: str) -> str:
    if unit in ("USD",):
        if abs(value) >= 1e12:
            return f"${value / 1e12:.2f}T"
        elif abs(value) >= 1e9:
            return f"${value / 1e9:.1f}B"
        elif abs(value) >= 1e6:
            return f"${value / 1e6:.1f}M"
        return f"${value:,.0f}"
    elif unit == "USD/share":
        return f"${value:.2f}/share"
    elif unit == "shares":
        return f"{value / 1e9:.2f}B shares"
    return f"{value:,.2f} {unit}"
