"""Coordinator agent (runs on the SuperLink): intake -> discover -> phase 1 -> phase 2 -> score -> explain."""

from calendula.grid import say
from calendula.protocol import envelope
from calendula.coordinator import explain, fanout, intake, scoring


def run(agent) -> None:
    profile = intake.parse(agent.prompt)

    roles = fanout.discover(agent)  # {role: node_id}
    say(agent, f"Agents online: {', '.join(sorted(roles)) or 'none'}\n\n")

    # Phase 1: Doctor gets only condition/specialty/needs_surgery (minimum necessary).
    doctors = fanout.ask(agent, roles, {"doctor": envelope("find_doctors", {
        "condition": profile["condition"], "specialty": profile["specialty"],
        "needs_surgery": profile["needs_surgery"], "limit": 15,
    })})["doctor"]
    if not doctors:
        say(agent, "Doctor directory unavailable, try again.")
        return
    npis = [d["npi"] for d in doctors["doctors"]]
    hids = sorted({d["hospital_id"] for d in doctors["doctors"]})

    # Phase 2: four agents in one push, one wait. Each gets only the fields it needs.
    phase2 = fanout.ask(agent, roles, {
        "review": envelope("reviews", {"npis": npis}),
        "hospital": envelope("hospitals", {"hospital_ids": hids, "condition": profile["condition"],
                                           "specialty": profile["specialty"]}),
        "insurance": envelope("coverage", {"plan_id": profile["plan_id"], "hospital_ids": hids}),
        "travel": envelope("travel", {"lat": profile["lat"], "lon": profile["lon"], "hospital_ids": hids}),
    })

    rows = scoring.join(doctors, **phase2)
    top, filtered = scoring.rank(rows, profile)
    missing = sorted(r for r, v in phase2.items() if v is None)
    say(agent, explain.explain(profile, top, filtered, missing))
