"""Start one chat run without the interactive `flwr chat` UI, then stream its log.

    uv run scripts/ask.py "I have atrial fibrillation, PLAN-B, zip 94301"
    FLWR_CHAT_SUPERLINK=supergrid FLWR_CHAT_FEDERATION=@kylechoi101/calendula uv run scripts/ask.py "..."

Uses flwr CLI internals (flwr 1.39); if an upgrade breaks it, fall back to `flwr chat`.
"""

import os
import subprocess
import sys
from pathlib import Path

from flwr.cli.chat.chat_app import start_chat_run
from flwr.cli.chat.chat_local_agent import build_local_agent
from flwr.cli.flower_config import read_superlink_connection
from flwr.cli.utils import init_http_client_from_connection

superlink = os.getenv("FLWR_CHAT_SUPERLINK", "local-deployment")
app = build_local_agent(Path(__file__).resolve().parents[1])
stub = init_http_client_from_connection(read_superlink_connection(superlink))
federation = os.getenv("FLWR_CHAT_FEDERATION")  # SuperGrid: the federation the agent nodes are in
run_id, _ = start_chat_run(stub, sys.argv[1], federation, None, fab_hash=app.fab_hash, fab_content=app.fab_content)
print(f"run {run_id}", flush=True)
subprocess.run(["flwr", "log", str(run_id), superlink])
