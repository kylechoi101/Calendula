"""Whole conversations run in-process through the fake grid. No model: intake uses its keyword fallback,
explain its template. Insurance, hospital and travel are protocol-v2 stand-ins (stub_workers.py)."""

import pytest

from calendula import coordinator, workers
from fake_grid import FakeAgent
from stub_workers import STUBS

FULL = ("My 8-year-old daughter Emily was just diagnosed with medulloblastoma. We live in 95816 and have "
        "SierraCare Health Plan. Being close to home matters most, and the surgeon's experience.")
ROLES = ("insurance", "review", "hospital", "travel")


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    for role, mod in STUBS.items():
        monkeypatch.setitem(workers.WORKERS, role, mod)
    monkeypatch.setattr(workers, "_data", {})


def run(prompt, roles=ROLES, history=()):
    agent = FakeAgent(prompt, roles=roles, history=history)
    coordinator.run(agent)
    return agent


def calls(agent):
    return [(role, env) for role, env in agent.sent if env["type"] != "whoami"]


def test_incomplete_case_asks_follow_up_and_calls_no_agent():
    agent = run("My son has a brain tumor, medulloblastoma. I'm scared.")
    assert "ZIP" in agent.text and "insurance" in agent.text
    assert agent.sent == []


def test_follow_up_turn_completes_the_case():
    history = [{"role": "user", "text": "My daughter has medulloblastoma."},
               {"role": "assistant", "text": "I'm so sorry. Could you tell me your ZIP code and insurance?"}]
    agent = run("95816, SierraCare Health Plan. Being close to home matters most.", history=history)
    assert "Looking for the best personalized medical service for you." in agent.text
    assert "Top doctors" in agent.text


def test_full_match_flow():
    agent = run(FULL)
    text = agent.text
    assert text.index("Here's what I understand") < text.index("Looking for the best personalized")
    assert "Top doctors" in text and "Top hospitals" in text
    sent = calls(agent)
    assert sent[0] == ("insurance", sent[0][1]) and sent[0][1]["data"] == {"insurer": "SierraCare Health Plan"}
    covered = set(STUBS["insurance"].load(workers.DATA_DIR)["SierraCare Health Plan"])
    for role, env in sent[1:]:
        assert set(env["data"]) == {"hospitals", "case"}
        assert set(env["data"]["hospitals"]) == covered
        assert "Emily" not in str(env["data"]["case"])  # the child's name stays with the coordinator


def test_unknown_insurer_asks_to_check_plan_name():
    agent = run("My son has medulloblastoma, ZIP 95816, Acme Health Plan. Distance matters most.")
    assert "couldn't find **Acme Health Plan**" in agent.text
    assert [r for r, _ in calls(agent)] == ["insurance"]


def test_missing_agent_is_flagged():
    agent = run(FULL, roles=("insurance", "review", "hospital"))
    assert "travel agent offline" in agent.text
    assert "Not included (agent unavailable): distance" in agent.text


def test_no_insurance_agent_stops():
    agent = run(FULL, roles=("review", "hospital", "travel"))
    assert "can't reach the insurance records" in agent.text


def test_minimum_necessary():
    sent = {role: env["data"] for role, env in calls(run(FULL))}
    assert sent["insurance"] == {"insurer": "SierraCare Health Plan"}
    assert sent["review"]["case"] == {}
    assert sent["travel"]["case"] == {"zip": "95816"}
    assert "zip" not in sent["hospital"]["case"]


def test_finished_search_is_not_rerun():
    first = run(FULL)
    agent = run("Thank you so much.", history=[{"role": "user", "text": FULL},
                                               {"role": "assistant", "text": first.text}])
    assert "still my best match" in agent.text and agent.sent == []


def test_corrected_insurer_is_used():
    history = [{"role": "user", "text": "My son has medulloblastoma, ZIP 95816, Acme Health Plan. Distance matters most."},
               {"role": "assistant", "text": "I couldn't find **Acme Health Plan**. Could you check the plan name?"}]
    agent = run("Sorry, it's SierraCare Health Plan.", history=history)
    assert calls(agent)[0][1]["data"] == {"insurer": "SierraCare Health Plan"}
    assert "Top doctors" in agent.text


def test_story_words_do_not_count_as_priorities():
    agent = run("She was treated at the hospital near home, we're in 95816 and Our Insurance is SierraCare Health Plan. "
                "Diagnosis: medulloblastoma.")
    assert agent.sent == [] and "what matters most" in agent.text
