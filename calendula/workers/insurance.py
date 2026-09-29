"""Insurance agent: owns data/insurance.json. Request type: coverage. Uses the model.

The agent checks each hospital with a tool; network status in the reply comes from data, never the model.
"""

import json
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool

from calendula import llm

PROMPT = """You check insurance coverage. Call check_coverage once with the request's plan_id and all
of its hospital_ids."""


def in_network(data: dict, plan_id: str, hids: list[str]) -> dict[str, bool]:
    if plan_id not in data["plans"]:
        raise ValueError(f"unknown plan {plan_id!r}")
    return {h: h in data["plans"][plan_id] for h in hids}


@function_tool
def check_coverage(ctx: RunContextWrapper[dict], plan_id: str, hospital_ids: list[str]) -> dict[str, bool]:
    """Whether each hospital is in-network for the plan. Errors on an unknown plan."""
    found = in_network(ctx.context["data"], plan_id, hospital_ids)
    ctx.context["seen"].update(found)
    return found


# Results land in ctx["seen"]; stop right after the tool instead of asking the model to summarize.
AGENT = Agent(name="insurance", instructions=PROMPT, tools=[check_coverage], tool_use_behavior="stop_on_first_tool")


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "insurance.json").read_text())


def handle(req: dict, data: dict) -> dict:
    ctx = {"data": data, "seen": {}}
    llm.run_agent(AGENT, req, ctx)
    missing = [h for h in req["hospital_ids"] if h not in ctx["seen"]]
    # Unknown plan raises here even if the agent swallowed it; the dispatcher replies with an error.
    seen = ctx["seen"] | in_network(data, req["plan_id"], missing)
    return {"coverage": {h: seen[h] for h in req["hospital_ids"]}}
