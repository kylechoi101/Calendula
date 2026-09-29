from calendula.coordinator import scoring


def s(name, kind, hospital, score):
    return {"name": name, "kind": kind, "hospital": hospital, "score": score, "note": ""}


REPLIES = {
    "hospital": {"scores": [s("A", "hospital", "A", 1.0), s("B", "hospital", "B", 0.0)]},
    "travel": {"scores": [s("A", "hospital", "A", 0.0), s("B", "hospital", "B", 1.0)]},
    "review": {"scores": [s("Dr. X", "doctor", "A", 0.5), s("Dr. Y", "doctor", "B", 0.5),
                          s("Dr. Z", "doctor", "C", 1.0)]},
}


def test_weights_decide_the_order():
    near = scoring.rank(["A", "B"], REPLIES, {"hospital": 1, "travel": 5, "review": 1})
    assert [d["name"] for d in near["doctors"]] == ["Dr. Y", "Dr. X"]
    best = scoring.rank(["A", "B"], REPLIES, {"hospital": 5, "travel": 1, "review": 1})
    assert [d["name"] for d in best["doctors"]] == ["Dr. X", "Dr. Y"]


def test_weighted_average():
    r = scoring.rank(["A", "B"], REPLIES, {"hospital": 1, "travel": 3, "review": 0})
    assert r["doctors"][0]["total"] == 0.75  # Dr. Y: (1*0 + 3*1) / 4


def test_uncovered_hospitals_are_dropped():
    r = scoring.rank(["A", "B"], REPLIES, {"hospital": 1, "travel": 1, "review": 1})
    assert "Dr. Z" not in [d["name"] for d in r["doctors"]]


def test_silent_agent_drops_out_of_the_average():
    r = scoring.rank(["A"], {"hospital": REPLIES["hospital"], "travel": None}, {"hospital": 1, "travel": 5})
    assert r["hospitals"][0]["total"] == 1.0


def test_malformed_entries_are_dropped():
    bad = {"hospital": {"scores": [{"name": "A", "hospital": "A", "score": 0.5},  # no kind
                                   {"name": "A", "kind": "hospital", "hospital": "A", "score": None},
                                   {"name": "A", "kind": "hospital", "hospital": ["A"], "score": 1},
                                   s("A", "hospital", "A", 0.7)]}}
    r = scoring.rank(["A"], bad, {"hospital": 1})
    assert r["hospitals"][0]["total"] == 0.7
