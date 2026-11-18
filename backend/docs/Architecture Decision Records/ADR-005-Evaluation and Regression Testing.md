# ADR-005: Evaluation and Regression Testing

**Status:** Accepted

## Context

LLM behavior is probabilistic and changes in prompts, models, tools, or retrieval can affect existing behavior. The challenge requires a way to evaluate the agent and detect regressions.

## Decision

Maintain a small versioned evaluation set covering core user intents, tool selection, retrieval, business calculations, and expected response behavior. Run deterministic unit/integration tests together with agent evaluations when changing prompts, models, tools, or retrieval configuration.

## Alternatives

* Manual testing only.
* Unit tests without agent-level evaluation.
* External evaluation platforms from the beginning.

## Trade-offs

* Provides repeatable evidence when changing the agent.
* Requires maintaining representative evaluation cases.
* LLM-based evaluations may introduce their own variability.
* The initial evaluation set will be intentionally small for the POC.

## Revisit when

Revisit when the evaluation set or production traffic becomes large enough to require automated evaluation infrastructure or dedicated observability tooling.
