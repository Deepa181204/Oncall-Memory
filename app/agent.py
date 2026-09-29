"""IncidentAgent: recall -> reason -> (human resolves) -> retain."""
from __future__ import annotations

import json
import asyncio

from . import config
from .llm import get_llm
from .memory import get_memory

RULES_QUERY = "team rules, preferences and approval requirements for handling production incidents"


class IncidentAgent:
    def __init__(self, memory=None, llm=None):
        self.memory = memory or get_memory()
        self.llm = llm or get_llm()

    @staticmethod
    def build_query(inc: dict) -> str:
        return f"{inc['service']}: {inc['title']}. {inc['symptoms']} {inc['logs']}"

    def triage(self, inc: dict, use_memory: bool = True) -> dict:
        memories, rules = [], []
        if use_memory:
            memories = self.memory.recall(self.build_query(inc), limit=8)   # HINDSIGHT RECALL
            rules = self.memory.recall(RULES_QUERY, limit=4)                # HINDSIGHT RECALL (team rules)
        result = self.llm.triage(inc, memories, rules)
        result["used_memory"] = use_memory
        result["memories_used"] = memories
        result["rules_used"] = rules
        return result

    async def atriage(self, inc: dict, use_memory: bool = True) -> dict:
        memories, rules = [], []
        if use_memory:
            memories = await self.memory.arecall(self.build_query(inc), limit=8)
            rules = await self.memory.arecall(RULES_QUERY, limit=4)
        result = await asyncio.to_thread(self.llm.triage, inc, memories, rules)
        result["used_memory"] = use_memory
        result["memories_used"] = memories
        result["rules_used"] = rules
        return result

    def resolve(self, inc: dict, root_cause: str, resolution: str, minutes: int,
                note: str = "", agent_result: dict | None = None) -> str:
        """Called when the human closes the incident. This is the learning step."""
        text = (f"Incident {inc['id']} on {inc['service']} ({inc['severity']}) was resolved. "
                f"Title: {inc['title']}. Symptoms: {inc['symptoms']} Key log: {inc['logs']} "
                f"Root cause: {root_cause} Resolution: {resolution} "
                f"Time to resolve: {minutes} minutes. Engineer note: {note}")
        if agent_result:
            top = (agent_result.get("first_actions") or ["(none)"])[0]
            ok = self.score(agent_result, inc)
            text += (f" The on-call agent's first suggestion was '{top}', which was "
                     f"{'correct and useful' if ok else 'not the actual fix'} for this incident.")
        self.memory.retain(text, context=f"post-incident review for {inc['id']}",  # HINDSIGHT RETAIN
                           tags=[f"service:{inc['service']}", f"severity:{inc['severity']}", "type:incident"])
        return text

    async def aresolve(self, inc: dict, root_cause: str, resolution: str, minutes: int,
                       note: str = "", agent_result: dict | None = None,
                       agent_suggestion: str = "", suggestion_was_useful: bool | None = None) -> str:
        text = (f"Incident {inc['id']} on {inc['service']} ({inc['severity']}) was resolved. "
                f"Title: {inc['title']}. Symptoms: {inc['symptoms']} Key log: {inc['logs']} "
                f"Root cause: {root_cause} Resolution: {resolution} "
                f"Time to resolve: {minutes} minutes. Engineer note: {note}")
        if agent_result:
            top = (agent_result.get("first_actions") or ["(none)"])[0]
            ok = self.score(agent_result, inc)
            text += (f" The on-call agent's first suggestion was '{top}', which was "
                     f"{'correct and useful' if ok else 'not the actual fix'} for this incident.")
        elif agent_suggestion:
            if suggestion_was_useful is None:
                feedback = "not rated by the engineer"
            else:
                feedback = "useful" if suggestion_was_useful else "not useful"
            text += f" The agent's first suggestion was '{agent_suggestion}'; engineer feedback: {feedback}."
        await self.memory.aretain(text, context=f"post-incident review for {inc['id']}",
                                  tags=[f"service:{inc['service']}", f"severity:{inc['severity']}", "type:incident"])
        return text

    def seed_rules(self, rules: list[str]):
        for r in rules:
            self.memory.retain(r, context="standing team rule", tags=["type:rule"])

    async def aseed_rules(self, rules: list[str]):
        for rule in rules:
            await self.memory.aretain(rule, context="standing team rule", tags=["type:rule"])

    def insights(self, question: str = "What recurring failure patterns do we have, and what usually fixes them?") -> str:
        return self.memory.reflect(question)                                # HINDSIGHT REFLECT

    async def ainsights(self, question: str = "What recurring failure patterns do we have, and what usually fixes them?") -> str:
        return await self.memory.areflect(question)

    @staticmethod
    def score(result: dict, inc: dict) -> bool:
        """Did the agent's top hypothesis/action point at the real fix? (keyword check)"""
        blob = ((result.get("first_actions") or [""])[0] + " " +
                ((result.get("hypotheses") or [{}])[0].get("cause", ""))).lower()
        return any(k in blob for k in inc["fix_keywords"])


def load_data() -> dict:
    return json.loads((config.DATA_DIR / "incidents.json").read_text())
