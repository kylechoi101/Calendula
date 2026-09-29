import pytest

from calendula import workers
from calendula.workers import travel

DATA = travel.load(workers.DATA_DIR)
REQ = {"hospitals": ["Sacramento Valley Hospital", "Sierra Advanced Medical Center", "Imperial California Hospital"],
       "case": {"zip": "95816"}}


def fake_google(origin_zip, dest_zips):
    """Offline stand-in for the Routes API: 1 min and 0.8 mi per unit of ZIP difference."""
    return [{"miles": round(abs(int(z) - int(origin_zip)) * 0.8, 1), "minutes": abs(int(z) - int(origin_zip))}
            for z in dest_zips]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(travel, "google", fake_google)


def test_closer_hospitals_score_higher_and_carry_distance_and_time():
    scores = {s["name"]: s for s in travel.handle(REQ, DATA)["scores"]}
    home, near, far = (scores[h] for h in REQ["hospitals"])
    assert home["score"] == 1.0 and home["minutes"] == 0  # same ZIP as the family
    assert near["score"] > far["score"] == 0.0  # 95816 -> 92243 is far past the 4 h cap
    assert near["kind"] == "hospital" and near["hospital"] == near["name"]
    assert near["note"] == "0.8 mi, about 1 min drive"


def test_unknown_hospitals_are_skipped_and_unroutable_dropped(monkeypatch):
    monkeypatch.setattr(travel, "google", lambda o, ds: [None for _ in ds])
    assert travel.handle({"hospitals": ["Nowhere General"], "case": {"zip": "95816"}}, DATA) == {"scores": []}
    assert travel.handle(REQ, DATA) == {"scores": []}


def test_bad_zip_is_an_error():
    with pytest.raises(ValueError, match="invalid ZIP"):
        travel.handle({"hospitals": REQ["hospitals"], "case": {"zip": "Sacramento"}}, DATA)


def test_note_formats_hours():
    assert travel.note({"miles": 120.5, "minutes": 130}) == "120.5 mi, about 2 h 10 min drive"
