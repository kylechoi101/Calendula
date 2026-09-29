import pytest

from calendula import llm, workers
from calendula.workers import insurance

DATA = insurance.load(workers.DATA_DIR)


def test_csv_loads_ten_insurers_with_covered_hospitals():
    assert len(DATA) == 10
    assert "Golden Gate Specialty Hospital" in DATA["SierraCare Health Plan"]
    assert all(DATA.values())


def test_exact_name_any_case_skips_the_model(monkeypatch):
    monkeypatch.setattr(llm, "run_agent", lambda *a: pytest.fail("model called for an exact name"))
    out = insurance.handle({"insurer": "  sierracare health plan "}, DATA)
    assert out == {"hospitals": DATA["SierraCare Health Plan"]}


def test_fuzzy_name_uses_the_insurer_the_agent_picked(monkeypatch):
    monkeypatch.setattr(llm, "run_agent", lambda agent, req, ctx: ctx.update(insurer="SierraCare Health Plan"))
    assert insurance.handle({"insurer": "Sierra Care"}, DATA) == {"hospitals": DATA["SierraCare Health Plan"]}


def test_no_match_is_unknown_insurer(monkeypatch):
    monkeypatch.setattr(llm, "run_agent", lambda *a: None)
    with pytest.raises(ValueError, match="unknown insurer"):
        insurance.handle({"insurer": "Acme Health Plan"}, DATA)
