"""Seed standing team rules into the configured memory bank."""
import asyncio

from app import config
from app.agent import IncidentAgent, load_data

async def main():
    if config.APP_ENV == "production":
        raise SystemExit("Refusing to seed synthetic demo rules in production; use POST /api/rules for approved team policies.")
    a = IncidentAgent()
    await a.memory.ainitialize()
    await a.aseed_rules(load_data()["team_rules"])
    print(f"Seeded team rules into {a.memory.name} bank '{a.memory.bank_id}'.")
    client = getattr(a.memory, "client", None)
    if client is not None:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
