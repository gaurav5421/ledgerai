#!/usr/bin/env python3
"""Showcase demo — walks through 5 queries that demonstrate LedgerAI's guardrails.

Each query triggers a different part of the pipeline:
1. Scope Guard refusal (investment advice)
2. Clean answer with provenance (factual lookup)
3. Trend analysis with derived metrics (operating margin over time)
4. Low-confidence disclaimer (ambiguous/sparse query)
5. Multi-turn investigation with decomposition (why did X change?)

Run:  .venv/bin/python scripts/showcase_demo.py
"""

import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# Suppress all log output so it doesn't pollute the formatted demo
logging.disable(logging.CRITICAL)

from src.agent.core import LedgerAIAgent  # noqa: E402

# ANSI colors for terminal output
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

QUERIES = [
    {
        "label": "SCOPE GUARD — Out-of-scope refusal",
        "description": (
            "The agent refuses investment advice before touching "
            "the LLM or database. No tokens spent, no hallucination risk."
        ),
        "query": "Should I buy Apple stock?",
    },
    {
        "label": "CLEAN ANSWER — Factual lookup with provenance",
        "description": (
            "A straightforward metric lookup. Every number is tagged "
            "to its SEC filing. Confidence scoring evaluates data quality."
        ),
        "query": "What was Apple's revenue last quarter?",
    },
    {
        "label": "DERIVED METRICS — Calculated trend over time",
        "description": (
            "Operating margin isn't stored directly — the agent computes "
            "it from operating_income / revenue across periods. The LLM "
            "intent classifier detects this is a trend query."
        ),
        "query": "How has Google's operating margin changed over the last year?",
    },
    {
        "label": "CROSS-COMPANY COMPARISON — Comparability warnings",
        "description": (
            "Comparing a tech company against a bank. The agent flags "
            "that certain metrics aren't comparable across industries "
            "and warns about different fiscal year endings."
        ),
        "query": "Compare operating margins for Apple and JPMorgan",
    },
    {
        "label": "INVESTIGATION — Decomposition (why did X change?)",
        "description": (
            "A 'why' query triggers metric decomposition — the agent "
            "breaks operating income into components (revenue, COGS, "
            "R&D, SGA) and identifies the primary driver of change."
        ),
        "query": "Why did Microsoft's operating income change?",
    },
]

SEPARATOR = f"{DIM}{'─' * 70}{RESET}"


def print_header():
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  LedgerAI — Guardrails Showcase Demo{RESET}")
    print(f"{DIM}  5 queries, each demonstrating a different reliability pattern{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")


def print_query_header(idx: int, item: dict):
    print(f"\n{SEPARATOR}")
    print(f"\n{BOLD}{CYAN}[{idx}/{len(QUERIES)}] {item['label']}{RESET}")
    print(f"{DIM}{item['description']}{RESET}")
    print(f"\n{YELLOW}Query: \"{item['query']}\"{RESET}\n")


def print_response(response):
    text = response.format_text()

    # Color the confidence line
    if response.confidence:
        level = response.confidence.level.value
        if level == "HIGH":
            color = GREEN
        elif level == "MEDIUM":
            color = YELLOW
        elif level == "LOW":
            color = YELLOW
        else:
            color = RED
        text = text.replace(
            f"**Confidence: {level}",
            f"**Confidence: {color}{level}{RESET}",
        )

    print(text)


def main():
    print_header()

    agent = LedgerAIAgent()
    interactive = "--auto" not in sys.argv

    for idx, item in enumerate(QUERIES, 1):
        if interactive and idx > 1:
            try:
                input(f"\n{DIM}Press Enter for next query " f"(or Ctrl+C to exit)...{RESET}")
            except (EOFError, KeyboardInterrupt):
                print(f"\n{DIM}Demo ended.{RESET}")
                break

        print_query_header(idx, item)

        start = time.time()
        response = agent.query(item["query"])
        elapsed = time.time() - start

        print_response(response)
        print(f"\n{DIM}[{elapsed:.1f}s]{RESET}")

        # Start fresh session between unrelated queries,
        # but keep session for the investigation flow
        if idx != 4:
            agent.new_session()

    print(f"\n{SEPARATOR}")
    print(f"\n{BOLD}Demo complete.{RESET}")
    print(
        f"{DIM}Each query demonstrated a different reliability pattern: "
        f"scope guard, provenance,\nderived metrics, comparability "
        f"warnings, and metric decomposition.{RESET}\n"
    )

    agent.close()


if __name__ == "__main__":
    main()
