#!/usr/bin/env python3
"""Quick interactive demo of LedgerAI agent.

Supports multi-turn investigation with:
- Numbered follow-up selection (type 1, 2, or 3 to select)
- Decomposition queries ("Why did X change?")
- Session state across turns
"""

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
    print("  Type 'new' to start a fresh investigation")
    print("  Type a number (1-3) to select a follow-up")
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
        "Why did Amazon's operating margin change recently?",
    ]

    while True:
        try:
            # Show turn count if in an active investigation
            if agent.session.turn_count > 0:
                prompt = f"\nYou (turn {agent.session.turn_count + 1}): "
            else:
                prompt = "\nYou: "
            query = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() == "quit":
            print("Goodbye!")
            break
        if query.lower() == "new":
            agent.new_session()
            print("\n--- New investigation started ---")
            continue
        if query.lower() == "help":
            print("\nExample questions:")
            for ex in examples:
                print(f"  - {ex}")
            print("\nDuring an investigation:")
            print("  - Type a number (1-3) to select a follow-up suggestion")
            print("  - Ask 'why' to decompose a metric change")
            print("  - Type 'new' to start a fresh investigation")
            continue

        print()
        response = agent.query(query)
        print(response.format_text())

    agent.close()


if __name__ == "__main__":
    main()
