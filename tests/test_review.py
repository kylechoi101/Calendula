from calendula import workers
from calendula.workers import review

DATA = review.load(workers.DATA_DIR)


def test_scores_only_doctors_at_covered_hospitals():
    out = review.handle({"hospitals": ["Pacific Crest Medical Center"], "case": {}}, DATA)
    assert {s["hospital"] for s in out["scores"]} == {"Pacific Crest Medical Center"}
    assert len(out["scores"]) == 5


def test_score_is_mean_rating_scaled_to_0_1():
    chen = next(s for s in review.handle({"hospitals": ["Pacific Crest Medical Center"], "case": {}},
                                         DATA)["scores"] if s["name"] == "Dr. Olivia Chen")
    assert chen["kind"] == "doctor"
    assert chen["score"] == round(((4.6 + 4.9) / 2 - 1) / 4, 3)
    assert chen["note"]  # model note, or "Google 4.6, GoodDoctor 4.9" without the model


def test_no_covered_hospitals():
    assert review.handle({"hospitals": [], "case": {}}, DATA) == {"scores": []}
