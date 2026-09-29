"""Thin wrappers over Flower's Grid tools (flwr 1.39), called directly without the model."""

import json
from uuid import uuid4


def call(agent, name: str, **args) -> dict:
    out = agent.grid.call({
        "type": "function_call", "call_id": f"c-{name}-{uuid4().hex[:8]}",
        "name": name, "arguments": json.dumps(args),
    })
    return json.loads(out["output"])


def node_ids(agent) -> list[str]:
    return [n["id"] for n in call(agent, "get_nodes", sample_size=None)["nodes"]]


def send_and_receive(agent, requests: dict[str, dict], timeout: float = 60) -> dict[str, dict | None]:
    """Send {node_id: envelope} in one push, wait once. Returns {node_id: reply envelope, or None if missing}."""
    ids = list(requests)
    pushed = call(agent, "push_messages", messages=[
        {"dst_node_id": n, "payload": json.dumps(requests[n]), "reply_to_message_id": None} for n in ids
    ])["results"]  # same order as sent
    by_msg = {r["message_id"]: n for r, n in zip(pushed, ids) if r["message_id"]}
    pulled = call(agent, "pull_messages", message_ids=list(by_msg), timeout=timeout)
    replies: dict[str, dict | None] = dict.fromkeys(ids)
    for m in pulled["messages"]:
        node = by_msg.get(m["reply_to_message_id"])
        if node and m["payload"]:
            try:
                replies[node] = json.loads(m["payload"])
            except json.JSONDecodeError:
                pass  # garbage reply counts as missing
    return replies


def reply_once(agent, payload: str) -> None:
    """Worker side: answer the message that started this run. Call exactly once."""
    call(agent, "push_reply_message", payload=payload)


def transcript(agent) -> list[dict]:
    """The chat so far as [{"role": "user"|"assistant", "text": ...}], ending with this run's prompt.

    Each `flwr chat` turn is a new run in one run series; get_trace() returns the whole series: the user's
    prompts as "message" events and our replies as text deltas.
    """
    turns: list[dict] = []
    try:
        trace = agent.events.get_trace()
    except Exception:  # noqa: BLE001 - no history available: this prompt is the whole conversation
        trace = []
    for e in trace:
        d = e.get("data") or {}
        kind = e.get("event") or d.get("type")
        if kind == "message" and d.get("role") == "user" and isinstance(d.get("content"), str):
            turns.append({"role": "user", "text": d["content"]})
        elif kind == "response.output_text.delta" and isinstance(d.get("delta"), str):
            if turns and turns[-1]["role"] == "assistant":
                turns[-1]["text"] += d["delta"]
            else:
                turns.append({"role": "assistant", "text": d["delta"]})
    if not turns or turns[-1] != {"role": "user", "text": agent.prompt}:
        turns.append({"role": "user", "text": agent.prompt})
    return turns


def say(agent, text: str) -> None:
    """Show text in `flwr chat` (renders output_text delta events only) and in `flwr log` (stdout only)."""
    agent.events.emit({"type": "response.output_text.delta", "delta": text})
    print(text, end="", flush=True)
