# Architecture

```
 Engineer / UI ──► FastAPI (app/server.py)
                        │
                 IncidentAgent (app/agent.py)
        ┌───────────────┼────────────────┐
   recall(query)    LLM (Groq)       retain(post-incident)
        │          reasons over          │
        ▼          memories+rules        ▼
              ┌─────────────────────┐
              │  Hindsight memory   │   reflect() → recurring patterns
              │  bank: oncall-memory│
              └─────────────────────┘
```
**Loop:** recall → reason → human resolves → retain. Each cycle makes the next recall richer.

**Design decisions**
- One bank per team; tags (`service:`, `severity:`, `type:`) leave room for filtered recall.
- Two recalls per triage: incident similarity, and team rules. Rules are retained as memories, not hardcoded in the prompt, so they can change without a deploy.
- The agent's own first suggestion and whether it was right is retained, so memory also records what *didn't* work.
- Memory is injected as text for the LLM to cite; the prompt forbids citing IDs not present in memories.
- `LocalMemory` exists only so tests and offline demos run; production path is `HindsightMemory`.
- The FastAPI path uses Hindsight's async client on the server event loop and closes provider clients on shutdown.
- Production API routes require a constant-time-checked bearer token, explicit allowed hosts, request-field limits, and responses with security headers; demo endpoints and OpenAPI docs are disabled.

**Runtime behavior:** Production requires Groq and Hindsight. Hindsight connectivity and credentials are checked during startup; provider errors return a generic 503 and are never replaced by a mock answer. Groq output is requested in JSON mode, shape-checked, and retried once if malformed. Local keyword memory and the mock LLM are explicit offline-demo settings only. Live payloads use `POST /api/triage` and `POST /api/resolve-live`. The shared API key protects the service endpoint; use authenticated HTTPS ingress for individual user identity, rate limiting, and audit policy.
