"""Confidence Scoring — structured evaluation of answer reliability.

Not a vibe check. Evaluates multiple dimensions to produce a calibrated
confidence score with clear reasoning.
"""

from dataclasses import dataclass
from enum import Enum


class ConfidenceLevel(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    REFUSE = "REFUSE"


@dataclass
class ConfidenceFactor:
    name: str
    score: float  # 0.0 to 1.0
    reason: str


@dataclass
class ConfidenceScore:
    level: ConfidenceLevel
    score: float  # 0.0 to 1.0
    factors: list[ConfidenceFactor]
    summary: str

    @property
    def should_answer(self) -> bool:
        return self.level != ConfidenceLevel.REFUSE


def classify_level(score: float) -> ConfidenceLevel:
    if score >= 0.8:
        return ConfidenceLevel.HIGH
    elif score >= 0.5:
        return ConfidenceLevel.MEDIUM
    elif score >= 0.2:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.REFUSE


def score_data_availability(
    requested_metrics: list[str],
    available_metrics: list[str],
    requested_periods: list[str] | None = None,
    available_periods: list[str] | None = None,
) -> ConfidenceFactor:
    """Score based on whether required data is present."""
    if not requested_metrics:
        return ConfidenceFactor("data_availability", 0.5, "No specific metrics identified")

    found = [m for m in requested_metrics if m in available_metrics]
    ratio = len(found) / len(requested_metrics)

    if ratio == 1.0:
        reason = f"All requested metrics available: {', '.join(found)}"
    elif ratio > 0:
        missing = [m for m in requested_metrics if m not in available_metrics]
        reason = f"Partial data: have {', '.join(found)}, missing {', '.join(missing)}"
    else:
        reason = f"None of the requested metrics found: {', '.join(requested_metrics)}"

    # Also check period availability
    period_score = 1.0
    if requested_periods and available_periods:
        avail_set = set(available_periods)
        found_periods = [p for p in requested_periods if p in avail_set]
        period_score = len(found_periods) / len(requested_periods) if requested_periods else 1.0
        if period_score < 1.0:
            reason += f" (period coverage: {period_score:.0%})"

    final_score = ratio * 0.7 + period_score * 0.3
    return ConfidenceFactor("data_availability", final_score, reason)


def score_calculation_complexity(
    is_direct_lookup: bool = False,
    num_components: int = 0,
    requires_cross_period: bool = False,
    requires_cross_company: bool = False,
) -> ConfidenceFactor:
    """Score based on how complex the calculation is."""
    if is_direct_lookup:
        return ConfidenceFactor(
            "calculation_complexity", 1.0, "Direct data lookup — no calculation needed"
        )

    score = 0.9  # Start high for calculated metrics
    reasons = []

    if num_components > 0:
        score -= 0.05 * num_components
        reasons.append(f"{num_components} component metrics")

    if requires_cross_period:
        score -= 0.1
        reasons.append("cross-period comparison")

    if requires_cross_company:
        score -= 0.1
        reasons.append("cross-company comparison")

    score = max(score, 0.3)
    reason = "Derived calculation: " + ", ".join(reasons) if reasons else "Simple calculation"
    return ConfidenceFactor("calculation_complexity", score, reason)


def score_temporal_relevance(
    data_period_end: str | None = None,
    latest_available: str | None = None,
) -> ConfidenceFactor:
    """Score based on how recent the data is."""
    if not data_period_end:
        return ConfidenceFactor("temporal_relevance", 0.5, "Period not specified")

    if data_period_end == latest_available:
        return ConfidenceFactor(
            "temporal_relevance", 1.0, f"Using most recent data ({data_period_end})"
        )

    # If we can determine staleness
    if latest_available:
        return ConfidenceFactor(
            "temporal_relevance",
            0.8,
            f"Data from {data_period_end} (latest available: {latest_available})",
        )

    return ConfidenceFactor("temporal_relevance", 0.7, f"Data from {data_period_end}")


def score_comparability(
    tickers: list[str],
    comparison_warnings: list[str],
) -> ConfidenceFactor:
    """Score based on whether comparisons are valid."""
    if len(tickers) <= 1:
        return ConfidenceFactor("comparability", 1.0, "Single company — no comparison issues")

    if not comparison_warnings:
        return ConfidenceFactor(
            "comparability", 0.9, f"Comparing {', '.join(tickers)} — no major issues detected"
        )

    penalty = 0.15 * len(comparison_warnings)
    score = max(0.3, 0.9 - penalty)
    reason = f"{len(comparison_warnings)} comparison warning(s): " + "; ".join(
        w[:80] for w in comparison_warnings
    )
    return ConfidenceFactor("comparability", score, reason)


def score_ambiguity(
    has_single_interpretation: bool = True,
    metric_count: int = 1,
) -> ConfidenceFactor:
    """Score based on query ambiguity."""
    if has_single_interpretation and metric_count == 1:
        return ConfidenceFactor("ambiguity", 1.0, "Clear, unambiguous question")

    if not has_single_interpretation:
        return ConfidenceFactor("ambiguity", 0.5, "Question has multiple valid interpretations")

    if metric_count > 3:
        return ConfidenceFactor("ambiguity", 0.6, f"Broad question covering {metric_count} metrics")

    return ConfidenceFactor("ambiguity", 0.8, "Moderately specific question")


def compute_confidence(factors: list[ConfidenceFactor]) -> ConfidenceScore:
    """Compute overall confidence from individual factors.

    Uses weighted average, with data_availability weighted highest.
    """
    if not factors:
        return ConfidenceScore(
            level=ConfidenceLevel.LOW,
            score=0.3,
            factors=[],
            summary="No confidence factors evaluated",
        )

    weights = {
        "data_availability": 0.35,
        "calculation_complexity": 0.20,
        "temporal_relevance": 0.15,
        "comparability": 0.15,
        "ambiguity": 0.15,
    }

    total_weight = 0.0
    weighted_sum = 0.0
    for f in factors:
        w = weights.get(f.name, 0.15)
        weighted_sum += f.score * w
        total_weight += w

    score = weighted_sum / total_weight if total_weight > 0 else 0.3
    level = classify_level(score)

    # Build summary
    if level == ConfidenceLevel.HIGH:
        summary = "Direct data retrieval with high reliability"
    elif level == ConfidenceLevel.MEDIUM:
        low_factors = [f for f in factors if f.score < 0.7]
        if low_factors:
            summary = "Answer available with caveats: " + "; ".join(f.reason for f in low_factors)
        else:
            summary = "Derived calculation with moderate confidence"
    elif level == ConfidenceLevel.LOW:
        low_factors = [f for f in factors if f.score < 0.5]
        summary = "Significant uncertainty: " + "; ".join(f.reason for f in low_factors)
    else:
        summary = "Cannot answer reliably: " + "; ".join(f.reason for f in factors if f.score < 0.2)

    return ConfidenceScore(
        level=level,
        score=round(score, 2),
        factors=factors,
        summary=summary,
    )
