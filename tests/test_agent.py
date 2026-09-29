import tempfile
import unittest
from pathlib import Path

from app.agent import IncidentAgent, load_data
from app.llm import MockLLM
from app.memory import LocalMemory


def make_agent():
    tmp = Path(tempfile.mkdtemp()) / "mem.json"
    return IncidentAgent(memory=LocalMemory("test", path=tmp), llm=MockLLM())


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.data = load_data()
        self.incs = {i["id"]: i for i in self.data["incidents"]}

    def test_local_memory_roundtrip(self):
        m = LocalMemory("t", path=Path(tempfile.mkdtemp()) / "m.json")
        m.retain("Kafka consumer rebalance storm fixed by raising max.poll.interval.ms")
        self.assertTrue(m.recall("kafka consumer rebalance storm lag"))
        self.assertFalse(m.recall("completely unrelated tls certificate"))

    def test_no_memory_is_generic(self):
        a = make_agent()
        r = a.triage(self.incs["INC-104"], use_memory=False)
        self.assertEqual(r["cited_incidents"], [])
        self.assertFalse(a.score(r, self.incs["INC-104"]))

    def test_memory_improves_repeat_incident(self):
        a = make_agent()
        a.resolve(self.incs["INC-101"], **{k: self.incs["INC-101"][k] for k in ("root_cause", "resolution")},
                  minutes=47, note="n")
        r = a.triage(self.incs["INC-104"], use_memory=True)
        self.assertIn("INC-101", r["cited_incidents"])
        self.assertTrue(a.score(r, self.incs["INC-104"]))

    def test_learning_curve_beats_baseline(self):
        a = make_agent()
        base = mem = 0
        for inc in self.data["incidents"]:
            base += a.score(a.triage(inc, use_memory=False), inc)
            res = a.triage(inc, use_memory=True)
            mem += a.score(res, inc)
            a.resolve(inc, inc["root_cause"], inc["resolution"], inc["minutes"], inc["note"], agent_result=res)
        self.assertGreater(mem, base)


if __name__ == "__main__":
    unittest.main()
