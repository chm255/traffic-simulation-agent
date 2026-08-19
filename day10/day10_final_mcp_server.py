from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from day06.day06_rag_tool_agent import (
    TOOL_MAP,
)


# ============================================================
# 1. Reuse Existing Business Capabilities
# ============================================================

real_search_project_knowledge = (
    TOOL_MAP[
        "search_project_knowledge"
    ]
)

real_run_sumo_experiment = (
    TOOL_MAP[
        "run_sumo_experiment"
    ]
)


# ============================================================
# 2. MCP Server
# ============================================================

mcp = MCPServer(
    "Traffic Simulation Final MCP Server"
)


# ============================================================
# 3. Knowledge Tool
# ============================================================

@mcp.tool(
    name="search_project_knowledge",
    title="Search Project Knowledge",
)
def search_project_knowledge_mcp(
    query: str,
) -> dict[str, Any]:
    """
    Search the local Traffic Simulation Agent project
    knowledge base.

    Use this tool when the user asks about project-specific
    definitions, metrics, scenarios, experiment rules,
    or other information stored in the project knowledge base.

    This is a read-only knowledge retrieval capability.

    Parameters:
    - query: the project knowledge question or search query

    Returns:
    - retrieved project knowledge
    - retrieval scores
    - relevant source chunks
    """

    print()
    print("=" * 80)
    print(
        "MCP Tool: "
        "search_project_knowledge"
    )
    print("=" * 80)

    print(
        f"Query: {query}"
    )

    return (
        real_search_project_knowledge(
            query=query
        )
    )


# ============================================================
# 4. SUMO Tool
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

    This tool executes a real SUMO simulation and consumes
    computational resources.

    Parameters:
    - scenario: semantic scenario name, such as "cross"
    - seed: random seed explicitly provided by the user
    - duration: simulation duration in seconds explicitly
      provided by the user

    Returns:
    - simulation configuration
    - vehicle counts
    - accumulated waiting time
    - traffic performance metrics
    """

    print()
    print("=" * 80)
    print(
        "MCP Tool: "
        "run_sumo_experiment"
    )
    print("=" * 80)

    print(
        f"Scenario: {scenario}"
    )

    print(
        f"Seed: {seed}"
    )

    print(
        f"Duration: {duration}"
    )

    return (
        real_run_sumo_experiment(
            scenario=scenario,
            seed=seed,
            duration=duration,
        )
    )


# ============================================================
# 5. Optional stdio Entry Point
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="stdio"
    )