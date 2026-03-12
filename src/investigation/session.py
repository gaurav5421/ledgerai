"""Investigation Session — multi-turn conversation state.

Tracks what's been discussed, supports progressive depth (summary → detail →
comparison), and maintains context across turns so the agent doesn't repeat
itself or lose track of the investigation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class InvestigationDepth(Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    COMPARISON = "comparison"
    DECOMPOSITION = "decomposition"


@dataclass
class TurnRecord:
    """Record of a single turn in the investigation."""

    query: str
    tickers: list[str]
    metrics: list[str]
    depth: InvestigationDepth
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    follow_ups_offered: list[str] = field(default_factory=list)
    decomposition_metric: str | None = None


@dataclass
class InvestigationSession:
    """Maintains state across a multi-turn investigation.

    Tracks:
    - What companies and metrics have been discussed
    - What depth level the user is at (summary → detail → decomposition)
    - Which follow-ups were offered (so we can match user input)
    - Conversation history for context
    """

    turns: list[TurnRecord] = field(default_factory=list)
    _active_tickers: set[str] = field(default_factory=set)
    _discussed_metrics: dict[str, set[str]] = field(default_factory=dict)  # ticker -> {metrics}

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def active_tickers(self) -> list[str]:
        """Companies currently in the investigation."""
        return list(self._active_tickers)

    @property
    def is_new(self) -> bool:
        return len(self.turns) == 0

    def record_turn(
        self,
        query: str,
        tickers: list[str],
        metrics: list[str],
        depth: InvestigationDepth,
        follow_ups: list[str] | None = None,
        decomposition_metric: str | None = None,
    ) -> None:
        """Record a completed turn."""
        self.turns.append(
            TurnRecord(
                query=query,
                tickers=tickers,
                metrics=metrics,
                depth=depth,
                follow_ups_offered=follow_ups or [],
                decomposition_metric=decomposition_metric,
            )
        )
        self._active_tickers.update(tickers)
        for ticker in tickers:
            if ticker not in self._discussed_metrics:
                self._discussed_metrics[ticker] = set()
            self._discussed_metrics[ticker].update(metrics)

    def get_discussed_metrics(self, ticker: str) -> set[str]:
        """Get metrics already discussed for a given ticker."""
        return self._discussed_metrics.get(ticker, set())

    def get_last_follow_ups(self) -> list[str]:
        """Get follow-ups offered in the most recent turn."""
        if self.turns:
            return self.turns[-1].follow_ups_offered
        return []

    def get_current_depth(self) -> InvestigationDepth:
        """Infer current depth from turn history."""
        if not self.turns:
            return InvestigationDepth.SUMMARY

        last = self.turns[-1]
        return last.depth

    def classify_depth(
        self, query: str, tickers: list[str], metrics: list[str]
    ) -> InvestigationDepth:
        """Classify what depth level this new query represents."""
        query_lower = query.lower()

        # Decomposition signals
        if any(
            kw in query_lower
            for kw in ["why", "decompose", "break down", "what drove", "what caused"]
        ):
            return InvestigationDepth.DECOMPOSITION

        # Comparison signals
        if len(tickers) > 1 or any(kw in query_lower for kw in ["compare", "vs", "versus"]):
            return InvestigationDepth.COMPARISON

        # Detail signals: trend, history, or follow-up on already-discussed topic
        if any(kw in query_lower for kw in ["trend", "history", "quarters", "over time"]):
            return InvestigationDepth.DETAIL

        # If we've already discussed this ticker+metric combo, this is deeper
        for ticker in tickers:
            discussed = self.get_discussed_metrics(ticker)
            if discussed & set(metrics):
                return InvestigationDepth.DETAIL

        return InvestigationDepth.SUMMARY

    def is_follow_up_selection(self, query: str) -> int | None:
        """Check if the user's input is selecting a follow-up by number (1, 2, 3).

        Returns the 0-based index if matched, None otherwise.
        """
        query = query.strip()

        # Match "1", "2", "3" or "option 1", "follow-up 2", etc.
        for i, _ in enumerate(self.get_last_follow_ups()):
            if query == str(i + 1):
                return i

        return None

    def build_context_summary(self) -> str | None:
        """Build a summary of the investigation so far for the LLM context.

        Returns None if no previous turns.
        """
        if not self.turns:
            return None

        lines = ["## Investigation Context (prior turns)"]
        for i, turn in enumerate(self.turns[-5:], 1):  # Last 5 turns
            tickers_str = ", ".join(turn.tickers)
            metrics_str = ", ".join(turn.metrics) if turn.metrics else "general"
            lines.append(f"Turn {i}: [{turn.depth.value}] {tickers_str} — {metrics_str}")
            lines.append(f"  Query: {turn.query}")

        lines.append(
            f"\nInvestigation covers: {', '.join(self._active_tickers)} "
            f"({self.turn_count} turns so far)"
        )

        return "\n".join(lines)
