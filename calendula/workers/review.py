"""Review agent: owns the doctor ratings. Request type: reviews. Uses the model for the note only.

Data: artificial_doctor_ratings.csv (Google and GoodDoctor stars per doctor). The doctor -> hospital link
comes from artificial_pediatric_brain_cancer_doctors.csv so the agent can keep to covered hospitals.
Scores come from the ratings, never the model; the model only writes the one-line note per doctor.
"""

import csv
from pathlib import Path

from agents import Agent, RunContextWrapper, StopAtTools, function_tool
from pydantic import BaseModel

from calendula import llm

RATINGS = "artificial_doctor_ratings.csv"
DOCTORS = "artificial_pediatric_brain_cancer_doctors.csv"

PROMPT = """You summarize doctors' public ratings for a worried parent. Call get_ratings once with the
request's hospitals, then call submit_notes once with, for every doctor, a note of 10 words or fewer
about their reputation (e.g. "highly rated on both sites", "ratings differ between sites").
Do not invent numbers."""


class Note(BaseModel):
    doctor_id: str
    note: str


def load(data_dir: Path) -> dict:
    with open(data_dir / DOCTORS, newline="") as f:
        hospital = {r["Doctor ID"]: r["Hospital Name"] for r in csv.DictReader(f)}
    with open(data_dir / RATINGS, newline="") as f:
        doctors = [{"id": r["Doctor ID"], "name": r["Doctor Name"], "hospital": hospital.get(r["Doctor ID"]),
                    "google": float(r["Google Rating (1-5)"]), "gooddoctor": float(r["GoodDoctor Rating (1-5)"])}
                   for r in csv.DictReader(f)]
    return {"doctors": doctors}


def at(data: dict, hospitals: list[str]) -> list[dict]:
    covered = set(hospitals)
    return [d for d in data["doctors"] if d["hospital"] in covered]


def default_note(d: dict) -> str:
    return f"Google {d['google']}, GoodDoctor {d['gooddoctor']}" + (
        " (sites disagree)" if abs(d["google"] - d["gooddoctor"]) >= 1 else "")


@function_tool
def get_ratings(ctx: RunContextWrapper[dict], hospitals: list[str]) -> list[dict]:
    """Google and GoodDoctor ratings (1-5) for every doctor at these hospitals."""
    return [{k: d[k] for k in ("id", "name", "google", "gooddoctor")} for d in at(ctx.context["data"], hospitals)]


@function_tool
def submit_notes(ctx: RunContextWrapper[dict], notes: list[Note]) -> str:
    """Submit one note per doctor. Ends the task."""
    ctx.context["notes"] = notes
    return "ok"


AGENT = Agent(name="review", instructions=PROMPT, tools=[get_ratings, submit_notes],
              tool_use_behavior=StopAtTools(stop_at_tool_names=["submit_notes"]))


def handle(req: dict, data: dict) -> dict:
    found = at(data, req["hospitals"])
    if not found:
        return {"scores": []}
    # The model sees only hospital names; ratings reach it through the tool. The case brief isn't needed.
    ctx = {"data": data, "notes": []}
    llm.run_agent(AGENT, {"hospitals": req["hospitals"]}, ctx)
    notes = {n.doctor_id: n.note for n in ctx["notes"]}
    scores = []
    for d in found:
        avg = (d["google"] + d["gooddoctor"]) / 2
        scores.append({"name": d["name"], "kind": "doctor", "hospital": d["hospital"],
                       "score": round((avg - 1) / 4, 3), "note": notes.get(d["id"]) or default_note(d)})
    return {"scores": scores}
