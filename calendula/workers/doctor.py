"""Doctor agent: owns data/doctor.json. Request type: find_doctors. Uses the model.

The agent pulls candidates with a tool and scores them; facts (name, expertise, ...) come from data, never the model.
"""

import json
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool
from pydantic import BaseModel

from calendula import llm

PROMPT = """You score how relevant doctors are to a patient's condition.
Call find_candidates with the request's specialty and needs_surgery, then for every candidate return a
relevance score from 0 to 1 and a rationale of 12 words or fewer, based only on their research_interest
and surgical procedures."""


class Score(BaseModel):
    npi: str
    relevance: float
    rationale: str


class Scores(BaseModel):
    scores: list[Score]


def candidates(data: dict, specialty: str, needs_surgery: bool) -> list[dict]:
    return [d for d in data["doctors"]
            if d["specialty"] == specialty and (not needs_surgery or d.get("surgical_expertise"))]


@function_tool
def find_candidates(ctx: RunContextWrapper[dict], specialty: str, needs_surgery: bool) -> list[dict]:
    """Doctors in this directory with the given specialty (and surgical experience if needs_surgery)."""
    found = candidates(ctx.context["data"], specialty, needs_surgery)
    return [{"npi": d["npi"], "research_interest": d["research_interest"],
             "procedures": list(d.get("surgical_expertise", {}))} for d in found]


AGENT = Agent(name="doctor", instructions=PROMPT, tools=[find_candidates], output_type=Scores)


def keyword_score(condition: str, d: dict) -> float:
    words = set(condition.lower().split())
    text = f"{d['research_interest']} {' '.join(d.get('surgical_expertise', {}))}".lower()
    return len([w for w in words if w in text]) / max(len(words), 1)


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "doctor.json").read_text())


def handle(req: dict, data: dict) -> dict:
    found = candidates(data, req["specialty"], req["needs_surgery"])
    out = llm.run_agent(AGENT, req, {"data": data})
    scores = {s.npi: s for s in out.scores} if out else {}
    doctors = []
    for d in found:
        s = scores.get(d["npi"])  # scores for unknown NPIs are ignored
        doctors.append({
            k: d[k] for k in ("npi", "name", "specialty", "hospital_id", "accepting_new_patients",
                              "expertise", "research_score")
        } | ({"relevance": min(max(s.relevance, 0.0), 1.0), "rationale": s.rationale} if s else
             {"relevance": keyword_score(req["condition"], d), "rationale": "keyword match"}))
    doctors.sort(key=lambda d: d["relevance"], reverse=True)
    return {"doctors": doctors[: req["limit"]]}
