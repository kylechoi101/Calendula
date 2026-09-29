"""Hospital agent: owns the hospital outcomes and capacity data. Request type: hospitals. No model.

Data: artificial_hospital_data_california.csv (one row per hospital).
Input:  {"hospitals": ["Pacific Crest Medical Center", ...], "case": {...},   # case isn't needed here
         "weights": {"Mortality Rate (%)": 5, "Wait Time (Days)": 2, ...}}   # optional, from the orchestrator
Output: {"scores": [{"name": h, "kind": "hospital", "hospital": h, "score": 0.83,
                     "note": "6.9% mortality, 1080 cases/yr, 25-day wait"}, ...]}, in request order
        (unsorted: the orchestrator ranks).

Only the requested hospitals are scored, against each other: each metric is min-max scaled within the list
(best = 1; one hospital or all equal -> 0.5), then combined with the weights the orchestrator sends: any
non-negative numbers keyed by the metric columns, rescaled to sum to 1 so scores stay in 0..1; a metric left
out gets 0; no weights -> DEFAULT_WEIGHTS. Unknown metric names, negative or all-zero weights are an error.
The coordinator then weights this whole score by the parent's "hospital_quality" priority.
Hospital Ranking and Number of Specialized Doctors are not scored: they track mortality and case volume
almost exactly, so they would count quality twice.
Unknown names are skipped; duplicates are scored once. Scores and notes come from the data, never a model.
"""

import csv
from pathlib import Path

HOSPITALS = "artificial_hospital_data_california.csv"

HIGHER_IS_BETTER = {
    "Mortality Rate (%)": False,
    "Wait Time (Days)": False,
    "Annual Cases": True,
    "Patients per Doctor": False,
}
DEFAULT_WEIGHTS = {"Mortality Rate (%)": 0.4, "Wait Time (Days)": 0.3, "Annual Cases": 0.2, "Patients per Doctor": 0.1}


def load(data_dir: Path) -> dict:
    with open(data_dir / HOSPITALS, newline="") as f:
        return {"hospitals": {r["Hospital Name"]: {col: float(r[col]) for col in HIGHER_IS_BETTER}
                              for r in csv.DictReader(f)}}


def scaled(values: list[float], higher_is_better: bool) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) if higher_is_better else (hi - v) / (hi - lo) for v in values]


def note(h: dict) -> str:
    return (f"{h['Mortality Rate (%)']:g}% mortality, {h['Annual Cases']:.0f} cases/yr, "
            f"{h['Wait Time (Days)']:.0f}-day wait")


def weights(given: dict | None) -> dict[str, float]:
    """Orchestrator weights rescaled to sum to 1; DEFAULT_WEIGHTS when none are given."""
    if not given:
        return DEFAULT_WEIGHTS
    unknown = given.keys() - HIGHER_IS_BETTER.keys()
    if unknown:
        raise ValueError(f"unknown weights {sorted(unknown)}; expected {list(HIGHER_IS_BETTER)}")
    if any(w < 0 for w in given.values()) or not sum(given.values()):
        raise ValueError("weights must be non-negative and not all zero")
    total = sum(given.values())
    return {col: given.get(col, 0) / total for col in HIGHER_IS_BETTER}


def handle(req: dict, data: dict) -> dict:
    ws = weights(req.get("weights"))
    hospitals = data["hospitals"]
    names = [n for n in dict.fromkeys(req["hospitals"]) if n in hospitals]
    if not names:
        return {"scores": []}
    scores = dict.fromkeys(names, 0.0)
    for col, weight in ws.items():
        for name, s in zip(names, scaled([hospitals[n][col] for n in names], HIGHER_IS_BETTER[col])):
            scores[name] += weight * s
    return {"scores": [{"name": n, "kind": "hospital", "hospital": n, "score": round(scores[n], 3),
                        "note": note(hospitals[n])} for n in names]}
