"""Talking to workers: role discovery and parallel requests."""

from calendula import grid
from calendula.protocol import envelope


def discover(agent) -> dict[str, str]:
    """Broadcast whoami; returns {role: node_id}. get_nodes has no names locally, so we ask."""
    ids = grid.node_ids(agent)
    if not ids:
        return {}
    replies = grid.send_and_receive(agent, {n: envelope("whoami", {}) for n in ids}, timeout=30)
    return {r["data"]["role"]: n for n, r in replies.items() if r and r.get("type") == "whoami"}


def ask(agent, roles: dict[str, str], requests: dict[str, dict], timeout: float = 60,
        errors: dict[str, str] | None = None) -> dict[str, dict | None]:
    """Send {role: envelope} in parallel. Returns {role: reply data, or None if offline/timeout/error}.

    If `errors` is given, each failed role's reason is stored there.
    """
    # TODO(coordinator owner): 200 s watchdog from the spec.
    online = {r: e for r, e in requests.items() if r in roles}
    for r in requests.keys() - online.keys():
        grid.say(agent, f"- {r} agent offline\n")
    for r in online:
        grid.say(agent, f"→ {r} agent…\n")
    replies = grid.send_and_receive(agent, {roles[r]: e for r, e in online.items()}, timeout) if online else {}
    out: dict[str, dict | None] = dict.fromkeys(requests)
    for r in online:
        reply = replies.get(roles[r])
        if reply and reply.get("type") != "error":
            out[r] = reply["data"]
        else:
            reason = reply["data"]["message"] if reply else "no reply"
            if errors is not None:
                errors[r] = reason
            grid.say(agent, f"- {r} agent missing: {reason}\n")
    return out
