# On-Call Memory Agent

An incident-response agent that **remembers every incident your team has ever fought**, and gets faster at recognising repeats. Built on [Hindsight](https://github.com/vectorize-io/hindsight) agent memory.

> The third time `connection pool exhausted` shows up after a deploy, the agent should already know the fix. Stateless agents can't do that. This one does.

## The problem
On-call engineers re-diagnose the same failures: pool exhaustion, Kafka rebalance storms, expired mTLS certs. The knowledge exists in old postmortems and in people's heads, not where the 3am responder needs it.

## What the agent does
1. **Triage**: given a live incident, it **recalls** similar past incidents and team rules from Hindsight, then produces ranked hypotheses, first actions, and items that need approval, citing the past incidents it relied on.
2. **Learn**: when the engineer closes the incident, the agent **retains** a post-incident record (symptoms, root cause, fix, time to resolve, and whether its own suggestion was right).
3. **Reflect**: on demand, it uses Hindsight **reflect** to synthesise recurring patterns across all incidents.

## How Hindsight is used (memory is the product)
| Op | Where | Why |
|---|---|---|
| `retain` | `IncidentAgent.resolve`, `seed_rules` (`app/agent.py`) | Stores post-incident reviews and standing team rules, tagged by service and severity |
| `recall` | `IncidentAgent.triage` | Pulls similar incidents (symptom/log similarity) and team rules before the LLM reasons |
| `reflect` | `IncidentAgent.insights` | Cross-incident pattern synthesis |

The "no memory" baseline and the "with memory" run use the **same LLM and prompt**; the only difference is what Hindsight returns.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set both GROQ_API_KEY and HINDSIGHT_API_KEY

# Run with Groq and Hindsight Cloud, or point HINDSIGHT_BASE_URL at your Hindsight server
make serve                       # UI at http://localhost:8000
```

The default runtime requires both Groq and Hindsight and fails closed when either is missing or unavailable. Hindsight Cloud uses `https://api.hindsight.vectorize.io`; its Python client creates the configured bank on startup and verifies access before serving. The agent calls Hindsight recall before each triage, retain after each resolution, and reflect for pattern summaries. These operations use the official Hindsight Python client ([setup](https://docs.hindsight.vectorize.io/getting-started/), [recall](https://docs.hindsight.vectorize.io/recall/), [retain](https://docs.hindsight.vectorize.io/retain/), [reflect](https://docs.hindsight.vectorize.io/reflect/)). Groq uses its OpenAI-compatible chat completion endpoint with JSON mode ([Groq compatibility docs](https://console.groq.com/docs/openai), [structured output docs](https://console.groq.com/docs/structured-outputs)).

### Production deployment

Set `APP_ENV=production`, `MEMORY_BACKEND=hindsight`, `LLM_BACKEND=groq`, `GROQ_API_KEY`, `HINDSIGHT_API_KEY`, a random `APP_API_KEY` with at least 32 characters, and a strict `ALLOWED_HOSTS` list through the deployment secret manager. Generate the app key with `python -c "import secrets; print(secrets.token_urlsafe(48))"`; do not commit `.env` or put provider keys in browser code. Every `/api/*` endpoint requires the app bearer key; the browser UI prompts for it and holds it in tab memory. Keep the service behind authenticated HTTPS ingress or an identity-aware proxy as well: the shared app key does not provide individual identities or role-based access control. Production disables demo incidents, seeding, sample answer, score, and OpenAPI documentation routes. Configure ingress rate limits, backups, retention, monitoring, and bank permissions for your organization.

`POST /api/triage` accepts an incident as JSON and always recalls Hindsight memories before Groq reasons over it. Include `Authorization: Bearer $APP_API_KEY` on API requests:

```json
{
  "incident_id": "OPS-2048",
  "service": "checkout-api",
  "severity": "SEV-2",
  "title": "Database connection pool exhausted",
  "symptoms": "Requests are timing out after the latest deploy.",
  "logs": "optional sanitized log excerpt"
}
```

```bash
curl -H "Authorization: Bearer $APP_API_KEY" -H "Content-Type: application/json" \
  -d '{"incident_id":"OPS-2048","service":"checkout-api","severity":"SEV-2","title":"Database connection pool exhausted","symptoms":"Requests time out after deploy","logs":"sanitized excerpt"}' \
  https://your-host/api/triage
```

After an engineer resolves it, `POST /api/resolve-live` accepts the same incident fields plus `root_cause`, `resolution`, optional `minutes` and `note`, and optional suggestion feedback. That call retains the post-incident review in the configured Hindsight bank. Add approved team policies with `POST /api/rules` and `{"rule":"Require a second engineer to approve production database failovers."}`. Treat submitted incident text and logs as sensitive operational data and apply your organization's retention policy.

Build and run the included container with your platform's secret injection:

```bash
docker build -t oncall-memory-agent .
docker run --rm -p 8000:8000 --env-file .env.production oncall-memory-agent
```

Create `.env.production` with `APP_ENV=production`, the provider settings above, and `ALLOWED_HOSTS` set to the externally visible hostname for a local container trial. The service exposes `GET /healthz` for liveness and `/readyz` for readiness after Hindsight startup checks. In an actual deployment, inject provider keys from the platform's secret manager rather than using `--env-file`.

### Offline demo

No provider keys? `make demo-offline` selects the deterministic mock LLM and local keyword-memory fallback explicitly. This mode is only a demo stand-in; it does not exercise Groq or Hindsight.

`make demo` runs the learning-curve replay against the configured real providers. `make test` runs the offline unit tests.

## The learning curve
Replaying 8 synthetic incidents in order (offline mock mode, see `docs/results.json`):

| # | Incident | No memory | With memory | Cited |
|---|---|---|---|---|
| 1 | INC-101 checkout-api (pool) | miss | miss | (first ever) |
| 2 | INC-102 order-events (Kafka) | miss | miss | |
| 3 | INC-103 auth-gateway (TLS) | miss | miss | |
| 4 | INC-104 payments-api (pool) | miss | **HIT** | INC-101 |
| 5 | INC-105 session-cache (Redis) | miss | miss | (novel) |
| 6 | INC-106 invoice-consumer (Kafka) | miss | **HIT** | INC-102 |
| 7 | INC-107 billing-worker (TLS) | miss | **HIT** | INC-103 |
| 8 | INC-108 search-api (pool) | miss | **HIT** | INC-101 |

Novel incidents don't improve (honest); repeats do. Re-run with your real LLM + Hindsight for real numbers, and put those in your article and video.

## Layout
```
app/        agent.py (loop) · memory.py (Hindsight + offline local) · llm.py (Groq/mock) · server.py + static/index.html
data/       incidents.json: synthetic but realistic incidents, logs, team rules
scripts/    seed.py · demo.py (learning-curve replay)
tests/      offline unit tests
docs/       ARCHITECTURE.md · DEMO_SCRIPT.md
content/    article / LinkedIn / video prompts + submission checklist
```

## Notes
- `fix_keywords` in `incidents.json` is only for scoring the demo; the agent never sees it.
- Groq responses are requested in JSON mode, validated before use, and retried once only when the response shape is invalid. Provider failures are surfaced; they never become mock answers.
- Hindsight connection and authorization failures stop application startup. Local keyword memory is available only when explicitly selected for offline demos.
- The live triage endpoint expects JSON with `incident_id`, `service`, `severity`, `title`, `symptoms`, and optional `logs`. The matching resolution endpoint accepts those incident fields plus `root_cause`, `resolution`, optional `minutes`, and `note`.
