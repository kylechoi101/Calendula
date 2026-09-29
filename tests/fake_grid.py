"""In-process stand-in for agent.grid: routes pushes straight to worker handlers. No SuperLink needed."""

import json

from calendula import workers


class FakeAgent:
    def __init__(self, prompt: str, roles=tuple(workers.WORKERS), history: list[dict] = ()):
        self.prompt = prompt
        self.history = list(history)  # earlier turns: [{"role": "user"|"assistant", "text": ...}]
        self.nodes = {str(i): role for i, role in enumerate(roles, 1)}  # node_id -> role
        self.outbox: dict[str, dict] = {}  # message_id -> reply message
        self.sent: list[tuple[str, dict]] = []  # (role, request envelope) for assertions
        self.chat: list[str] = []
        self.grid = self
        self.events = self

    def emit(self, event: dict) -> None:
        if event.get("type") == "response.output_text.delta":
            self.chat.append(event["delta"])

    def get_trace(self) -> list[dict]:
        """Earlier turns as Flower stores them, then this run's prompt (Flower records it at run start)."""
        out = []
        for t in self.history + [{"role": "user", "text": self.prompt}]:
            if t["role"] == "user":
                out.append({"event": "message", "data": {"type": "message", "role": "user", "content": t["text"]}})
            else:
                out.append({"event": "response.output_text.delta",
                            "data": {"type": "response.output_text.delta", "delta": t["text"]}})
        return out

    @property
    def text(self) -> str:
        return "".join(self.chat)

    def call(self, fc: dict) -> dict:
        args = json.loads(fc["arguments"])
        out = getattr(self, "_" + fc["name"])(**args)
        return {"type": "function_call_output", "call_id": fc["call_id"], "output": json.dumps(out)}

    def _get_nodes(self, sample_size=None):
        return {"nodes": [{"id": n, "name": None, "location": None} for n in self.nodes],
                "num_available": len(self.nodes)}

    def _push_messages(self, messages):
        results = []
        for m in messages:
            mid = f"m{len(self.outbox) + 1}"
            role = self.nodes[m["dst_node_id"]]
            self.sent.append((role, json.loads(m["payload"])))
            self.outbox[mid] = {"message_id": f"r-{mid}", "reply_to_message_id": mid,
                                "src_node_id": m["dst_node_id"], "error": None,
                                "payload": workers.answer(role, m["payload"])}
            results.append({"message_id": mid, "error": None})
        return {"results": results}

    def _pull_messages(self, message_ids, timeout):
        return {"messages": [self.outbox.pop(i) for i in message_ids if i in self.outbox],
                "pending_message_ids": []}
