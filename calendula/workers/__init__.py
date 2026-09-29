"""Worker dispatch. Each worker module exposes load(data_dir) -> data and handle(request_data, data) -> reply_data.

Workers never touch Flower: `answer` is plain str -> str, so every worker is testable in pytest.
"""

import json
import os
from pathlib import Path

from calendula import grid, protocol
from calendula.workers import doctor, hospital, insurance, review, travel

WORKERS = {"doctor": doctor, "review": review, "hospital": hospital, "insurance": insurance, "travel": travel}
# CALENDULA_DATA_DIR: each SuperNode reads its data from local disk (the CSVs can't ride in the FAB, which
# only bundles .py/.toml/.md/.yaml/.json/.jsonl). Unset: the repo's data/ folder (pytest, local dev).
DATA_DIR = Path(os.environ.get("CALENDULA_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")

_data: dict[str, object] = {}  # loaded once per process


def answer(role: str, payload: str) -> str:
    """Handle one request envelope. Always returns a reply envelope; never raises."""
    try:
        env = protocol.parse(payload)
    except protocol.ProtocolError as e:
        return json.dumps(protocol.error(str(e)))
    if role not in WORKERS:
        return json.dumps(protocol.error(f"unknown role {role!r}", env["id"]))
    if env["type"] == "whoami":
        return json.dumps(protocol.envelope("whoami", {"role": role}, env["id"]))
    if env["type"] != protocol.ROLE_TYPE[role]:
        return json.dumps(protocol.error(f"{role} does not handle {env['type']!r}", env["id"]))
    try:
        if role not in _data:
            _data[role] = WORKERS[role].load(DATA_DIR)
        reply = WORKERS[role].handle(env["data"], _data[role])
    except Exception as e:  # a buggy worker returns an error envelope instead of crashing the node
        return json.dumps(protocol.error(f"{role} failed: {e}", env["id"]))
    return json.dumps(protocol.envelope(env["type"], reply, env["id"]))


def serve(agent, role: str) -> None:
    """Flower entry on a SuperNode. agent.prompt is {"message_id", "src_node_id", "payload"}."""
    try:
        payload = json.loads(agent.prompt)["payload"]
    except (json.JSONDecodeError, KeyError, TypeError):
        payload = ""
    grid.reply_once(agent, answer(role, payload))
