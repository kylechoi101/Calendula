"""Whole match run in-process through the fake grid."""

from calendula import coordinator
from fake_grid import FakeAgent


def test_full_match():
    agent = FakeAgent("I have atrial fibrillation, PLAN-B, zip 94301")
    coordinator.run(agent)
    assert "Dr. Maya Chen" in agent.text, agent.text


def test_minimum_necessary():
    agent = FakeAgent("afib")
    coordinator.run(agent)
    sent = {role: env["data"] for role, env in agent.sent if env["type"] != "whoami"}
    assert "plan_id" not in sent["doctor"] and "lat" not in sent["doctor"]
    assert "condition" not in sent["insurance"] and "lat" not in sent["insurance"]
    assert "condition" not in sent["travel"] and "plan_id" not in sent["travel"]
    assert set(sent["review"]) == {"npis"}


def test_missing_worker_is_flagged():
    agent = FakeAgent("afib", roles=("doctor", "review", "hospital", "insurance"))
    coordinator.run(agent)
    assert "travel agent offline" in agent.text
    assert "Missing sources: travel" in agent.text


def test_no_doctor_agent():
    agent = FakeAgent("afib", roles=("review", "hospital"))
    coordinator.run(agent)
    assert "Doctor directory unavailable" in agent.text
