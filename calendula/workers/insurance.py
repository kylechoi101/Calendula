"""Insurance agent: owns the insurer -> hospital contracts. Request type: coverage.

Data: artificial_insurance_hospital_contracts.csv (one row per insurer, 1 = hospital in network).
An exact (case-insensitive) insurer name is answered from data directly. Otherwise the model matches what
the parent wrote ("Sierra Care", "sierracare plan") to a known insurer via tools; the covered hospitals
always come from data, never the model.
"""

import csv
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool

from calendula import llm

CONTRACTS = "artificial_insurance_hospital_contracts.csv"

PROMPT = """You match the insurance a parent wrote to one insurer in our records. Call list_insurers,
pick the one insurer that is clearly the same company or plan (ignore case, spacing, typos, and extra
words like "plan" or "insurance"), then call covered_hospitals with its exact name. If none clearly
matches, do not call covered_hospitals; reply "no match"."""


def load(data_dir: Path) -> dict:
    with open(data_dir / CONTRACTS, newline="") as f:
        return {r.pop("Insurance Provider"): [h for h, v in r.items() if v.strip() == "1"] for r in csv.DictReader(f)}


@function_tool
def list_insurers(ctx: RunContextWrapper[dict]) -> list[str]:
    """Every insurer in our records."""
    return list(ctx.context["data"])


@function_tool
def covered_hospitals(ctx: RunContextWrapper[dict], insurer: str) -> list[str]:
    """Hospitals in network for this insurer. insurer must be an exact name from list_insurers."""
    found = ctx.context["data"].get(insurer)
    if found is None:
        raise ValueError(f"unknown insurer {insurer!r}; use a name from list_insurers")
    ctx.context["insurer"] = insurer
    return found


AGENT = Agent(name="insurance", instructions=PROMPT, tools=[list_insurers, covered_hospitals])


def handle(req: dict, data: dict) -> dict:
    asked = str(req["insurer"]).strip()
    exact = {name.lower(): name for name in data}.get(asked.lower())
    if exact is None:
        ctx = {"data": data, "insurer": None}
        llm.run_agent(AGENT, {"insurer": asked}, ctx)
        exact = ctx["insurer"]
    if exact is None:  # the coordinator looks for this phrase to ask the parent to check the plan name
        raise ValueError(f"unknown insurer {asked!r}")
    return {"hospitals": data[exact]}
