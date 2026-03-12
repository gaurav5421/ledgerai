"""LedgerAI Chainlit UI — polished chat interface for financial analysis.

Run: chainlit run ui/app.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

import chainlit as cl  # noqa: E402

from src.agent.core import LedgerAIAgent  # noqa: E402
from src.agent.response import AgentResponse  # noqa: E402
from src.guardrails.confidence import ConfidenceLevel  # noqa: E402

# ============================================================
# Starters — example questions for first-time users
# ============================================================


@cl.set_starters
async def set_starters(user=None, language=None):
    return [
        cl.Starter(
            label="Apple Revenue",
            message="What was Apple's revenue last quarter?",
            icon="/public/icons/chart.svg",
        ),
        cl.Starter(
            label="Margin Trends",
            message="How has Microsoft's gross margin trended over the last 8 quarters?",
            icon="/public/icons/trending.svg",
        ),
        cl.Starter(
            label="Company Comparison",
            message="Compare operating margins for AAPL, MSFT, and GOOGL",
            icon="/public/icons/compare.svg",
        ),
        cl.Starter(
            label="Investigate Changes",
            message="Why did Amazon's operating margin change recently?",
            icon="/public/icons/search.svg",
        ),
    ]


# ============================================================
# Chat Lifecycle
# ============================================================


@cl.on_chat_start
async def on_chat_start():
    agent = LedgerAIAgent()
    cl.user_session.set("agent", agent)

    welcome = (
        "Welcome to **LedgerAI** — your financial analysis agent.\n\n"
        "I analyze public company financials from SEC EDGAR filings for "
        "**AAPL**, **MSFT**, **GOOGL**, **AMZN**, and **JPM**.\n\n"
        "Ask me about revenue, margins, earnings, cash flow, or comparisons. "
        "Try one of the examples below, or type your own question."
    )
    await cl.Message(content=welcome).send()


# ============================================================
# Message Handler
# ============================================================


@cl.on_message
async def on_message(message: cl.Message):
    agent = _get_agent()
    query = message.content.strip()
    if not query:
        return
    response = await _run_query(agent, query)
    await _send_response(response)


# ============================================================
# Action Callbacks
# ============================================================


@cl.action_callback("follow_up")
async def on_follow_up(action: cl.Action):
    query = action.payload.get("query", "")
    if not query:
        return
    clean_query = query.split(" [")[0]
    agent = _get_agent()
    # Show the selected follow-up as a user message
    await cl.Message(content=clean_query, author="User", type="user_message").send()
    response = await _run_query(agent, clean_query)
    await _send_response(response)


# ============================================================
# Shared Logic
# ============================================================


def _get_agent() -> LedgerAIAgent:
    agent = cl.user_session.get("agent")
    if not agent:
        agent = LedgerAIAgent()
        cl.user_session.set("agent", agent)
    return agent


async def _run_query(agent: LedgerAIAgent, query: str) -> AgentResponse:
    async with cl.Step(name="Analyzing", type="run") as step:
        step.input = query
        response = agent.query(query)
        step.output = "Done"
    return response


async def _send_response(response: AgentResponse) -> None:
    elements = []
    content_parts = []

    # Confidence badge
    if response.confidence:
        content_parts.append(f"{_confidence_badge(response.confidence.level)}\n")

    # Main answer
    content_parts.append(response.answer)

    # Decomposition
    if response.decomposition:
        content_parts.append(f"\n---\n{response.decomposition.format_text()}")

    # Methodology (sidebar element)
    if response.methodology:
        elements.append(cl.Text(name="Methodology", content=response.methodology, display="side"))

    # Sources (sidebar element)
    if response.sources and response.sources != "No sources available.":
        elements.append(cl.Text(name="Sources", content=response.sources, display="side"))

    # Warnings
    if response.warnings:
        warnings_text = "\n".join(f"- {w}" for w in response.warnings)
        content_parts.append(f"\n**Warnings**\n{warnings_text}")

    # Confidence details
    if response.confidence:
        content_parts.append(
            f"\n**Confidence: {response.confidence.level.value}** "
            f"({response.confidence.score:.0%})\n"
            f"_{response.confidence.summary}_"
        )

    # Follow-up action buttons
    actions = []
    for follow_up in response.follow_ups:
        actions.append(
            cl.Action(
                name="follow_up",
                payload={"query": follow_up},
                label=follow_up.split(" [")[0],
            )
        )

    await cl.Message(
        content="\n".join(content_parts),
        elements=elements,
        actions=actions,
    ).send()


def _confidence_badge(level: ConfidenceLevel) -> str:
    badges = {
        ConfidenceLevel.HIGH: "**`HIGH CONFIDENCE`**",
        ConfidenceLevel.MEDIUM: "**`MEDIUM CONFIDENCE`**",
        ConfidenceLevel.LOW: "**`LOW CONFIDENCE`**",
        ConfidenceLevel.REFUSE: "**`CANNOT ANSWER`**",
    }
    return badges.get(level, "")
