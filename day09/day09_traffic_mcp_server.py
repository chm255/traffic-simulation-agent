from __future__ import annotations

from typing import Any

from mcp.server import MCPServer


# ============================================================
# 1. Reuse Existing Traffic Tool
# ============================================================

from day06.day06_rag_tool_agent import (
    TOOL_MAP,
)


# ============================================================
# 2. Get Existing SUMO Business Function
# ============================================================

real_run_sumo_experiment = (
    TOOL_MAP[
        "run_sumo_experiment"
    ]
)


# ============================================================
# 3. Create MCP Server
# ============================================================

mcp = MCPServer(
    "Traffic Simulation MCP Server"
)


# ============================================================
# 4. Expose Existing SUMO Capability as MCP Tool
# ============================================================

@mcp.tool(
    name="run_sumo_experiment",
    title="Run SUMO Experiment",
)
def run_sumo_experiment_mcp(
    scenario: str,
    seed: int,
    duration: int,
) -> dict[str, Any]:
    """
    Run a real SUMO traffic simulation experiment.

    Call this tool ONLY when the user has explicitly provided
    all three required experiment parameters:

    - scenario
    - seed
    - duration

    If any required parameter is missing, do NOT call this tool.
    Ask the user for the missing parameter instead.

    Never invent, assume, infer, or use default values for
    scenario, seed, or duration.

    Returns:
    - simulation configuration
    - vehicle counts
    - accumulated waiting time
    - traffic performance metrics
    """

    return real_run_sumo_experiment(
        scenario=scenario,
        seed=seed,
        duration=duration,
    )


# ============================================================
# 5. Run MCP Server
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="stdio"
    )