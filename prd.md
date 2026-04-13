# Incident Intelligence Platform (IIP) - Product Requirements Document

## The Pitch

An open-source RAG platform that ingests your incident history (postmortems, runbooks, Slack threads, PagerDuty alerts, Grafana dashboards) and lets on-call engineers ask "Has this happened before? What fixed it?" during a live incident, getting grounded answers with source links in under 3 seconds.

## Why This Project

### The Problem is Real and Unsolved

Every SRE team has the same experience: it's 2 AM, an alert fires, and the on-call engineer spends 20 minutes digging through Confluence, old Slack threads, and past JIRA tickets trying to figure out if this has happened before and what the fix was. The context exists somewhere in the organization, but it's scattered across 5-6 tools and buried in unstructured text.

Existing incident management tools (incident.io, Rootly, FireHydrant, PagerDuty) focus on the workflow layer: who gets paged, how incidents are tracked, and how postmortems are generated. None of them do deep semantic retrieval over your historical incident corpus to surface relevant past context during a live incident.

### Why It Positions You as an AI Engineer

This is not "I called an LLM API." It forces you to solve every hard problem in production RAG:

1. **Multi-source ingestion** with different document structures (Markdown postmortems vs. JSON alerts vs. conversational Slack threads)
2. **Hybrid retrieval** (BM25 + vector search + metadata filtering)
3. **Evaluation framework** with measurable metrics (retrieval recall, faithfulness, latency)
4. **Observability over the RAG pipeline itself** (trace every query, log retrieval scores, detect drift)
5. **Agentic query routing** (simple lookup vs. multi-hop reasoning vs. timeline reconstruction)

### Why It's Resume-Worthy

- Solves a real problem that SRE teams at every company face
- Open-source with a clear README and architecture diagram gets GitHub stars
- Demonstrates production RAG patterns that companies are actively hiring for
- Directly relevant to roles at Grafana Labs, Datadog, PagerDuty, incident.io, Google Cloud SRE tooling

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Orchestration | LlamaIndex | Best abstractions for multi-source ingestion, node parsing, and query engines |
| Vector Store | Qdrant (self-hosted via Docker) | Supports hybrid search natively (dense + sparse vectors), metadata filtering, and payload storage. Production-grade unlike FAISS. |
| Sparse Retrieval | BM25 via Qdrant's built-in sparse vectors | Catches exact-match queries that embedding models miss (error codes, service names, alert IDs) |
| Re-ranker | Cohere Rerank API or cross-encoder (ms-marco-MiniLM-L-6-v2) | Precision boost on top-k results before LLM prompt |
| LLM | Google Gemini 1.5 Flash (primary), Gemini 1.5 Pro (complex queries) | Fast, cheap, 1M token context window for fallback |
| Embedding | Gemini text-embedding-004 (768 dim) | Strong performance, free tier generous |
| Backend | FastAPI (Python 3.12) | Async-native, OpenAPI docs auto-generated, easy to test |
| Frontend | Next.js 15 (App Router) + Tailwind | Your strongest frontend stack |
| Auth | GitHub OAuth / Google OAuth via NextAuth.js | Teams authenticate, scoped data access |
| Database | PostgreSQL 16 | Metadata, users, conversations, eval results. JSONB for flexible schema. |
| Cache | Redis | Query result caching, rate limiting, job queue (RQ) |
| Observability | OpenTelemetry + Prometheus + Grafana | Trace every RAG query end-to-end, dashboard retrieval quality metrics |
| Eval Framework | RAGAS + custom test harness | Automated nightly eval runs against golden dataset |
| Infra | Docker Compose (local), GCP Cloud Run (prod) | One-command setup |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                          │
│  Confluence/Notion  │  Slack  │  PagerDuty  │  GitHub Issues │
│  (Markdown exports) │ (API)   │   (API)     │    (API)       │
└────────┬────────────┴────┬────┴──────┬──────┴───────┬───────┘
         │                 │           │              │
         ▼                 ▼           ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                         │
│                                                               │
│  Source Connectors -> Document Parser -> Chunking Engine      │
│                       (per-source)       (semantic+structural)│
│                                                               │
│  Metadata Extractor -> Embedding Gen -> Qdrant Upsert         │
│  (severity, service,    (Gemini)         (dense + sparse)     │
│   date, team, tags)                                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      QDRANT VECTOR DB                        │
│                                                               │
│  Collection: incidents                                        │
│  - Dense vector (768 dim, Gemini embedding)                  │
│  - Sparse vector (BM25 tokens)                               │
│  - Payload: file_path, source_type, service, severity,       │
│             date, team, chunk_type, parent_doc_id             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      QUERY ENGINE                            │
│                                                               │
│  User Query                                                   │
│     |                                                         │
│     |-> Query Classifier (simple / multi-hop / timeline)     │
│     |-> Query Rewriter (expand acronyms, add synonyms)       │
│     |-> Hybrid Retrieval (dense + sparse + metadata filter)  │
│     |-> Re-ranker (cross-encoder or Cohere)                  │
│     |-> Context Assembly (dedupe, order, truncate)           │
│     |-> LLM Generation (Gemini, streaming)                   │
│          |-> Citation extraction + source linking             │
│                                                               │
│  Every step emits OpenTelemetry spans                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY LAYER                        │
│                                                               │
│  Prometheus Metrics:                                          │
│  - iip_query_latency_seconds (histogram)                     │
│  - iip_retrieval_score_top1 (gauge)                          │
│  - iip_retrieval_chunks_returned (histogram)                 │
│  - iip_llm_tokens_used (counter)                             │
│  - iip_query_feedback_positive (counter)                     │
│  - iip_eval_faithfulness_score (gauge, from nightly runs)    │
│                                                               │
│  Grafana Dashboards:                                          │
│  - Query Performance (latency p50/p95/p99)                   │
│  - Retrieval Quality (avg top-1 score, feedback ratio)       │
│  - Eval Trends (faithfulness, recall over time)              │
└─────────────────────────────────────────────────────────────┘
```

## Core Features

### P0 - Production MVP (Weeks 1-3)

**1. Multi-Source Ingestion Pipeline**

The system must ingest incident data from at least 3 source types:

- **Markdown files** (postmortem exports from Confluence/Notion/GitHub): Parse headings as section boundaries. Extract structured fields (Severity, Services Affected, Root Cause, Timeline, Action Items) as metadata.
- **JSON/webhook payloads** (PagerDuty alerts, OpsGenie incidents): Normalize to a common incident schema. Extract service name, severity, timestamp, description, resolution notes.
- **Slack thread exports** (JSON from Slack API or export): Treat each thread as a document. Merge consecutive messages from the same author. Extract timestamps, usernames, channel names as metadata.

Each source type gets its own connector class implementing a `BaseConnector` interface. Adding a new source means implementing one class.

**2. Intelligent Chunking Engine**

Not all documents should be chunked the same way:

- **Postmortems**: Section-aware chunking. "Root Cause" section stays as one chunk. "Timeline" section stays as one chunk. Never split a section mid-paragraph.
- **Alert payloads**: Each alert is one chunk (they're already small). Group related alerts within a 5-minute window into a single "alert burst" chunk.
- **Slack threads**: Chunk by conversation turn (question-answer pairs). Keep 2-message overlap between chunks for context.

Every chunk includes metadata:
- `source_type`: postmortem | alert | slack_thread | runbook
- `service`: the service(s) mentioned
- `severity`: p0 | p1 | p2 | p3 | unknown
- `date`: when the incident occurred
- `team`: owning team
- `chunk_type`: root_cause | timeline | resolution | discussion | alert | runbook_step

**3. Hybrid Retrieval with Metadata Filtering**

```
Step 1: Query Analysis
  Extract metadata filters from natural language
  "What caused the payment service outage last month?"
    -> service=payment, date=last_30_days

Step 2: Hybrid Search
  Dense vector search (semantic similarity): weight 0.7
  Sparse BM25 search (keyword matching): weight 0.3
  Apply metadata filters (service, severity, date range)
  Return top 20 candidates

Step 3: Re-ranking
  Cross-encoder scores each (query, chunk) pair
  Return top 5 after re-ranking

Step 4: Context Assembly
  Deduplicate overlapping chunks
  Order by relevance score
  Include parent document title for each chunk
  Truncate to fit context window (8K tokens for context)
```

**4. Streaming Chat Interface**

- Clean chat UI built in Next.js
- Each answer includes inline citations: `[Postmortem: Payment Gateway Timeout, 2025-12-15]`
- Citations are clickable, expanding to show the source chunk
- "Sources" panel on the right showing all retrieved chunks with relevance scores
- Conversation history within session
- Workspace selector if multiple incident corpuses are indexed

**5. RAG Evaluation Framework**

This is what separates this project from every tutorial. Ship with a built-in eval system:

- **Golden dataset**: 50 question-answer pairs manually curated from your indexed incidents
- **Automated metrics** (via RAGAS):
  - `faithfulness`: Is every claim in the answer supported by retrieved context? Target: > 0.85
  - `answer_relevancy`: Does the answer address the question? Target: > 0.80
  - `context_precision`: Are the retrieved chunks relevant? Target: > 0.75
  - `context_recall`: Did retrieval surface all needed information? Target: > 0.75
- **Nightly eval runs**: GitHub Actions workflow runs the eval suite, stores results in PostgreSQL, exposes trends via Grafana
- **Regression detection**: If any metric drops > 5% from the 7-day average, log a warning

**6. Pipeline Observability**

Every query is traced end-to-end with OpenTelemetry:

- Span 1: `query_parse` (extract filters, classify query type)
- Span 2: `embedding_generation` (Gemini API call)
- Span 3: `hybrid_retrieval` (Qdrant search)
- Span 4: `reranking` (cross-encoder scoring)
- Span 5: `context_assembly` (dedup, truncate)
- Span 6: `llm_generation` (Gemini streaming)
- Span 7: `total_query` (end-to-end)

Prometheus metrics exported at `/metrics`. Pre-built Grafana dashboard JSON included in the repo.

### P1 - Enhanced (Weeks 4-5)

**7. Query Router (Agentic)**

Not all queries need the same pipeline:

- **Simple lookup**: "What's the runbook for restarting the auth service?" -> Direct retrieval, no multi-hop
- **Causal reasoning**: "Why did the cart service fail on March 12?" -> Retrieve timeline + root cause chunks, synthesize
- **Comparison**: "How does last week's DB outage compare to the one in January?" -> Parallel retrieval across two time ranges, comparative prompt
- **Timeline reconstruction**: "Walk me through the payment incident from start to resolution" -> Retrieve all chunks for that incident, order by timestamp, narrative prompt

A lightweight classifier (prompt-based) routes queries to the appropriate pipeline.

**8. Incremental Ingestion**

- Webhook endpoints for PagerDuty and Slack
- File watcher for Markdown directory (new postmortems dropped into a folder)
- Only embed and index new/changed documents (content hash comparison)
- Background job queue via Redis RQ

**9. Team-Scoped Access**

- Users belong to teams/workspaces
- Each workspace has its own incident corpus and Qdrant collection
- Cross-workspace queries are opt-in

### P2 - Differentiators (Week 6+)

**10. Similar Incident Detection (Proactive)**

When a new alert comes in via webhook, automatically find the 3 most similar past incidents and push a notification:

"New alert: `CartService latency > 2s`. This looks similar to:
- [2025-11-20] Cart service degradation due to Redis connection pool exhaustion (92% match)
- [2025-09-03] Cart checkout timeouts from DB connection leak (78% match)"

This is the killer feature. Proactive, not reactive.

**11. Incident Knowledge Graph**

Build a lightweight knowledge graph during ingestion:
- Nodes: services, teams, error types, infrastructure components
- Edges: "caused_by", "affected", "resolved_by", "owned_by"
- Enables queries like: "What services are most commonly affected when Redis goes down?"

**12. CLI Tool**

`iip query "has the auth service had connection pool issues before?"` from the terminal during an incident. No browser needed.

## Data Model

### `workspaces`
- id (UUID PK), name, slug (unique), created_at

### `users`
- id (UUID PK), workspace_id (FK), email, name, avatar_url, oauth_provider, oauth_id, created_at

### `data_sources`
- id (UUID PK), workspace_id (FK), source_type (enum: markdown_dir, pagerduty, slack, github_issues, opsgenie), config (JSONB, encrypted), status (enum: active, syncing, error, disabled), last_synced_at, created_at

### `documents`
- id (UUID PK), workspace_id (FK), data_source_id (FK), title, source_url, source_type, incident_date, severity, services (text[]), teams (text[]), raw_content (text), content_hash (varchar 64), created_at, updated_at

### `chunks`
- id (UUID PK), document_id (FK), workspace_id (FK), content (text), chunk_type, start_char, end_char, metadata (JSONB), qdrant_point_id (UUID), created_at

### `conversations`
- id (UUID PK), workspace_id (FK), user_id (FK), title, created_at, updated_at

### `messages`
- id (UUID PK), conversation_id (FK), role (enum: user, assistant), content (text), retrieved_chunk_ids (UUID[]), retrieval_scores (float[]), latency_ms, model_used, feedback (enum: positive, negative, null), created_at

### `eval_runs`
- id (UUID PK), workspace_id (FK), run_type (enum: nightly, manual, ci), faithfulness (float), answer_relevancy (float), context_precision (float), context_recall (float), total_questions (int), avg_latency_ms (int), created_at

### `eval_results`
- id (UUID PK), eval_run_id (FK), question (text), expected_answer (text), generated_answer (text), retrieved_chunks (UUID[]), faithfulness (float), answer_relevancy (float), context_precision (float), context_recall (float), latency_ms (int), created_at

## API Endpoints

### Auth
- `GET /auth/login` - Initiate OAuth
- `GET /auth/callback` - OAuth callback
- `GET /auth/me` - Current user + workspace

### Data Sources
- `POST /api/sources` - Register a data source
- `GET /api/sources` - List sources for workspace
- `POST /api/sources/:id/sync` - Trigger sync/ingestion
- `GET /api/sources/:id/status` - Sync progress

### Query
- `POST /api/query` - Ask a question (streaming SSE response)
- `POST /api/query/:message_id/feedback` - Thumbs up/down

### Conversations
- `GET /api/conversations` - List conversations
- `GET /api/conversations/:id` - Full conversation with messages
- `DELETE /api/conversations/:id` - Delete conversation

### Eval
- `POST /api/eval/run` - Trigger eval run
- `GET /api/eval/runs` - List eval runs with scores
- `GET /api/eval/runs/:id` - Detailed results per question
- `GET /api/eval/trends` - Score trends over time

### Admin
- `GET /api/stats` - Workspace stats
- `GET /metrics` - Prometheus metrics endpoint

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| End-to-end query latency (p95) | < 3 seconds |
| Retrieval latency (p95) | < 500ms |
| Ingestion throughput | 100 documents/minute |
| RAGAS faithfulness | > 0.85 |
| RAGAS context precision | > 0.75 |
| Max corpus size | 10,000 documents / 500K chunks |
| Concurrent queries | 25 |
| Docker Compose cold start | < 2 minutes |
| Test coverage (backend) | > 80% |

## What Makes This Production-Grade

1. **Hybrid retrieval, not just vector search.** BM25 + dense vectors + metadata filtering + re-ranking. This is the retrieval stack companies actually use.

2. **Built-in evaluation.** Golden dataset, automated RAGAS metrics, nightly runs, regression detection. You can point to a dashboard showing faithfulness scores over time.

3. **Observability over the RAG pipeline.** Every query is traced with OpenTelemetry. Prometheus metrics. Grafana dashboards. You're monitoring the AI system the same way you'd monitor any production service.

4. **Multi-source ingestion with proper document processing.** Not "upload a PDF." Structured connectors with different parsing strategies per source type.

5. **Agentic query routing.** Different query types get different retrieval and generation strategies.

6. **One-command deployment.** `docker compose up` gives you Qdrant, PostgreSQL, Redis, the API, the frontend, Prometheus, and Grafana all running.

## Sample Incident Data (For Demo)

Create a synthetic corpus using Gemini:

- 50 postmortems across 8 services (auth, payment, cart, search, notification, API gateway, database, cache)
- 200 PagerDuty-style alert payloads
- 30 Slack thread exports (simulated incident response conversations)
- 20 runbook Markdown files

Base them on common SRE failure patterns: connection pool exhaustion, memory leaks, certificate expiry, DNS failures, deployment rollbacks, database migration issues, rate limiting misconfigurations, cache stampedes.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Qdrant learning curve | Excellent Python client and Docker setup. Hybrid search is worth the investment over FAISS. |
| Evaluation dataset requires manual effort | Create 50 Q&A pairs during Week 1 while building the synthetic corpus. |
| Re-ranker adds latency | Use small cross-encoder (MiniLM, ~50ms). Cache results. Make it toggleable via config. |
| Gemini rate limits | Exponential backoff. Batch embeddings. Cache query embeddings. |
| Scope creep | The eval framework IS the project. Ship P0 with solid eval scores before touching P1. |

## Success Criteria

1. Demo video: ingest 50 postmortems, ask 5 diverse questions, get accurate cited answers in < 3 seconds
2. RAGAS eval scores published in README with exact numbers
3. Grafana dashboard screenshot in README showing query latency and retrieval quality metrics
4. `docker compose up` works on a clean machine with no manual setup beyond API keys
5. GitHub README has architecture diagram, setup instructions, eval results, and demo GIF
