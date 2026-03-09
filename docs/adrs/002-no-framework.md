# ADR-002: No Agent Framework

## Status
Accepted

## Decision
Build directly on the Anthropic Python SDK with custom Python orchestration. No agent framework (no ADK, LangGraph, CrewAI, etc.).

## Context
The current landscape includes Google ADK, LangGraph, CrewAI, AutoGen, and OpenAI Agents SDK. These frameworks provide abstractions for agent orchestration, tool management, and state handling.

## Why No Framework

- **Transparency is the product.** The whole thesis is "I understand what makes agents reliable in production." If wrapped in a framework, the framework makes the architecture decisions, not us. Every piece should be visible, explainable, and intentional.

- **The orchestration is simple.** The agent's flow is: classify query → retrieve data → assemble context → call LLM → validate output → score confidence → format response. That's ~100-150 lines of orchestration code. A framework adds abstraction around something that doesn't need abstracting.

- **Dependency risk.** Agent frameworks are evolving rapidly. Direct API calls to Claude are stable and well-documented.

- **Portability.** A project built on direct API calls with clean Python signals "I can work with whatever you have." This matters for consulting and potential clients on various cloud platforms.

## What Frameworks Solve That We Don't Need
- Multi-agent coordination → we have one agent
- Complex state machines with branching/looping → our flow is linear
- Managed deployment to cloud → we're deploying a Streamlit demo
- Session persistence across millions of users → we're demoing to prospects

## When to Reconsider
If productized into a platform with multiple agent configurations, persistent sessions, cloud deployment at scale, and multi-agent coordination.
