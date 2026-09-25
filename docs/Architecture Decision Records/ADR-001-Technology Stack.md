# ADR-001: Technology Stack

**Status:** Accepted

## Context

The challenge requires a Python or Go API and an AI agent capable of using tools and external knowledge. The POC should also allow the LLM and embedding provider to evolve without coupling the application to a single vendor.

## Decision

Use Python with FastAPI for the application API. Use LangChain for model, tool, embedding, and retrieval abstractions, and LangGraph for agent orchestration and stateful execution. OpenAI and Gemini models should be selectable through configuration rather than embedded in business logic.

## Alternatives

* Go with a custom agent/tooling implementation.
* Python with direct provider SDKs.
* Python with LlamaSDK agent/tooling implementation.
* Python with LangChain but custom orchestration.

## Trade-offs

* Adds framework dependencies compared with direct SDK usage.
* Provides useful abstractions for provider and tool interchangeability.
* LangGraph adds structure that is useful if the agent workflow becomes stateful or multi-step.
* The application remains responsible for business logic rather than delegating it to the frameworks.

## Revisit when

Revisit if the frameworks introduce unnecessary complexity or prevent the agent from remaining simple and understandable.
