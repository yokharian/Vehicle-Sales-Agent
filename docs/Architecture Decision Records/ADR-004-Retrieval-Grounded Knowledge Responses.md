# ADR-004: Retrieval-Grounded Knowledge Responses

**Status:** Accepted

## Context

The agent must provide factual information about the business while minimizing unsupported claims. The knowledge base contains approved business information that should take precedence over the LLM's general model knowledge.

## Decision

Ground business knowledge responses in retrieved content from an approved knowledge base. The `knowledge_search` tool returns evidence, while the LLM is responsible only for using that evidence to formulate the response. Empty or insufficient retrieval must not be replaced with invented facts.

## Alternatives

* Rely on the LLM's pretrained knowledge.
* Allow unrestricted web search.
* Store business knowledge directly in prompts.

## Trade-offs

* Reduces unsupported business claims.
* Requires maintaining and evaluating the knowledge base.
* Retrieval quality becomes part of overall answer quality.
* Some questions may require an explicit "I don't have enough information" response.

## Revisit when

Revisit if the knowledge sources or freshness requirements require external search or a different knowledge architecture.
