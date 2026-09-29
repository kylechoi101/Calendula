"""Doctor agent: owns data/artificial_pediatric_brain_cancer_doctors.csv. Request type: find_doctors (protocol v2).

Input:  {"hospitals": [<covered hospital names>],
         "case": {"condition": <parent's wording of the tumor type>, "age": ..., "summary": ...},
         "weights": {<metric>: <number >= 0>, ...}}   # optional; set by the orchestrator
        Metrics: "Research Score", "Surgical Expertise (Years)", "Tumor Types Treated" (how many of the three
        tumor types the doctor has experience with). Same rules as the Hospital agent: weights are rescaled
        to sum to 1, a metric left out gets 0, no weights at all = equal weights. Unknown metrics, negative
        weights or all-zero weights -> error reply.
Output: {"scores": [{"name": <Doctor Name>, "kind": "doctor", "hospital": <Hospital Name>,
                     "score": <0-1>, "note": "treats medulloblastoma, 19 yrs surgery, research 6.9"}, ...]}
        Only doctors at the covered hospitals with experience in the case's tumor type, best first.
        Ties are broken by Doctor ID so the order is stable.

Score: each metric is min-max scaled within those doctors (best = 1, all equal -> 0.5), then weighted.
Raw columns other than those in the note (Hospital Ranking, Hospital Affiliated, Doctor ID, the experience
flags) stay on this node.

The model's only job is judgment: mapping the parent's wording ("DIPG", "brainstem glioma", ...) to one of the
three tumor types in the data. The select_tumor_type tool records that choice; handle() builds the reply from
the CSV, so no number passes through the model. Exact names and known aliases skip the model entirely; if the
model fails or finds no match, the reply is an error ("unknown condition").
"""

import csv
import re
from pathlib import Path
from typing import Literal

from agents import Agent, RunContextWrapper, StopAtTools, function_tool

from calendula import llm

DATA_FILE = "artificial_pediatric_brain_cancer_doctors.csv"

# Tumor type -> the dataset column that records experience with it.
EXPERIENCE_COLUMNS = {
    "medulloblastoma": "Medulloblastoma Experience",
    "pediatric high-grade glioma": "Pediatric High-Grade Glioma Experience",
    "ependymoma": "Ependymoma Experience",
}
TumorType = Literal["medulloblastoma", "pediatric high-grade glioma", "ependymoma"]
# Other ways a condition may be written -> tumor type. Anything not here goes to the model.
ALIASES = {
    "high-grade glioma": "pediatric high-grade glioma",
    "pediatric hgg": "pediatric high-grade glioma",
    "hgg": "pediatric high-grade glioma",
}
METRICS = ["Research Score", "Surgical Expertise (Years)", "Tumor Types Treated"]

PROMPT = f"""You map a parent's description of their child's brain tumor to exactly one tumor type that this
doctor directory records experience for: {", ".join(EXPERIENCE_COLUMNS)}.
The request has the parent's wording ("condition") and may have a short case summary. Call select_tumor_type
once with the matching type. If the description is not one of these tumor types, do not call the tool and
reply "none". Never guess from unrelated symptoms."""


@function_tool
def select_tumor_type(ctx: RunContextWrapper[dict], tumor_type: TumorType) -> dict:
    """Record the tumor type that matches the patient's condition; returns how many doctors have experience."""
    ctx.context["tumor_type"] = tumor_type
    column = EXPERIENCE_COLUMNS[tumor_type]
    return {"tumor_type": tumor_type, "doctors_with_experience": sum(d[column] == "Yes" for d in ctx.context["data"])}


# No output_type alongside tools (see PR #3): the answer is what select_tumor_type recorded, and the run
# stops at that tool call, so the model's final text is never needed.
AGENT = Agent(name="doctor", instructions=PROMPT, tools=[select_tumor_type],
              tool_use_behavior=StopAtTools(stop_at_tool_names=["select_tumor_type"]))


def load(data_dir: Path) -> list[dict]:
    with open(data_dir / DATA_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["Research Score"] = float(r["Research Score"])
        r["Surgical Expertise (Years)"] = int(r["Surgical Expertise (Years)"])
        r["Tumor Types Treated"] = sum(r[c] == "Yes" for c in EXPERIENCE_COLUMNS.values())
    return rows


def known_tumor_type(condition: str) -> str | None:
    """Exact tumor type or known alias (case, "_" and extra spaces ignored); None if not recognized."""
    key = re.sub(r"\s+", " ", condition.strip().lower().replace("_", " "))
    key = ALIASES.get(key, key)
    return key if key in EXPERIENCE_COLUMNS else None


def tumor_type_for(condition: str, data: list[dict], summary: str = "") -> str:
    """Known wording -> no model call. Otherwise ask the agent; raises ValueError if nothing matches."""
    tumor_type = known_tumor_type(condition)
    if tumor_type is None:
        ctx = {"data": data, "tumor_type": None}
        llm.run_agent(AGENT, {"condition": condition, "summary": summary}, ctx)
        tumor_type = ctx["tumor_type"]  # what the tool recorded, not the model's final text
    if tumor_type not in EXPERIENCE_COLUMNS:
        raise ValueError(f"unknown condition {condition!r}; expected one of {sorted(EXPERIENCE_COLUMNS)}")
    return tumor_type


def normalized_weights(weights: dict | None) -> dict[str, float]:
    """Weights rescaled to sum to 1; a metric left out gets 0; no weights at all -> equal weights."""
    if not weights:
        return dict.fromkeys(METRICS, 1 / len(METRICS))
    unknown = set(weights) - set(METRICS)
    if unknown:
        raise ValueError(f"unknown weight(s) {sorted(unknown)}; expected {METRICS}")
    if any(isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0 for w in weights.values()):
        raise ValueError("weights must be numbers >= 0")
    total = sum(weights.values())
    if total == 0:
        raise ValueError("weights are all zero")
    return {m: weights.get(m, 0) / total for m in METRICS}


def scaled(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    return [0.5] * len(values) if hi == lo else [(v - lo) / (hi - lo) for v in values]


def score(doctors: list[dict], weights: dict[str, float]) -> list[float]:
    columns = {m: scaled([d[m] for d in doctors]) for m in METRICS}
    return [sum(weights[m] * columns[m][i] for m in METRICS) for i in range(len(doctors))]


def note(tumor_type: str, d: dict) -> str:
    return (f"treats {tumor_type}, {d['Surgical Expertise (Years)']} yrs surgery, "
            f"research {d['Research Score']:g}")


def handle(req: dict, data: list[dict]) -> dict:
    weights = normalized_weights(req.get("weights"))
    case = req["case"]
    tumor_type = tumor_type_for(case["condition"], data, case.get("summary") or "")
    column = EXPERIENCE_COLUMNS[tumor_type]
    covered = set(req["hospitals"])
    matches = [d for d in data if d[column] == "Yes" and d["Hospital Name"] in covered]
    if not matches:
        return {"scores": []}
    ranked = sorted(zip(score(matches, weights), matches), key=lambda sd: (-sd[0], sd[1]["Doctor ID"]))
    return {"scores": [
        {"name": d["Doctor Name"], "kind": "doctor", "hospital": d["Hospital Name"],
         "score": round(s, 3), "note": note(tumor_type, d)}
        for s, d in ranked
    ]}
