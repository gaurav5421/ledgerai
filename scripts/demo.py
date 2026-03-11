#!/usr/bin/env python3
"""Quick interactive demo of LedgerAI agent."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from src.agent.core import LedgerAIAgent  # noqa: E402


def main():
    print("=" * 60)
    print("  LedgerAI — Financial Analysis Agent")
    print("  Type 'quit' to exit, 'help' for example questions")
    print("=" * 60)

    try:
        agent = LedgerAIAgent()
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)

    examples = [
        "What was Apple's revenue last quarter?",
        "How has Microsoft's gross margin trended over the last 8 quarters?",
        "Compare operating margins for AAPL, MSFT, and GOOGL",
        "Should I buy Apple stock?",
        "What was JPMorgan's net income?",
        "Why did Amazon's net income change recently?",
    ]

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() == "quit":
            print("Goodbye!")
            break
        if query.lower() == "help":
            print("\nExample questions:")
            for ex in examples:
                print(f"  - {ex}")
            continue

        print()
        response = agent.query(query)
        print(response.format_text())

    agent.close()


if __name__ == "__main__":
    main()
