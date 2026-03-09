# ADR-001: Single Agent vs. Multi-Agent System

## Status
Accepted

## Decision
Single agent with modular internal components and tool-calling.

## Context
The system performs multiple functions — query understanding, data retrieval (SQL + vector), calculation, guardrail checking, confidence scoring, response formatting, and follow-up suggestions. This raises the question of whether these should be separate agents coordinating with each other.

## Why Single Agent

- **Debuggability.** When something goes wrong in a multi-agent system, you have to trace which agent failed, what it passed downstream, and whether the failure was in the handoff or the execution. A single agent with modular internal components lets you trace every decision through one call chain. For a project whose entire thesis is reliability and auditability, this is critical.

- **Latency.** Every agent-to-agent handoff is another LLM round trip. A multi-agent answer to "What was Apple's gross margin?" could take 8-12 seconds across multiple LLM calls. A single agent with deterministic tooling does it in 2-3 seconds.

- **The complexity is in context, not coordination.** The hard problems here are metric definitions, guardrail logic, and confidence scoring. These are context problems, not delegation problems. Adding more agents doesn't make the metric registry better — it just adds communication overhead.

- **Scope discipline.** Multi-agent systems are seductive to build but brutal to ship. Time spent on inter-agent protocols and shared state management is engineering effort with zero business value for this project.

## When to Reconsider
If the system is productized and needs genuinely autonomous subtasks (one agent researching while another analyzes industry trends) or agents with different security boundaries.
