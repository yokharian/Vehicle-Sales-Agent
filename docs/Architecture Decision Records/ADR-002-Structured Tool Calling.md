# ADR-002: Structured Tool Calling

**Status:** Accepted

## Context

The agent needs to interpret natural-language requests and perform operations such as catalog search, knowledge retrieval, and financial calculations. These operations require predictable behavior and, in some cases, explicit business rules that should not depend on free-form LLM reasoning.

## Decision

Use structured tool calling for agent actions. The LLM is responsible for interpreting user intent, selecting tools, and communicating results, while tools execute deterministic operations, retrieve authoritative data, and return structured results. Business rules such as financing calculations and catalog filtering will therefore live in application code rather than prompts or LLM-generated reasoning. LangGraph orchestrates the interaction between the model, tools, and conversation state.

## Alternatives

* Open-ended ReAct agent with business logic delegated to LLM reasoning.
* Hard-coded intent classification followed by application logic.
* Implement business rules directly in prompts.
* A fully scripted conversation flow.
* External business rules engine.

## Trade-offs

* More predictable and testable behavior.
* Business logic remains independent from the LLM and can be tested deterministically.
* Requires well-defined tool contracts and explicit business rules.
* Less flexibility for unexpected multi-step reasoning.
* Changes to business rules require code changes rather than prompt changes.

## Revisit when

Revisit if the agent requires substantially more autonomous planning or if business rules become sufficiently complex to justify a dedicated rules engine or external domain service.