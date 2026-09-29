"""Learning-curve demo: replay 8 incidents in order.
For each: triage WITHOUT memory (baseline) and WITH memory, score both, then teach the agent the outcome.
Run:  python -m scripts.demo --fresh
"""
import argparse
import asyncio
import json
import time

from app import config
from app.agent import IncidentAgent, load_data
from app.memory import get_memory


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="use a brand-new memory bank for a clean run")
    args = ap.parse_args()
    bank = f"{config.HINDSIGHT_BANK_ID}-{int(time.time())}" if args.fresh else config.HINDSIGHT_BANK_ID
    data = load_data()
    agent = IncidentAgent(memory=get_memory(bank))
    await agent.memory.ainitialize()
    await agent.aseed_rules(data["team_rules"])
    print(f"memory={agent.memory.name} bank={bank} llm={agent.llm.name}\n")
    print(f"{'#':<3}{'incident':<9}{'service':<24}{'no-memory':<11}{'with-memory':<12}cited")
    rows, base_hits, mem_hits = [], 0, 0
    for i, inc in enumerate(data["incidents"], 1):
        base = await agent.atriage(inc, use_memory=False)
        withm = await agent.atriage(inc, use_memory=True)
        b, m = agent.score(base, inc), agent.score(withm, inc)
        base_hits += b
        mem_hits += m
        print(f"{i:<3}{inc['id']:<9}{inc['service']:<24}{'HIT' if b else 'miss':<11}{'HIT' if m else 'miss':<12}{','.join(withm.get('cited_incidents', [])) or '-'}")
        rows.append({"n": i, "id": inc["id"], "baseline_hit": b, "memory_hit": m,
                     "cited": withm.get("cited_incidents", []), "minutes_when_resolved": inc["minutes"]})
        await agent.aresolve(inc, inc["root_cause"], inc["resolution"], inc["minutes"], inc["note"], agent_result=withm)
    n = len(data["incidents"])
    print(f"\nfirst-suggestion accuracy: no-memory {base_hits}/{n} | with-memory {mem_hits}/{n}")
    (config.ROOT / "docs" / "results.json").write_text(json.dumps(
        {"memory": agent.memory.name, "llm": agent.llm.name, "baseline": base_hits, "with_memory": mem_hits, "rows": rows}, indent=2))
    client = getattr(agent.memory, "client", None)
    if client is not None:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
