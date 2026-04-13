# Incident Intelligence Platform (IIP) - User Flows

## Flow 1: First-Time Setup & Data Ingestion

```
Landing Page
|
+-- User clicks "Get Started"
|
+-- GitHub/Google OAuth
|   +-- Authorize read access
|
+-- Create Workspace
|   +-- Name: "Acme SRE Team"
|   +-- Slug auto-generated: acme-sre-team
|
+-- Dashboard (empty state)
    +-- "Connect your first data source"
    +-- Three cards:
        +-- [Upload Postmortems] (Markdown files/folder)
        +-- [Connect PagerDuty] (API key)
        +-- [Import Slack Threads] (JSON export)
```

### Screen: Landing Page

- Hero: "Your incidents have answers. Find them."
- Subtext: "Index your postmortems, alerts, and Slack threads. Ask questions during your next outage. Get grounded answers in seconds."
- Two CTAs: "Get Started" (primary), "View Demo" (secondary, links to demo video)
- Below fold: architecture diagram + 3 stats (< 3s query latency, 85%+ faithfulness, 5 data sources supported)
- Social proof section: "Built for SRE teams" with logos of tools it integrates with (PagerDuty, Slack, Grafana, Confluence)

### Screen: Dashboard (Empty State)

- Welcome banner with workspace name
- Three source type cards, each with:
  - Icon + title
  - 1-line description
  - "Connect" button
- Below: "Or try with sample data" button that loads the synthetic incident corpus

---

## Flow 2: Ingesting Postmortems (Markdown Source)

```
User clicks "Upload Postmortems"
|
+-- Option A: Upload individual .md files (drag and drop)
+-- Option B: Point to a directory path (for Docker volume mount)
+-- Option C: Paste a GitHub repo URL containing postmortems
|
+-- POST /api/sources
|   { source_type: "markdown_dir", config: { path: "/data/postmortems" } }
|
+-- Backend kicks off ingestion job:
|   |
|   +-- Scan directory for .md files
|   |
|   +-- For each file:
|   |   +-- Parse Markdown headings as section boundaries
|   |   +-- Extract metadata from frontmatter (if YAML header exists):
|   |   |   severity, services, date, team, tags
|   |   +-- If no frontmatter, use LLM to extract metadata from content
|   |   +-- Section-aware chunking:
|   |   |   "Summary" -> 1 chunk
|   |   |   "Root Cause" -> 1 chunk
|   |   |   "Timeline" -> 1 chunk (or split if > 1000 tokens)
|   |   |   "Resolution" -> 1 chunk
|   |   |   "Action Items" -> 1 chunk
|   |   +-- Generate embeddings (batch, Gemini text-embedding-004)
|   |   +-- Generate sparse BM25 vectors
|   |   +-- Upsert to Qdrant with full payload metadata
|   |   +-- Store document + chunk records in PostgreSQL
|   |
|   +-- Update source status: syncing -> active
|
+-- UI shows real-time progress:
    +-- "Parsing documents... (12/50)"
    +-- "Generating embeddings... (batch 3/8)"
    +-- "Indexing in Qdrant..."
    +-- DONE: "50 postmortems indexed, 342 chunks created"
    +-- Stats card: services detected, severity distribution, date range
```

### Postmortem Parsing Detail

Input Markdown example:
```markdown
---
title: Payment Gateway Timeout
date: 2025-12-15
severity: P1
services: [payment-service, stripe-integration]
team: payments
---

## Summary
On Dec 15, the payment service experienced elevated latency...

## Timeline
- 14:02 UTC: First alert fired for payment-service p95 > 2s
- 14:05 UTC: On-call acknowledged, began investigation
...

## Root Cause
The Stripe webhook handler was not releasing HTTP connections...

## Resolution
Deployed hotfix to add connection pool timeout of 30s...

## Action Items
- [ ] Add connection pool monitoring to Grafana dashboard
- [ ] Set up alert for connection pool exhaustion
```

Output chunks:
```
Chunk 1: { type: "summary", service: "payment-service", severity: "P1", ... }
Chunk 2: { type: "timeline", service: "payment-service", ... }
Chunk 3: { type: "root_cause", service: "payment-service", ... }
Chunk 4: { type: "resolution", service: "payment-service", ... }
Chunk 5: { type: "action_items", service: "payment-service", ... }
```

---

## Flow 3: Ingesting PagerDuty Alerts

```
User clicks "Connect PagerDuty"
|
+-- Form: Enter PagerDuty API key + date range
|   +-- "Last 30 days" / "Last 90 days" / "All time" / Custom
|
+-- POST /api/sources
|   { source_type: "pagerduty", config: { api_key: "encrypted_xxx", range: "90d" } }
|
+-- Backend:
|   +-- Fetch incidents via PagerDuty REST API
|   +-- For each incident:
|   |   +-- Normalize to common schema:
|   |   |   title, description, service, severity, created_at,
|   |   |   resolved_at, acknowledged_by, escalation_policy, notes
|   |   +-- Group related alerts within 5-minute windows
|   |   |   (multiple alerts for same service = one "alert burst" document)
|   |   +-- Each incident becomes 1 document, 1-3 chunks:
|   |       +-- Alert details chunk
|   |       +-- Resolution notes chunk (if present)
|   |       +-- Linked postmortem reference (if URL in notes)
|   +-- Embed and index
|
+-- UI: "187 alerts imported from PagerDuty, 12 services detected"
```

---

## Flow 4: Ingesting Slack Threads

```
User clicks "Import Slack Threads"
|
+-- Option A: Upload Slack export JSON
+-- Option B: Paste Slack API token + channel list
|
+-- Backend:
|   +-- For each incident channel (matching pattern: #incident-*)
|   |   +-- Fetch thread messages
|   |   +-- Merge consecutive messages from same author
|   |   +-- Chunk by conversation turn:
|   |       Message A (question) + Message B (answer) = 1 chunk
|   |       Keep 2-message overlap for context
|   |   +-- Extract metadata:
|   |       channel name, participants, timestamps, mentioned services
|   |   +-- If thread mentions a postmortem link, create cross-reference
|   +-- Embed and index
|
+-- UI: "23 incident threads imported from 3 channels"
```

---

## Flow 5: Asking a Question (Core Query Loop)

```
User navigates to Chat from dashboard
|
+-- Chat interface loads:
|   +-- Left sidebar: workspace info, data source status, past conversations
|   +-- Center: chat panel
|   +-- Right (collapsible): source chunks panel
|
+-- User types: "What caused the payment service outage in December?"
|
+-- POST /api/query
|   {
|     question: "What caused the payment service outage in December?",
|     conversation_id: null
|   }
|
+-- Backend Query Pipeline (all steps traced with OpenTelemetry):
|
|   SPAN 1: query_parse (15ms)
|   +-- Extract metadata filters from natural language:
|   |   service: "payment-service"
|   |   date_range: "2025-12-01 to 2025-12-31"
|   +-- Classify query type: "causal_reasoning"
|   +-- Rewrite query for retrieval:
|       Original: "What caused the payment service outage in December?"
|       Rewritten: "payment service outage root cause December 2025"
|
|   SPAN 2: embedding_generation (80ms)
|   +-- Embed rewritten query via Gemini text-embedding-004
|
|   SPAN 3: hybrid_retrieval (120ms)
|   +-- Dense search: top 20 by cosine similarity (weight 0.7)
|   +-- Sparse BM25 search: top 20 by keyword match (weight 0.3)
|   +-- Apply metadata filters: service="payment*", date>=2025-12-01
|   +-- Reciprocal Rank Fusion to merge dense + sparse results
|   +-- Return top 20 candidates
|
|   SPAN 4: reranking (50ms)
|   +-- Cross-encoder (MiniLM) scores each (query, chunk) pair
|   +-- Sort by re-rank score
|   +-- Return top 5
|
|   SPAN 5: context_assembly (5ms)
|   +-- Deduplicate overlapping chunks (same document, adjacent sections)
|   +-- Order: root_cause chunks first, then timeline, then resolution
|   +-- Attach parent document title to each chunk
|   +-- Truncate total context to 8K tokens
|   +-- Build prompt:
|       System: "You are an SRE assistant. Answer based ONLY on
|               the incident context below. Cite sources using
|               [Source: document_title, date] format. If context
|               is insufficient, say so."
|       Context: [5 chunks with metadata headers]
|       Question: "What caused the payment service outage in December?"
|
|   SPAN 6: llm_generation (streaming, 800ms TTFT)
|   +-- Gemini 1.5 Flash streaming response
|   +-- Extract citations as response streams
|   +-- Save message pair to PostgreSQL
|   +-- Log: latency, retrieval scores, model, token count
|
+-- UI streams the response:
|   +-- Markdown rendered progressively
|   +-- Inline citations appear as colored chips:
|       [Postmortem: Payment Gateway Timeout, 2025-12-15]
|   +-- Right panel populates with source chunks:
|       Each shows: relevance score (0.94), chunk type badge,
|       first 3 lines of content, "Expand" button
|
+-- Below the response:
    +-- Feedback: thumbs up / thumbs down
    +-- "View trace" link (opens Grafana trace view for this query)
    +-- Suggested follow-ups:
        "What were the action items?"
        "Has this service had similar issues before?"
        "Show me the timeline of this incident"
```

### Chat Interface Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Logo] Incident Intelligence    [Workspace: Acme SRE ▼]      [⚙]  │
├───────────────┬──────────────────────────────┬───────────────────────┤
│               │                              │                       │
│  DATA SOURCES │  USER                        │  SOURCES              │
│  ───────────  │  What caused the payment     │  ─────────            │
│  ● Postmortems│  service outage in December? │                       │
│    50 docs    │                              │  [0.94] root_cause    │
│  ● PagerDuty │  ASSISTANT                   │  Payment Gateway      │
│    187 alerts │  Based on the postmortem     │  Timeout              │
│  ● Slack     │  from December 15, the root  │  "The Stripe webhook  │
│    23 threads │  cause was that the Stripe   │  handler was not..."  │
│               │  webhook handler was not     │  [Expand]             │
│  CONVERSATIONS│  releasing HTTP connections  │                       │
│  ───────────  │  back to the pool. [Source:  │  [0.87] timeline      │
│  > Payment    │  Payment Gateway Timeout,    │  Payment Gateway      │
│    outage...  │  2025-12-15]                 │  Timeout              │
│  > Auth       │                              │  "14:02 UTC: First    │
│    service... │  The connection pool         │  alert fired..."      │
│  > Redis      │  exhaustion caused cascading │  [Expand]             │
│    cache...   │  timeouts across all payment │                       │
│               │  endpoints, with p95 latency │  [0.82] resolution    │
│               │  exceeding 10 seconds.       │  Payment Gateway      │
│               │  [Source: PagerDuty Alert     │  Timeout              │
│               │  #4521, 2025-12-15]          │  "Deployed hotfix..." │
│               │                              │  [Expand]             │
│               │  Action items included adding │                       │
│               │  connection pool monitoring   │  ─────────            │
│               │  to Grafana and setting up    │  [View Trace]        │
│               │  exhaustion alerts.           │  Total: 1.07s        │
│               │                              │  Retrieval: 170ms     │
│               │  👍 👎  [View trace]         │  Rerank: 48ms         │
│               │                              │  LLM: 812ms           │
│               │  Suggested:                  │                       │
│               │  [Has this happened before?] │                       │
│               │  [Show me the timeline]      │                       │
│               │                              │                       │
│               │  ┌────────────────────────┐  │                       │
│               │  │ Ask about incidents... │  │                       │
│               │  └────────────────────────┘  │                       │
└───────────────┴──────────────────────────────┴───────────────────────┘
```

---

## Flow 6: Query Types and Routing

### Simple Lookup
```
User: "What's the runbook for restarting the auth service?"

-> Classifier: SIMPLE_LOOKUP
-> Retrieval: Filter chunk_type=runbook_step, service=auth
-> No multi-hop needed
-> Direct answer with runbook steps
-> Latency target: < 1.5s
```

### Causal Reasoning
```
User: "Why did the cart service fail on March 12?"

-> Classifier: CAUSAL_REASONING
-> Retrieval: Filter service=cart, date=2025-03-12
-> Prioritize: root_cause chunks first, then timeline
-> Prompt instructs: "Explain the chain of events that led to the failure"
-> Latency target: < 3s
```

### Comparison
```
User: "How does last week's DB outage compare to the one in January?"

-> Classifier: COMPARISON
-> Two parallel retrievals:
   Search 1: service=database, date=last_7_days
   Search 2: service=database, date=2025-01-01 to 2025-01-31
-> Merge results, deduplicate
-> Prompt instructs: "Compare these two incidents: similarities, differences,
   and whether the same root cause applies"
-> Latency target: < 4s
```

### Timeline Reconstruction
```
User: "Walk me through the payment incident from start to resolution"

-> Classifier: TIMELINE
-> Retrieval: service=payment, sort by date, retrieve ALL chunk types
-> Priority: timeline > alert > discussion > resolution
-> Prompt instructs: "Reconstruct a chronological narrative of this incident"
-> Latency target: < 4s
```

---

## Flow 7: Evaluation Dashboard

```
User navigates to /eval from sidebar
|
+-- Eval Overview:
|   +-- Latest run: April 10, 2026 (nightly)
|   +-- Score cards:
|       Faithfulness: 0.88 (+0.02 from last week)
|       Answer Relevancy: 0.83 (-0.01)
|       Context Precision: 0.79 (+0.03)
|       Context Recall: 0.76 (stable)
|
+-- Trend Charts:
|   +-- Line chart: all 4 metrics over last 30 days
|   +-- Regression alerts highlighted in red
|
+-- Per-Question Breakdown (table):
|   +-- Question | Expected | Generated | Faithfulness | Precision | Pass/Fail
|   +-- Click any row to see full detail:
|       +-- Retrieved chunks with scores
|       +-- Side-by-side: expected vs generated answer
|       +-- Which chunks were relevant vs. retrieved
|
+-- Actions:
    +-- "Run Eval Now" button
    +-- "Edit Golden Dataset" (opens editor for Q&A pairs)
    +-- "Export Results" (CSV download)
```

### Eval Dashboard Layout
```
┌────────────────────────────────────────────────────────────────────┐
│  Evaluation Dashboard                    [Run Eval Now] [Export]    │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │ Faithful.  │  │ Answer Rel │  │ Ctx Prec.  │  │ Ctx Recall │   │
│  │   0.88     │  │   0.83     │  │   0.79     │  │   0.76     │   │
│  │   +0.02    │  │   -0.01    │  │   +0.03    │  │   stable   │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              METRICS OVER LAST 30 DAYS                       │  │
│  │  1.0 ─┬──────────────────────────────────────────────────    │  │
│  │       │  ____faithfulness____                                │  │
│  │  0.8 ─┤ /                    \_____                          │  │
│  │       │/  ___answer_rel___          \___                     │  │
│  │  0.6 ─┤ /                                                    │  │
│  │       │     ___ctx_precision___                               │  │
│  │  0.4 ─┤                                                      │  │
│  │       └──────────────────────────────────────────────────    │  │
│  │        Mar 11        Mar 21        Mar 31        Apr 10      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  PER-QUESTION RESULTS (Latest Run: 50 questions)                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ # │ Question                        │ Faith │ Prec │ Status │  │
│  │ 1 │ What caused the payment outage? │ 0.95  │ 0.90 │ PASS   │  │
│  │ 2 │ How was Redis cache fixed?      │ 0.78  │ 0.65 │ FAIL   │  │
│  │ 3 │ What's the auth service runbook?│ 0.92  │ 0.88 │ PASS   │  │
│  │...│ ...                             │ ...   │ ...  │ ...    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Flow 8: Observability (Grafana Dashboards)

```
User clicks "View Trace" on any query response
|
+-- Opens Grafana trace view (embedded or linked):
    +-- Full trace waterfall:
        query_parse      [=====]                          15ms
        embed_query           [========]                  80ms
        hybrid_retrieval              [==========]        120ms
        reranking                              [====]     50ms
        context_assembly                           [=]    5ms
        llm_generation                              [===============] 812ms
        ──────────────────────────────────────────────────────────
        total                                                   1.07s

User navigates to pre-built Grafana dashboard:
|
+-- Panel 1: Query Latency (p50, p95, p99 over time)
+-- Panel 2: Retrieval Quality (avg top-1 similarity score)
+-- Panel 3: Queries per Hour
+-- Panel 4: Feedback Ratio (positive / total)
+-- Panel 5: Token Usage (cumulative, per model)
+-- Panel 6: Eval Score Trends (faithfulness, precision)
+-- Panel 7: Retrieval Score Distribution (histogram)
+-- Panel 8: Error Rate (failed queries / total)
```

---

## Flow 9: Source Chunk Viewer

```
User clicks a citation chip in a response:
  [Postmortem: Payment Gateway Timeout, 2025-12-15]
|
+-- Expandable panel slides in from the right:
|
+-- Header:
|   +-- Document title: "Payment Gateway Timeout"
|   +-- Source type badge: "Postmortem"
|   +-- Date: December 15, 2025
|   +-- Severity: P1
|   +-- Services: payment-service, stripe-integration
|   +-- Team: Payments
|
+-- Chunk content (syntax highlighted if code):
|   +-- Section: "Root Cause"
|   +-- Full text of the chunk
|   +-- Highlighted: the specific sentences that matched the query
|
+-- Context:
|   +-- "View full document" link (opens the complete postmortem)
|   +-- "Other chunks from this document" (expandable list)
|   +-- Relevance score: 0.94
|   +-- Retrieval method: "Dense + BM25 (hybrid)"
|
+-- Close button returns to chat
```

---

## Flow 10: Similar Incident Detection (Proactive, P2)

```
External: PagerDuty fires a new alert
|
+-- Webhook hits POST /api/webhooks/pagerduty
|
+-- Backend:
|   +-- Parse alert payload
|   +-- Embed alert description
|   +-- Search Qdrant for top 3 most similar past incidents
|   +-- Filter: only return matches with score > 0.70
|
+-- If matches found:
|   +-- POST to Slack webhook:
|       "🔍 IIP detected similar past incidents for alert:
|        `CartService latency > 2s` (P2, cart-service)
|
|        Similar incidents:
|        1. [92% match] Cart service degradation - Redis pool exhaustion
|           (2025-11-20, P1) - Fixed by increasing pool size
|        2. [78% match] Cart checkout timeouts - DB connection leak
|           (2025-09-03, P1) - Fixed by adding connection timeout
|        3. [71% match] Cart API 504s during peak traffic
|           (2025-07-15, P2) - Fixed by scaling replicas
|
|        View details: https://iip.yourteam.dev/similar/alert-xyz"
|
+-- Dashboard also shows a "Recent Alerts" feed with matches
```

---

## Error States

### No Relevant Results Found
```
User: "What happened to the billing microservice?"
(No billing service in the corpus)

Response:
"I couldn't find any incidents related to a billing service in your
indexed data. The services I have data for are: auth, payment, cart,
search, notification, API gateway, database, and cache.

Could you check if:
- The service has a different name in your postmortems?
- Billing incidents are stored in a data source that hasn't been connected yet?"
```

### Low Confidence Retrieval
```
(Top retrieval score < 0.50)

Response:
"I found some potentially related information, but my confidence is low.
Here's what I found, but please verify:

[Answer with heavy caveats and lower-ranked citations]

Retrieval confidence: Low (best match: 0.43)
Consider rephrasing your question or checking if relevant postmortems
have been indexed."
```

### Ingestion Failures
```
Source sync fails (API timeout, bad credentials, parse error)

Dashboard shows:
- Source card turns red with error badge
- Error detail: "PagerDuty API returned 401. Check your API key."
- "Retry" button + "Edit Config" button
- Last successful sync timestamp preserved
```

### Rate Limited
```
Gemini API returns 429

User sees:
- "Processing your question..." with spinner
- Backend retries with exponential backoff (1s, 2s, 4s)
- After 3 retries: "The AI service is temporarily busy. Your question
  has been queued and will be answered in approximately 30 seconds."
```

---

## Implementation Priority (Build Order)

### Week 1: Retrieval Foundation
- [ ] Project scaffold: FastAPI + Docker Compose (PostgreSQL, Qdrant, Redis)
- [ ] BaseConnector interface + MarkdownConnector implementation
- [ ] Section-aware chunking for postmortems
- [ ] Gemini embedding integration (batch)
- [ ] BM25 sparse vector generation
- [ ] Qdrant hybrid upsert (dense + sparse + payload)
- [ ] Basic hybrid retrieval endpoint (no re-ranking yet)
- [ ] Create synthetic incident corpus (50 postmortems, 200 alerts)
- [ ] Create golden eval dataset (50 Q&A pairs)

### Week 2: Query Engine + Eval
- [ ] Query metadata extraction (service, date filters from natural language)
- [ ] Cross-encoder re-ranking integration
- [ ] Context assembly logic (dedup, ordering, truncation)
- [ ] Gemini streaming generation with citation extraction
- [ ] RAGAS eval harness (faithfulness, relevancy, precision, recall)
- [ ] First eval run: measure baseline scores, iterate on chunking/retrieval
- [ ] PostgreSQL schema for eval_runs and eval_results
- [ ] GitHub Actions workflow for nightly eval

### Week 3: Frontend + Observability
- [ ] Next.js chat interface with streaming SSE
- [ ] Citation chips (clickable, expandable source viewer)
- [ ] Source chunks panel (right sidebar)
- [ ] OpenTelemetry instrumentation (all 7 spans)
- [ ] Prometheus metrics endpoint
- [ ] Grafana dashboard JSON (import-ready)
- [ ] Conversation persistence (save/load/list)
- [ ] Feedback collection (thumbs up/down per message)

### Week 4: Polish + Data Sources
- [ ] PagerDuty connector
- [ ] Slack thread connector
- [ ] Query router (classify: simple / causal / comparison / timeline)
- [ ] Eval dashboard page in frontend
- [ ] Docker Compose with all services (API, frontend, Qdrant, PG, Redis, Prometheus, Grafana)
- [ ] README: architecture diagram, setup guide, eval scores, screenshots

### Week 5: Differentiators
- [ ] Incremental ingestion (content hash-based change detection)
- [ ] Similar incident detection webhook
- [ ] Slack notification for similar incidents
- [ ] CLI tool: `iip query "..."`
- [ ] Load testing with Locust (your existing expertise)
- [ ] Demo video recording
- [ ] Deploy to GCP Cloud Run

### Week 6: Stretch
- [ ] Incident knowledge graph (service-to-service relationships)
- [ ] Team-scoped access control
- [ ] Cross-workspace queries
- [ ] Advanced Grafana dashboards (retrieval score distributions, per-service accuracy)
