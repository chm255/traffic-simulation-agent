from __future__ import annotations

from mcp.server import MCPServer


# ============================================================
# 1. Create MCP Server
# ============================================================

mcp = MCPServer(
    "Traffic Learning MCP Server"
)


# ============================================================
# 2. Tool: multiply
# ============================================================

@mcp.tool()
def multiply(
    a: int,
    b: int,
) -> int:
    """
    Multiply two integers.
    """

    return a * b


# ============================================================
# 3. Tool: describe_scenario
# ============================================================


#把普通 Python Function 注册为 MCP Tool。
@mcp.tool()
def describe_scenario(
    scenario: str,
) -> dict[str, str]:
    """
    Return simple information about a traffic scenario.
    """

    if scenario == "cross":

        return {
            "scenario": "cross",
            "description":
                "A simple SUMO intersection "
                "scenario used in this project.",
        }

    return {
        "scenario": scenario,
        "description":
            "Unknown scenario.",
    }


# ============================================================
# 4. Run Server
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="stdio"
    )