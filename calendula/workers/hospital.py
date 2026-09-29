"""Hospital agent: owns data/hospital.json. Request type: hospitals. Uses the model.

The agent matches the patient's condition to the hospital's outcome records (e.g. "afib" ->
"atrial fibrillation") via tools; the numbers in the reply come from data, never the model.
"""

import json
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool
from pydantic import BaseModel

from calendula import llm

PROMPT = """You look up hospitals for a patient. For every hospital id in the request, call
list_conditions, pick the recorded condition that matches the request's condition (or none if no
record matches), then call get_hospital with that exact name (or null)."""


class Done(BaseModel):
    hospital_ids: list[str]


def lookup(data: dict, hid: str, condition: str | None, specialty: str) -> dict | None:
    h = data["hospitals"].get(hid)
    if h is None:
        return None
    o = h.get("outcomes", {}).get(condition or "", {})
    return {"name": h["name"], "ranking": h["ranking"], "doctor_patient_ratio": h["doctor_patient_ratio"],
            "mortality": o.get("mortality"), "case_volume": o.get("case_volume"),
            "wait_days": h.get("wait_days", {}).get(specialty)}


@function_tool
def list_conditions(ctx: RunContextWrapper[dict], hospital_id: str) -> list[str]:
    """Conditions this hospital has outcome records for."""
    return list(ctx.context["data"]["hospitals"].get(hospital_id, {}).get("outcomes", {}))


@function_tool
def get_hospital(ctx: RunContextWrapper[dict], hospital_id: str, condition: str | None) -> dict | None:
    """Ranking, staffing, wait days and outcomes for one hospital. condition must be from list_conditions."""
    found = lookup(ctx.context["data"], hospital_id, condition, ctx.context["specialty"])
    ctx.context["seen"][hospital_id] = found
    return found


AGENT = Agent(name="hospital", instructions=PROMPT, tools=[list_conditions, get_hospital], output_type=Done)


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "hospital.json").read_text())


def handle(req: dict, data: dict) -> dict:
    ctx = {"data": data, "specialty": req["specialty"], "seen": {}}
    llm.run_agent(AGENT, req, ctx)
    hospitals = {}
    for hid in req["hospital_ids"]:  # anything the agent skipped: exact-match lookup
        h = ctx["seen"].get(hid) or lookup(data, hid, req["condition"], req["specialty"])
        if h:
            hospitals[hid] = h
    return {"hospitals": hospitals}
