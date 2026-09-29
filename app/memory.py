"""Memory layer.

HindsightMemory  -> the real thing: retain / recall / reflect against Hindsight.
LocalMemory      -> explicit offline mode (keyword overlap) so tests and demos run anywhere.
                    It is NOT a substitute for Hindsight's multi-strategy recall.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from . import config
from .errors import ProviderUnavailable

MISSION = (
    "I am the on-call memory for a platform engineering team. I remember every incident: "
    "symptoms, root causes, fixes that worked or failed, time to resolve, and the team's "
    "rules for handling production changes."
)
logger = logging.getLogger(__name__)


class HindsightMemory:
    name = "hindsight"

    def __init__(self, base_url: str, api_key: str, bank_id: str):
        from hindsight_client import Hindsight  # pip install hindsight-client

        kwargs = {"base_url": base_url, "timeout": 30, "max_attempts": 2}
        if api_key:
            kwargs["api_key"] = api_key
        self.client = Hindsight(**kwargs)
        self.bank_id = bank_id

    async def ainitialize(self):
        """Initialize and check the bank on the application's persistent event loop."""
        try:
            try:
                await self.client.acreate_bank(bank_id=self.bank_id, name="On-call memory", mission=MISSION)
            except Exception as exc:
                status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
                if status != 409 and "already exists" not in str(exc).lower():
                    raise
            # Authentication and connectivity are checked before accepting traffic.
            await self.client.arecall(bank_id=self.bank_id, query="on-call incident memory readiness check")
        except Exception:
            await self.client.aclose()
            raise

    async def aretain(self, content: str, context: str | None = None, tags: list[str] | None = None):
        try:
            return await self.client.aretain(bank_id=self.bank_id, content=content, context=context, tags=tags)
        except Exception as exc:
            logger.warning("Hindsight retain failed: %s", type(exc).__name__)
            raise ProviderUnavailable("Hindsight retain request failed.") from exc

    async def arecall(self, query: str, limit: int = 8) -> list[str]:
        try:
            res = await self.client.arecall(bank_id=self.bank_id, query=query)
        except Exception as exc:
            logger.warning("Hindsight recall failed: %s", type(exc).__name__)
            raise ProviderUnavailable("Hindsight recall request failed.") from exc
        items = getattr(res, "results", res) or []
        return [getattr(r, "text", str(r)) for r in items][:limit]

    async def areflect(self, query: str) -> str:
        try:
            result = await self.client.areflect(bank_id=self.bank_id, query=query)
        except Exception as exc:
            logger.warning("Hindsight reflect failed: %s", type(exc).__name__)
            raise ProviderUnavailable("Hindsight reflect request failed.") from exc
        return getattr(result, "text", "") or ""


_STOP = set("the a an and or of to in on at for with is was are were be by from this that it as after before during into".split())


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 2}


class LocalMemory:
    name = "local"

    def __init__(self, bank_id: str, path: Path | None = None):
        self.bank_id = bank_id
        self.path = path or (config.DATA_DIR / ".local_memory.json")
        self.items: list[str] = []
        if self.path.exists():
            try:
                self.items = json.loads(self.path.read_text()).get(bank_id, [])
            except Exception:
                self.items = []

    async def ainitialize(self):
        return None

    def _save(self):
        try:
            db = json.loads(self.path.read_text()) if self.path.exists() else {}
            db[self.bank_id] = self.items
            self.path.write_text(json.dumps(db))
        except Exception:
            pass

    def retain(self, content: str, context: str | None = None, tags: list[str] | None = None):
        self.items.append(content)
        self._save()

    def recall(self, query: str, limit: int = 8) -> list[str]:
        q = _tokens(query)
        scored = [(len(q & _tokens(m)) / (len(q) ** 0.5 or 1), m) for m in self.items]
        return [m for s, m in sorted(scored, key=lambda x: -x[0]) if s >= 1.5][:limit]

    def reflect(self, query: str) -> str:
        hits = self.recall(query, 5)
        return "Local fallback (no synthesis). Top memories:\n- " + "\n- ".join(hits) if hits else "No memories yet."

    async def aretain(self, content: str, context: str | None = None, tags: list[str] | None = None):
        self.retain(content, context, tags)

    async def arecall(self, query: str, limit: int = 8) -> list[str]:
        return self.recall(query, limit)

    async def areflect(self, query: str) -> str:
        return self.reflect(query)


def get_memory(bank_id: str | None = None):
    config.validate_settings()
    bank_id = bank_id or config.HINDSIGHT_BANK_ID
    mode = config.MEMORY_BACKEND
    if mode == "local":
        return LocalMemory(bank_id)
    return HindsightMemory(config.HINDSIGHT_BASE_URL, config.HINDSIGHT_API_KEY, bank_id)
