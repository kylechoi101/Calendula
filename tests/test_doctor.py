from pathlib import Path

import pytest

from calendula.workers import doctor

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PCMC, GG = "Pacific Crest Medical Center", "Golden Gate Specialty Hospital"


def d(doc_id, mb="No", hgg="No", ep="No", research=5.0, years=10, hospital=PCMC):
    row = {"Doctor ID": doc_id, "Doctor Name": f"Dr {doc_id}", "Hospital Affiliated": "Yes",
           "Hospital Name": hospital, "Hospital Ranking": "1",
           "Medulloblastoma Experience": mb, "Pediatric High-Grade Glioma Experience": hgg,
           "Ependymoma Experience": ep, "Research Score": research, "Surgical Expertise (Years)": years}
    row["Tumor Types Treated"] = [mb, hgg, ep].count("Yes")  # as load() computes it
    return row


DATA = [
    d("A", mb="Yes", research=7.0, years=5),
    d("B", mb="Yes", research=9.0, years=20),
    d("C", mb="Yes", research=7.0, years=25),
    d("D", hgg="Yes", ep="Yes", research=10.0),
    d("E", mb="Yes", research=10.0, years=30, hospital=GG),
]


def req(condition="medulloblastoma", hospitals=(PCMC,), weights=None, summary=""):
    r = {"hospitals": list(hospitals), "case": {"condition": condition, "age": 8, "summary": summary}}
    return r | ({"weights": weights} if weights is not None else {})


def names(r, data=DATA):
    return [s["name"] for s in doctor.handle(r, data)["scores"]]


@pytest.fixture
def agent_picks(monkeypatch):
    """Stand in for the model: run_agent 'calls the tool' by recording a tumor type, like the real agent."""
    calls = []

    def pick(tumor_type):
        def fake_run_agent(agent, req, ctx, **kw):
            calls.append(req)
            ctx["tumor_type"] = tumor_type
            return tumor_type or "none"
        monkeypatch.setattr(doctor.llm, "run_agent", fake_run_agent)
        return calls
    return pick


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setattr(doctor.llm, "run_agent", lambda *a, **k: None)


# --- selection and reply shape ------------------------------------------------

def test_only_covered_hospitals_and_matching_experience(no_model):
    assert set(names(req())) == {"Dr A", "Dr B", "Dr C"}                 # E is at an uncovered hospital
    assert set(names(req(hospitals=(PCMC, GG)))) == {"Dr A", "Dr B", "Dr C", "Dr E"}


def test_reply_matches_protocol_v2(no_model):
    s = doctor.handle(req(condition="ependymoma"), DATA)["scores"][0]
    assert s == {"name": "Dr D", "kind": "doctor", "hospital": PCMC, "score": 0.5,  # alone: all metrics 0.5
                 "note": "treats ependymoma, 10 yrs surgery, research 10"}


def test_no_matches_is_empty_not_error(no_model):
    assert doctor.handle(req(hospitals=("Nowhere General",)), DATA) == {"scores": []}


# --- scoring --------------------------------------------------------------------

def test_weights_decide_the_order(no_model):
    # B: research 9, 20 yrs; C: research 7, 25 yrs; A: research 7, 5 yrs (all treat 1 tumor type)
    assert names(req(weights={"Research Score": 1})) == ["Dr B", "Dr A", "Dr C"]
    assert names(req(weights={"Surgical Expertise (Years)": 1})) == ["Dr C", "Dr B", "Dr A"]


def test_scores_are_0_to_1_and_sorted(no_model):
    scores = [s["score"] for s in doctor.handle(req(), DATA)["scores"]]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 1 for s in scores)


def test_default_weights_are_equal(no_model):
    # scaled: B research 1, years .75; C research 0, years 1; A 0, 0; breadth all equal (.5)
    assert names(req()) == ["Dr B", "Dr C", "Dr A"]


def test_breadth_counts_when_weighted(no_model):
    data = [d("N", mb="Yes"), d("W", mb="Yes", hgg="Yes", ep="Yes")]
    assert names(req(weights={"Tumor Types Treated": 1}), data) == ["Dr W", "Dr N"]


def test_normalized_weights():
    assert doctor.normalized_weights(None) == dict.fromkeys(doctor.METRICS, 1 / 3)
    assert doctor.normalized_weights({}) == dict.fromkeys(doctor.METRICS, 1 / 3)
    w = doctor.normalized_weights({"Research Score": 3, "Surgical Expertise (Years)": 1})  # left out -> 0
    assert w == {"Research Score": 0.75, "Surgical Expertise (Years)": 0.25, "Tumor Types Treated": 0}


@pytest.mark.parametrize("weights", [{"Bedside Manner": 1}, {"Research Score": -1}, {"Research Score": "high"},
                                     {"Research Score": 0, "Surgical Expertise (Years)": 0}])
def test_bad_weights_rejected(no_model, weights):
    with pytest.raises(ValueError):
        doctor.handle(req(weights=weights), DATA)


# --- mapping the parent's wording ------------------------------------------------

@pytest.mark.parametrize("condition", ["Pediatric High-Grade Glioma", "high-grade glioma", "HGG",
                                       "  pediatric_high-grade  glioma "])
def test_known_wording_skips_the_model(agent_picks, condition):
    calls = agent_picks("ependymoma")  # would be wrong if it were used
    assert doctor.tumor_type_for(condition, DATA) == "pediatric high-grade glioma"
    assert calls == []


def test_other_wording_uses_the_tool_recorded_tumor_type(agent_picks):
    calls = agent_picks("pediatric high-grade glioma")
    assert names(req(condition="DIPG", summary="7-year-old, brainstem lesion")) == ["Dr D"]
    assert calls == [{"condition": "DIPG", "summary": "7-year-old, brainstem lesion"}]  # no age, no hospitals


def test_model_finds_no_match_is_an_error(agent_picks):
    agent_picks(None)
    with pytest.raises(ValueError, match="unknown condition"):
        doctor.handle(req(condition="broken arm"), DATA)


def test_model_unavailable_and_unknown_wording_is_an_error(no_model):
    with pytest.raises(ValueError, match="unknown condition"):
        doctor.handle(req(condition="DIPG"), DATA)


# --- real data ---------------------------------------------------------------------

def test_real_dataset(no_model):
    data = doctor.load(DATA_DIR)
    hospitals = sorted({r["Hospital Name"] for r in data})
    assert len(data) == 150 and len(hospitals) == 30
    for condition, expected in [("medulloblastoma", 97), ("pediatric high-grade glioma", 94), ("ependymoma", 95)]:
        out = doctor.handle(req(condition=condition, hospitals=hospitals), data)["scores"]
        assert len(out) == expected
    two = hospitals[:2]
    out = doctor.handle(req(hospitals=two), data)["scores"]
    assert out and {s["hospital"] for s in out} <= set(two)
