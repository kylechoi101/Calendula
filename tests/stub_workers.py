"""Protocol-v2 stand-ins for the agents teammates own (insurance, hospital, travel), built on the CSVs.

Used only in coordinator tests until the real workers speak v2. Deliberately simple.
"""

import csv
from types import SimpleNamespace

CONTRACTS = "artificial_insurance_hospital_contracts.csv"
HOSPITALS = "artificial_hospital_data_california.csv"


def _insurance_load(data_dir):
    with open(data_dir / CONTRACTS, newline="") as f:
        return {r.pop("Insurance Provider"): [h for h, v in r.items() if v == "1"] for r in csv.DictReader(f)}


def _insurance_handle(req, data):
    if req["insurer"] not in data:
        raise ValueError(f"unknown insurer {req['insurer']!r}")
    return {"hospitals": data[req["insurer"]]}


def _hospital_load(data_dir):
    with open(data_dir / HOSPITALS, newline="") as f:
        return {r["Hospital Name"]: r for r in csv.DictReader(f)}


def _hospital_handle(req, data):
    return {"scores": [{"name": h, "kind": "hospital", "hospital": h,
                        "score": round(1 - (int(data[h]["Hospital Ranking"]) - 1) / 30, 3),
                        "note": f"ranked #{data[h]['Hospital Ranking']}"} for h in req["hospitals"] if h in data]}


def _travel_handle(req, data):
    # Stand-in distance: ZIP-number closeness. The real travel agent uses Google Maps.
    z = int(req["case"]["zip"])
    return {"scores": [{"name": h, "kind": "hospital", "hospital": h,
                        "score": round(max(0.0, 1 - abs(int(data[h]["ZIP Code"]) - z) / 5000), 3),
                        "note": f"ZIP {data[h]['ZIP Code']}"} for h in req["hospitals"] if h in data]}


STUBS = {
    "insurance": SimpleNamespace(load=_insurance_load, handle=_insurance_handle),
    "hospital": SimpleNamespace(load=_hospital_load, handle=_hospital_handle),
    "travel": SimpleNamespace(load=_hospital_load, handle=_travel_handle),
}
