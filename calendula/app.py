"""AgentApp entry. The same bundle runs on every node; node_config.role decides what it is."""

from flwr.agentapp import AgentApp, AgentSession
from flwr.app import Context

from calendula import coordinator, workers

app = AgentApp()


@app.main()
def main(agent: AgentSession, context: Context) -> None:
    role = context.node_config.get("role")
    if role:  # SuperNodes are started with --node-config role="<role>"
        workers.serve(agent, str(role))
    else:  # SuperLink: node_config is empty
        coordinator.run(agent)
