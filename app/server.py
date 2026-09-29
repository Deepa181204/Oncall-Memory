"""FastAPI server:  uvicorn app.server:app --reload --port 8000"""
from contextlib import asynccontextmanager
import hmac
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import config
from .agent import IncidentAgent, load_data
from .errors import ProviderUnavailable

logger = logging.getLogger(__name__)
_ready = False


@asynccontextmanager
async def lifespan(_app):
    global _ready
    await agent.memory.ainitialize()
    _ready = True
    yield
    _ready = False
    memory_client = getattr(agent.memory, "client", None)
    if memory_client is not None and hasattr(memory_client, "aclose"):
        await memory_client.aclose()
    llm_client = getattr(agent.llm, "client", None)
    if llm_client is not None and hasattr(llm_client, "close"):
        llm_client.close()


production = config.APP_ENV == "production"
app = FastAPI(title="On-Call Memory Agent", lifespan=lifespan,
              docs_url=None if production else "/docs",
              redoc_url=None if production else "/redoc",
              openapi_url=None if production else "/openapi.json")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)
agent = IncidentAgent()
DATA = load_data()
INCIDENTS = {i["id"]: i for i in DATA["incidents"]}
_last: dict[str, dict] = {}  # last memory-enabled triage per incident, used when teaching
STATIC = Path(__file__).parent / "static"


@app.middleware("http")
async def secure_responses_and_authenticate(request, call_next):
    if request.url.path.startswith("/api/"):
        raw_length = request.headers.get("content-length", "0")
        try:
            body_length = int(raw_length)
        except ValueError:
            return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
        if body_length > 65536:
            return JSONResponse({"detail": "Request body exceeds 64 KiB"}, status_code=413)
    if request.url.path.startswith("/api/") and config.APP_API_KEY:
        authorization = request.headers.get("authorization", "")
        token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(token.encode("utf-8"), config.APP_API_KEY.encode("utf-8")):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401,
                                headers={"WWW-Authenticate": "Bearer"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ProviderUnavailable)
async def provider_error_handler(_request, exc: ProviderUnavailable):
    logger.error("Upstream provider request failed: %s", exc.__class__.__name__)
    return JSONResponse({"detail": "An upstream provider is temporarily unavailable."},
                        status_code=503, headers={"Retry-After": "5"})


class Resolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(min_length=1, max_length=100)
    root_cause: str = Field(min_length=1, max_length=4000)
    resolution: str = Field(min_length=1, max_length=4000)
    minutes: int = Field(default=30, ge=0, le=525600)
    note: str = Field(default="", max_length=4000)


class IncidentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(min_length=1, max_length=100)
    service: str = Field(min_length=1, max_length=200)
    severity: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    symptoms: str = Field(min_length=1, max_length=8000)
    logs: str = Field(default="", max_length=12000)


class ResolveInput(Resolve):
    service: str = Field(min_length=1, max_length=200)
    severity: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    symptoms: str = Field(min_length=1, max_length=8000)
    logs: str = Field(default="", max_length=12000)
    agent_suggestion: str = Field(default="", max_length=1000)
    suggestion_was_useful: bool | None = None


class Adhoc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=4000)


class TeamRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule: str = Field(min_length=1, max_length=4000)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    if not _ready:
        raise HTTPException(503, "provider initialization is not complete")
    return {"status": "ready"}


@app.get("/api/status")
def status():
    return {"memory": agent.memory.name, "bank": agent.memory.bank_id, "llm": agent.llm.name,
            "demo_mode": config.APP_ENV != "production"}


@app.get("/api/incidents")
def incidents():
    if config.APP_ENV == "production":
        raise HTTPException(404, "not found")
    return [{k: v for k, v in i.items() if k in ("id", "service", "severity", "title", "symptoms", "logs")}
            for i in DATA["incidents"]]


@app.post("/api/seed")
async def seed():
    if config.APP_ENV == "production":
        raise HTTPException(404, "not found")
    await agent.aseed_rules(DATA["team_rules"])
    return {"seeded": len(DATA["team_rules"])}


@app.post("/api/rules")
async def add_team_rule(body: TeamRule):
    """Retain an operator-approved standing rule in Hindsight."""
    await agent.memory.aretain(body.rule, context="operator-approved team rule", tags=["type:rule"])
    return {"retained": True}


@app.post("/api/triage/{incident_id}")
async def triage(incident_id: str, use_memory: bool = True):
    if config.APP_ENV == "production":
        raise HTTPException(404, "not found")
    inc = INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(404, "unknown incident")
    res = await agent.atriage(inc, use_memory=use_memory)
    if use_memory:
        _last[incident_id] = res
    if config.APP_ENV != "production":
        res["correct"] = agent.score(res, inc)  # demo-only grading against known truth
    return res


@app.post("/api/triage")
async def triage_live(body: IncidentInput):
    """Triage an incident supplied by an operator or an upstream alert pipeline."""
    return await agent.atriage(body.model_dump(), use_memory=True)


@app.post("/api/resolve")
async def resolve(body: Resolve):
    if config.APP_ENV == "production":
        raise HTTPException(404, "not found")
    inc = INCIDENTS.get(body.incident_id)
    if not inc:
        raise HTTPException(404, "unknown incident")
    text = await agent.aresolve(inc, body.root_cause, body.resolution, body.minutes, body.note, _last.get(body.incident_id))
    return {"retained": text}


@app.post("/api/resolve-live")
async def resolve_live(body: ResolveInput):
    """Retain a resolved live incident in Hindsight as a post-incident review."""
    inc = body.model_dump(include={"incident_id", "service", "severity", "title", "symptoms", "logs"})
    inc["id"] = inc.pop("incident_id")
    text = await agent.aresolve(inc, body.root_cause, body.resolution, body.minutes, body.note,
                                agent_suggestion=body.agent_suggestion,
                                suggestion_was_useful=body.suggestion_was_useful)
    return {"retained": text}


@app.get("/api/truth/{incident_id}")
def truth(incident_id: str):
    """Demo helper: pre-fills the 'engineer closes incident' form."""
    if config.APP_ENV == "production":
        raise HTTPException(404, "not found")
    i = INCIDENTS.get(incident_id)
    if not i:
        raise HTTPException(404, "unknown incident")
    return {k: i[k] for k in ("root_cause", "resolution", "minutes", "note")}


@app.post("/api/recall")
async def recall(body: Adhoc):
    return {"memories": await agent.memory.arecall(body.query, 10)}


@app.get("/api/insights")
async def insights():
    return {"insights": await agent.ainsights()}
