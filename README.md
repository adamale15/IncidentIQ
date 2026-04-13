# Incident Intelligence Platform (IIP)

An open-source RAG platform that ingests your incident history (postmortems, runbooks, Slack threads, PagerDuty alerts) and lets on-call engineers ask "Has this happened before? What fixed it?" during a live incident, getting grounded answers with source links in under 3 seconds.

## 🎯 Key Features

- **Multi-Source Ingestion**: Markdown postmortems, PagerDuty alerts, Slack threads
- **Hybrid Retrieval**: BM25 + dense vector search + metadata filtering + reranking
- **Streaming Chat Interface**: Get answers with inline citations in real-time
- **Built-in Evaluation**: RAGAS metrics tracked over time with regression detection
- **Full Observability**: OpenTelemetry tracing + Prometheus metrics + Grafana dashboards
- **Proactive Detection**: Similar incident detection when new alerts fire

## 🏗️ Architecture

```
Data Sources → Ingestion Pipeline → Qdrant Vector DB
                                         ↓
User Query → Query Engine → Hybrid Retrieval → Reranking → LLM Generation
                                         ↓
                              OpenTelemetry Traces → Prometheus → Grafana
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))
- Node.js 18+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/adamale15/IncidentIQ.git
cd IncidentIQ
```

2. **Configure environment variables**

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY and other credentials
```

3. **Start all services**

```bash
docker compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Qdrant (ports 6333, 6334)
- Redis (port 6379)
- FastAPI Backend (port 8000)
- Next.js Frontend (port 3000)
- Prometheus (port 9090)
- Grafana (port 3001)

4. **Access the application**

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Grafana: http://localhost:3001 (admin/admin)

## 📊 Evaluation Results

Coming soon - RAGAS metrics will be published here after Phase 2 implementation.

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LlamaIndex |
| Vector Store | Qdrant (hybrid search) |
| Sparse Retrieval | BM25 via Qdrant |
| Re-ranker | cross-encoder (ms-marco-MiniLM) |
| LLM | Google Gemini 1.5 Flash/Pro |
| Embedding | Gemini text-embedding-004 |
| Backend | FastAPI (Python 3.12) |
| Frontend | Next.js 15 + Tailwind |
| Auth | NextAuth.js (GitHub/Google OAuth) |
| Database | PostgreSQL 16 |
| Cache | Redis |
| Observability | OpenTelemetry + Prometheus + Grafana |
| Eval | RAGAS |

## 📖 Documentation

- [Product Requirements Document](./prd.md)
- [User Flows](./userflow.md)
- [Implementation Plan](./.cursor/plans/iip_implementation_plan_*.plan.md)

## 🧪 Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
cd backend
pytest
```

### Run Evaluation

```bash
cd backend
python -m app.evaluation.ragas_runner --run-type manual
```

## 🗺️ Roadmap

- [x] Phase 1: Retrieval Foundation (Week 1)
- [ ] Phase 2: Query Engine + Evaluation (Week 2)
- [ ] Phase 3: Frontend + Observability (Week 3)
- [ ] Phase 4: Polish + Additional Data Sources (Week 4)
- [ ] Phase 5: Differentiators (Week 5)
- [ ] Phase 6: Stretch Goals (Week 6+)

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Built with inspiration from production RAG systems at leading SRE-focused companies.
