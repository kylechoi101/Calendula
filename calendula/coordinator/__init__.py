"""Coordinator agent (runs on the SuperLink).

Each `flwr chat` turn is one run: intake over the whole chat -> (warm follow-up and stop) or
recap -> insurance (covered hospitals) -> scoring agents in parallel -> weighted ranking -> explain.
"""

from calendula.grid import say, transcript
from calendula.protocol import ROLE_TYPE, envelope
from calendula.coordinator import explain, fanout, intake, scoring

SCORING_ROLES = ("review", "hospital", "travel", "doctor")  # doctor joins only if a node runs it


def run(agent) -> None:
    profile = intake.gather(transcript(agent))
    if profile["missing"]:  # no agent is called until the case is complete
        say(agent, profile["follow_up"] + "\n")
        return
    say(agent, intake.recap(profile))

    roles = fanout.discover(agent)  # {role: node_id}
    say(agent, f"Agents online: {', '.join(sorted(roles)) or 'none'}\n\n")

    # Step 1: insurance gets only the insurer, and returns the hospitals it covers.
    errors: dict[str, str] = {}
    cov = fanout.ask(agent, roles, {"insurance": envelope("coverage", {"insurer": profile["insurer"]})},
                     errors=errors)["insurance"]
    if cov is None:
        if "insurance" in errors and "unknown insurer" in errors["insurance"]:
            say(agent, f"\nI couldn't find **{profile['insurer']}** in our insurance records. Could you check "
                       "the plan name on your insurance card and tell me exactly how it's written?\n")
        else:
            say(agent, "\nI'm sorry, I can't reach the insurance records right now. Please try again shortly.\n")
        return
    covered = cov["hospitals"]
    if not covered:
        say(agent, f"\nI'm sorry, I couldn't find hospitals in our network that {profile['insurer']} covers "
                   "for this care. It may help to ask your insurer about out-of-network exceptions.\n")
        return
    say(agent, f"{len(covered)} hospitals are covered by {profile['insurer']}.\n\n")

    # Step 2: every scoring agent gets the covered hospitals and the case brief, in one push.
    req = {"hospitals": covered, "case": intake.case(profile)}
    asked = [r for r in SCORING_ROLES if r in roles or r != "doctor"]
    replies = fanout.ask(agent, roles, {r: envelope(ROLE_TYPE[r], req) for r in asked})

    w = intake.weights(profile)
    ranking = scoring.rank(covered, replies, w)
    missing = sorted(r for r, v in replies.items() if v is None)
    say(agent, "\n" + explain.explain(intake.case(profile), {r: w[r] for r in asked}, ranking, missing))
