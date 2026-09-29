#!/usr/bin/env bash
# Local rehearsal (run `uv sync` first): 1 SuperLink + 5 SuperNodes (one per worker role). Ctrl-C stops all. Logs in logs/.
set -euo pipefail
trap 'kill 0' EXIT
mkdir -p logs
# Model endpoint + key for every node (see .env.example). Flower Runtime takes one key per process;
# the Kimi key also works for MiniMax on this endpoint.
set -a; source .env; set +a
export FLWR_MODEL_API_ENDPOINT="${FLWR_MODEL_API_ENDPOINT:-https://api.tokenfactory.tf-ca1.nebius.com/v1/responses}"
export FLWR_MODEL_API_KEY="${FLWR_MODEL_API_KEY:-$KIMI_API_KEY}"
# Workers read the CSVs from here (not from the installed app bundle, which drops .csv files).
export CALENDULA_DATA_DIR="$PWD/data"

# Control API on 9093 (8000 is often taken); no per-run `uv sync`, deps come from this env.
uv run flower-superlink --insecure --port 9093 --disable-runtime-dependency-installation > logs/superlink.log 2>&1 &
sleep 3

port=9094
for role in doctor review hospital insurance travel; do
  uv run flower-supernode --insecure --superlink 127.0.0.1:9092 \
    --port $port --node-config "role=\"$role\"" > "logs/$role.log" 2>&1 &
  port=$((port + 1))
done

echo "Cluster up. In another shell: FLWR_CHAT_SUPERLINK=local-deployment flwr chat, then /load ."
wait
