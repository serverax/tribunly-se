# Mother Algorithm Control Plane v1

Distributed control system for lawapp: ingestion, legal truth DB, RAG+Graph (Postgres),
agent swarm, governance, learning, and documents.

**Owner alignment (binding):**
- Graph store: PostgreSQL `legal_nodes` / `legal_edges` (NOT Neo4j)
- Control plane: Python FastAPI at `backend/core/control_plane/` (NOT TypeScript orchestrator)
- DB is truth: LLM never writes law tables; ingestion-only + proposal queue (082/083)

---

## ASCII architecture

```
                         +------------------+
                         |  Client / API    |
                         |  POST /assess    |
                         |  POST /api/diag  |
                         +--------+---------+
                                  |
                                  v
+------------------+    +---------+----------+     +----------------------+
| Ingestion Engine |    |  MotherController   |     |  Agent Swarm         |
| connectors/      |    |  control_plane/     |     |  registry.py +       |
| validation/      +--->|  mother_controller  +---->|  swarm_agents.py     |
| quarantine 083   |    +---------+----------+     +----------+-----------+
+------------------+              |                            |
                                  |                            |
     +----------------------------+----------------------------+
     |                            |                            |
     v                            v                            v
+----+----+              +--------+--------+           +-------+-------+
| Postgres |              | ReasoningRouter |           | GraphController|
| rules    |              | RAG + rules +   |           | legal_nodes/   |
| corpus   |              | pipeline.assess |           | legal_edges    |
| chunks   |              +--------+--------+           +-------+-------+
| graph    |                       |                            |
+----+----+                       v                            |
     ^                   +--------+--------+                   |
     |                   | GovernanceEngine  |<----------------+
     |                   | legal_truth_val.  |
     |                   | govern + Critic   |
     |                   +--------+--------+
     |                            |
     |                   +--------+--------+
     |                   | MemoryStore     |
     |                   | agent_memory    |
     |                   | feedback_registry|
     |                   +--------+--------+
     |                            |
     |                   +--------+--------+
     +-------------------| LearningLoop    |
                         | knowledge_proposer|
                         | ingestion_proposals 082|
                         +-------------------+
```

---

## Module map (repo path + port)

| Module | Repo path | Port / service |
|--------|-----------|----------------|
| API monolith | `backend/api/main.py` | **8000** (backend) |
| Mother control plane | `backend/core/control_plane/` | in-process (8000) |
| Brain pipeline | `backend/core/brain.py` | in-process |
| Orchestrator | `backend/core/orchestrator.py` | in-process |
| Pipeline assess | `backend/core/pipeline.py` | in-process |
| Retrieve / RAG | `backend/core/retrieve.py` | in-process + **8017** rag-service |
| Graph (Postgres) | `backend/core/legal_graph.py`, `graph_controller.py` | in-process + **8018** graph-rag-service |
| Rules engine | `backend/domains/employment/` | in-process + **8016** rules-service |
| Legal truth validator | `backend/core/legal_truth_validator.py` | in-process |
| Knowledge proposer | `backend/core/knowledge_proposer.py` | in-process |
| Governance | `backend/core/govern.py`, `governance_engine.py` | in-process |
| Ingestion connectors | `ingestion/connectors/` | batch jobs |
| Ingestion validation | `ingestion/validation/` | in-process |
| Agent registry | `backend/core/agents/registry.py` | in-process |
| Swarm agents | `backend/core/agents/swarm_agents.py` | in-process |
| Postgres + pgvector | `db/migrations/` | **5432** (db) |
| Redis (rate limit) | docker-compose | **6379** |
| Ollama (local LLM) | host.docker.internal | **11434** |
| Audit service | `services/lawapp-audit-service/` | **8020** |
| Redaction service | `services/lawapp-redaction-service/` | **8019** |

---

## Agent swarm

| Agent | Role | Delegates to |
|-------|------|--------------|
| IntakeAgent | Classify, scope, missing facts | `classify`, `detect_gaps` |
| RetrievalAgent | Hybrid RAG + rules bundle | `retrieve`, bundle metrics |
| GraphAgent | Postgres graph context | `GraphController`, `legal_graph` |
| ReasoningAgent | Governed assessment | `pipeline.assess` |
| RiskAgent | Weaknesses, human review | deterministic risk heuristics |
| JudgeAgent | Legal truth + citations | `legal_truth_validator`, `citation_verifier` |
| DocumentAgent | Self-help drafts | `documents.generate_*` |

All agents register in `backend/core/agents/registry.py` and trace stages via
`control_plane_stages` / `brain_traces.orchestration_stages`.

---

## Control flow

```
User
  -> Intake (IntakeAgent: classify, fact gaps)
  -> Retrieve (ReasoningRouter: rules + corpus + graph context)
  -> Reason (pipeline.assess / brain orchestrator, local Ollama when enabled)
  -> Govern (GovernanceEngine: PASS | FAIL | ESCALATE | HUMAN_REVIEW)
  -> Memory (MemoryStore: agent_memory, feedback_registry when consented)
  -> Learn (LearningLoop: ingestion_proposals only, never direct law writes)
  -> Response (governed assessment + metadata)
```

Entry points: `MotherController.process()` called from `POST /assess` and `POST /api/diagnosis`.

---

## Five design rules (enforced invariants)

1. **DB is truth**  
   Rules, legislation rows, and corpus chunks are written only by ingestion jobs and
   approved ops paths. LLM and learning loop enqueue `knowledge.ingestion_proposals` (082) only.

2. **Postgres graph, not Neo4j**  
   All graph traversal uses `legal_nodes` / `legal_edges` via `GraphController` and
   `backend/core/legal_graph.py`.

3. **No answer without governance**  
   Every user-facing response passes `GovernanceEngine` and `legal_truth_validator`
   before delivery. Verdicts: PASS, FAIL, ESCALATE, HUMAN_REVIEW.

4. **Fail-closed retrieval**  
   Empty or weak grounding yields `insufficient_grounding` or `not_supported`, never
   fabricated citations. CitationGuard / Critic gate unresolved cites.

5. **Trace everything**  
   `trace_id`, `control_plane_stages`, and `brain_traces` record intake through learn.
   Quarantined ingestion lands in `knowledge.quarantine_queue` (083), not production tables.

---

## Migrations

| Migration | Purpose |
|-----------|---------|
| 018 | `legal_nodes`, `legal_edges` |
| 076 | `agent_memory`, `brain_traces` extensions |
| 082 | `knowledge.ingestion_proposals`, `case_outcome_feedback` |
| 083 | `knowledge.quarantine_queue` |

---

## Deploy (local Docker)

```bash
docker compose up -d --build backend
curl -s -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the time limit for unfair dismissal?","facts":{},"use_model":false}'
```

Proof artifact: `reports/mother_control_plane_v1_cursor.txt`
