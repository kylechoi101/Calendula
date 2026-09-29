import csv
import json

import pytest

from calendula import protocol, workers
from calendula.workers import DATA_DIR, hospital


def h(mortality=8.0, wait=10, cases=500, ppd=50.0):
    return {"Mortality Rate (%)": mortality, "Wait Time (Days)": wait, "Annual Cases": cases,
            "Patients per Doctor": ppd}


DATA = {"hospitals": {
    "Best": h(mortality=6.0, wait=5, cases=1000, ppd=40.0),
    "Worst": h(mortality=12.0, wait=30, cases=200, ppd=70.0),
    "Mid": h(mortality=9.0, wait=17.5, cases=600, ppd=55.0),
}}
TRADEOFF = {"hospitals": {"Good but slow": h(mortality=6.0, wait=30), "Fast but worse": h(mortality=12.0, wait=5)}}


def rank(names, data=DATA, weights=None):
    req = {"hospitals": names, "case": protocol.CASE} | ({"weights": weights} if weights is not None else {})
    return hospital.handle(req, data)["scores"]


def by_name(out):
    return {s["name"]: s["score"] for s in out}


def test_v2_score_entries_in_request_order():
    out = rank(["Worst", "Mid", "Best"])
    assert [(s["name"], s["score"]) for s in out] == [("Worst", 0.0), ("Mid", 0.5), ("Best", 1.0)]
    assert out[2] == {"name": "Best", "kind": "hospital", "hospital": "Best", "score": 1.0,
                      "note": "6% mortality, 1000 cases/yr, 5-day wait"}


def test_only_requested_hospitals_are_scored_against_each_other():
    # Without Best in the list, Mid is now the best of the two.
    assert by_name(rank(["Worst", "Mid"])) == {"Mid": 1.0, "Worst": 0.0}


def test_default_weights_put_quality_over_wait():
    assert by_name(rank(["Fast but worse", "Good but slow"], TRADEOFF)) == {
        "Good but slow": round(0.4 + 0.2 * 0.5 + 0.1 * 0.5, 3), "Fast but worse": round(0.3 + 0.2 * 0.5 + 0.1 * 0.5, 3)}


def test_orchestrator_weights_decide_the_tradeoff():
    both = ["Good but slow", "Fast but worse"]
    quality_first = by_name(rank(both, TRADEOFF, {"Mortality Rate (%)": 5, "Wait Time (Days)": 1}))
    urgent = by_name(rank(both, TRADEOFF, {"Mortality Rate (%)": 1, "Wait Time (Days)": 5}))
    assert quality_first == {"Good but slow": round(5 / 6, 3), "Fast but worse": round(1 / 6, 3)}
    assert urgent == {"Good but slow": round(1 / 6, 3), "Fast but worse": round(5 / 6, 3)}


def test_weights_are_rescaled_and_missing_metrics_count_zero():
    only_mortality = rank(["Worst", "Mid", "Best"], weights={"Mortality Rate (%)": 1})
    assert only_mortality == rank(["Worst", "Mid", "Best"], weights={"Mortality Rate (%)": 7})
    assert by_name(only_mortality) == {"Best": 1.0, "Mid": 0.5, "Worst": 0.0}


def test_no_weights_uses_defaults():
    assert rank(["Worst", "Mid", "Best"], weights={}) == rank(["Worst", "Mid", "Best"]) == \
        rank(["Worst", "Mid", "Best"], weights=hospital.DEFAULT_WEIGHTS)


@pytest.mark.parametrize("bad", [{"Hospital Ranking": 1}, {"Annual Cases": -1}, {"Annual Cases": 0}])
def test_bad_weights_raise(bad):
    with pytest.raises(ValueError):
        rank(["Mid"], weights=bad)


def test_bad_weights_become_an_error_reply():
    env = protocol.envelope("hospitals", {"hospitals": ["Mid"], "case": protocol.CASE, "weights": {"x": 1}}, "t1")
    reply = json.loads(workers.answer("hospital", json.dumps(env)))
    assert reply["type"] == "error" and "unknown weights" in reply["data"]["message"]


def test_single_hospital_scores_half():
    assert [s["score"] for s in rank(["Mid"])] == [0.5]


def test_unknown_and_duplicate_names():
    assert [s["name"] for s in rank(["Nope", "Mid", "Best", "Mid"])] == ["Mid", "Best"]
    assert rank(["Nope"]) == [] and rank([]) == []


def test_real_csv():
    with open(DATA_DIR / hospital.HOSPITALS, newline="") as f:
        rows = list(csv.DictReader(f))
    names = [r["Hospital Name"] for r in rows]
    data = hospital.load(DATA_DIR)
    assert len(names) == 30 and list(data["hospitals"]) == names
    out = rank(names, data)
    assert [s["name"] for s in out] == names
    assert all(0 <= s["score"] <= 1 for s in out)
    pacific = next(s for s in out if s["name"] == "Pacific Crest Medical Center")
    assert pacific["note"] == "6.9% mortality, 1080 cases/yr, 25-day wait"
