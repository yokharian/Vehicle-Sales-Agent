# PRD: Knowledge Search Tool

**Version:** 1.0
**Status:** Accepted
**Tool:** `knowledge_search`

## 1. Purpose

Provide the AI sales agent with reliable, grounded information from an approved business knowledge base.

The tool retrieves relevant passages from indexed documents and returns them as evidence for the LLM. It does not generate answers or make business decisions.

Typical topics include:

* Kavak value proposition
* Purchase requirements
* Financing information
* Warranty information
* Other approved business documentation

The tool must not rely on the LLM's internal knowledge for facts that should come from the approved knowledge base.

---

## 2. Goals

* Retrieve relevant passages from approved documents.
* Support natural-language questions in Spanish and English.
* Support both semantic and keyword-based retrieval.
* Return source metadata with retrieved passages.
* Provide concise evidence for LLM response generation.
* Reduce unsupported factual claims.
* Make retrieval deterministic and testable for a fixed knowledge base.
* Keep the retrieval implementation independent from the LLM provider.
* Allow OpenAI and Gemini models/embeddings to be selected through configuration.

---

## 3. Non-Goals

* General web search.
* Answer generation.
* Vehicle catalog retrieval.
* Financing calculations.
* Conversation management.
* Autonomous multi-step agents.
* Automatic ingestion of arbitrary external content.
* Real-time crawling or synchronization of external websites.

---

## 4. Knowledge Source

The initial knowledge base consists of curated `.md` and `.txt` documents stored under:

```text
data/documents/
```

Example:

```text
data/documents/
├── kavak.md
├── financing.md
├── requirements.txt
└── warranty.md
```

Only approved documents are included in the runtime knowledge base.

The source documents are considered authoritative for the facts exposed through this tool.

The LLM must not independently invent or infer company policies when the knowledge base does not provide sufficient evidence.

---

## 5. Tool Interface

### Input

```json
{
  "query": "¿Qué documentos necesito para comprar un auto?",
  "k": 6
}
```

Parameters:

```text
query: str
k: int = 6
```

Constraints:

* `query` is required and must not be empty.
* `k` must be between 1 and 20.
* The tool may internally retrieve more candidates than `k` when required by the retrieval strategy.
* Internal retrieval parameters must not be exposed as part of the agent-facing contract unless needed.

### Output

The tool returns zero or more structured document results:

```json
[
  {
    "content": "...",
    "metadata": {
      "source": "requirements.txt",
      "chunk_index": 4
    }
  }
]
```

The external tool contract should remain independent of the underlying vector store, retriever implementation, embedding provider, and LLM provider.

---

## 6. Document Processing

Documents are transformed into retrieval chunks during an explicit indexing process.

Initial configuration:

```text
chunk size:    ~500 characters
overlap:       ~100 characters
file types:    .md, .txt
```

The chunking strategy should preserve headings and nearby context where possible.

Each chunk must retain enough metadata to identify its source document and position.

Example metadata:

```json
{
  "source": "financing.md",
  "chunk_index": 12
}
```

Unsupported file types and hidden files are ignored.

Document indexing must not happen on every user request.

---

## 7. Storage

PostgreSQL is the persistent datastore for the knowledge index.

The dense vector representation is stored using PostgreSQL with the `pgvector` extension.

The system stores, at minimum:

```text
document
chunk
content
metadata
embedding
```

The vector store is an implementation detail of `knowledge_search`. The tool's external contract must not depend on PostgreSQL-specific details.

A simplified indexing flow is:

```text
Approved documents
       │
       ▼
Parse documents
       │
       ▼
Split into chunks
       │
       ▼
Generate embeddings
       │
       ▼
Store chunks + metadata + embeddings
       │
       ▼
PostgreSQL + pgvector
```

The indexing process should be exposed through a repeatable CLI or application command.

---

## 8. Embedding Provider

The embedding implementation must be provider-agnostic.

The application should use a common embedding abstraction so that OpenAI and Gemini-compatible embedding models can be selected through configuration without changing the retrieval tool.

Conceptually:

```text
EmbeddingProvider
       │
       ├── OpenAI
       └── Gemini
```

The selected embedding model must be used consistently when indexing and querying the same vector index.

Changing embedding models requires re-indexing the affected documents.

The POC does not require supporting multiple embedding models in the same index.

---

## 9. Retrieval Strategy

The initial implementation uses hybrid retrieval combining:

1. **Dense vector retrieval**
2. **BM25 keyword retrieval**

### Dense retrieval

Dense retrieval uses embeddings stored in PostgreSQL/pgvector.

It is intended to capture semantic similarity and paraphrased questions.

Example:

```text
"¿Qué necesito llevar para comprar un vehículo?"
```

should be able to retrieve content discussing purchase requirements even when the wording differs.

### BM25 retrieval

BM25 is used for lexical matching.

It is particularly useful for:

* Exact terms
* Names
* Requirements
* Numbers
* Product terminology
* Short queries

Example:

```text
"tasa 10%"
```

may benefit from lexical matching because the exact term is significant.

### Ensemble retrieval

The initial implementation combines BM25 and dense retrieval through LangChain's retriever abstractions.

Conceptually:

```text
                    Query
                      │
              ┌───────┴───────┐
              ▼               ▼
            BM25          Dense Search
              │           PostgreSQL
              │             pgvector
              └───────┬───────┘
                      ▼
                Rank Fusion
                      │
                      ▼
                Top-K results
```

The initial ensemble weights are configuration parameters rather than business rules.

They must be evaluated against the retrieval test set before being treated as final.

For the POC, no additional search infrastructure is required.

---

## 10. Retrieval Abstractions

The retrieval implementation should use LangChain abstractions where practical.

The application should depend on interfaces such as:

```text
BaseRetriever
BaseEmbeddings
Document
```

rather than directly coupling the agent to PostgreSQL, pgvector, BM25, or a specific embedding provider.

The implementation may therefore evolve from:

```text
BM25 + PostgreSQL/pgvector
```

to another retrieval implementation without changing the `knowledge_search` tool contract.

---

## 11. Agent Integration

`knowledge_search` is exposed to the agent as a structured tool.

The agent is implemented using LangGraph for orchestration and LangChain tool/model abstractions.

The LLM provider is not part of the tool contract.

Conceptually:

```text
                    LangGraph Agent
                          │
                    Structured Tools
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
      knowledge_search           other tools
             │
             ▼
      Hybrid Retriever
        ┌────┴────┐
        ▼         ▼
      BM25     pgvector
                  │
                  ▼
             PostgreSQL
```

The agent may use an OpenAI or Gemini chat model through the same model abstraction.

Provider selection should be configuration-driven rather than implemented as provider-specific agent logic.

---

## 12. Grounding Contract

The tool returns evidence; it does not generate the final answer.

The orchestrator provides retrieved content to the LLM as explicit context.

The response-generation prompt should instruct the model to:

1. Prefer retrieved evidence for business facts.
2. Avoid unsupported factual claims.
3. State when the knowledge base does not contain enough information.
4. Distinguish retrieved facts from general conversational language.
5. Avoid exposing internal retrieval metadata unless appropriate.

A low-quality or empty retrieval result must not be treated as evidence.

The LLM must not fabricate a business fact as a fallback when retrieval fails.

---

## 13. Relevance and Retrieval Parameters

The following parameters should be configurable:

```text
top_k
BM25 candidate count
dense candidate count
ensemble weights
similarity threshold
```

The POC should start with simple defaults.

For example:

```text
final top_k:       6
BM25 candidates:   6
dense candidates:  6
```

Exact values and ensemble weights should be validated using the retrieval evaluation dataset.

A similarity score must not be interpreted as a guarantee that a passage is factually sufficient.

If evaluation demonstrates that a minimum relevance threshold improves precision, a configurable threshold may be introduced.

---

## 14. Error Handling

### No Documents

Return an empty result set and log the configuration problem.

### No Relevant Results

Return an empty result set.

The agent should then avoid making unsupported claims.

### Invalid Query

Return a validation error.

### Embedding Failure

Log the technical error and return a controlled tool error.

Do not generate a fabricated answer as a fallback.

### Database / Vector Store Failure

Log the technical error and return a controlled tool error.

Errors must not expose credentials, connection strings, or other sensitive information.

---

## 15. Performance Targets

Initial POC targets:

| Operation                |                          Target |
| ------------------------ | ------------------------------: |
| Document indexing        | <2 s for challenge-sized corpus |
| Query embedding          |                            <1 s |
| BM25 retrieval           |                         <100 ms |
| PostgreSQL vector search |                         <200 ms |
| End-to-end retrieval     |                         <500 ms |

These are engineering targets for the POC rather than challenge acceptance criteria.

Performance should be measured against the actual challenge dataset before introducing additional infrastructure.

---

## 16. Testing

### Unit Tests

Cover:

* document loading
* supported file types
* hidden-file handling
* chunking
* metadata integrity
* query validation
* empty knowledge base
* BM25 retrieval
* vector retrieval
* result ordering
* provider configuration

### Retrieval Evaluation

Create a small labeled evaluation dataset containing representative questions:

```text
"¿Qué documentos necesito para comprar?"
"¿Cómo funciona el financiamiento?"
"¿Qué ofrece Kavak?"
"¿Cómo funciona la garantía?"
```

For each query, identify acceptable source chunks.

Measure retrieval quality using metrics such as:

```text
Recall@K
Precision@K
MRR
```

The evaluation should compare:

```text
BM25
Dense
Hybrid
```

This provides evidence for whether the ensemble actually improves retrieval quality.

### Integration Tests

Cover:

```text
question
    ↓
LangGraph agent
    ↓
knowledge_search
    ↓
hybrid retrieval
    ↓
retrieved context
    ↓
LLM response
```

The final generated answer should be evaluated separately from retrieval quality.

---

## 17. Acceptance Criteria

The knowledge search capability is ready for integration when:

* Approved `.md` and `.txt` documents can be indexed.
* Document chunks and embeddings persist in PostgreSQL.
* Dense retrieval works through pgvector.
* BM25 retrieval works against the indexed corpus.
* Hybrid retrieval can combine both strategies.
* Every result contains source metadata.
* Retrieval returns only content from the approved knowledge base.
* Empty or irrelevant retrieval does not cause the system to invent facts.
* OpenAI and Gemini-compatible providers can be selected through configuration.
* The agent consumes retrieval through a stable structured tool interface.
* Retrieval behavior is covered by automated tests.
* Retrieval quality is measured against a small labeled evaluation set.
* The retrieval implementation can be replaced without changing the external `knowledge_search` contract.

---

## 18. Current Limitations

The POC intentionally does not support:

* PDF/DOCX ingestion.
* Automatic web crawling.
* Real-time external content synchronization.
* Multiple embedding models in the same index.
* Distributed search infrastructure.
* Advanced reranking models.
* Large-scale retrieval optimization.
* Production-grade document versioning.

These capabilities should only be introduced if production requirements justify the additional complexity.

---

## 19. Dependencies

Core dependencies:

* Python
* PostgreSQL
* pgvector
* Pydantic
* LangChain
* LangGraph
* BM25 implementation through LangChain
* OpenAI and/or Gemini provider integrations
* Pytest

The knowledge search tool must not depend on a specific LLM provider.

The tool is responsible for retrieval only; model selection and agent orchestration belong to the agent layer.

**Implementation:** `src/tools/knowledge_search.py`
**Documents:** `data/documents/`
**Index:** PostgreSQL + pgvector
**Tests:** `tests/test_knowledge_search.py`
