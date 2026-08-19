from __future__ import annotations

import asyncio

from mcp import Client

from day08.day08_tool_policy import (
    AUTO,
    APPROVAL,
    get_tool_policy,
)

from day10.day10_final_mcp_server import (
    mcp,
)


EXPECTED_TOOLS = {
    "search_project_knowledge",
    "run_sumo_experiment",
}


async def main() -> None:

    print()
    print("=" * 80)
    print("Day 10 Project Smoke Test")
    print("=" * 80)

    passed = True

    # ========================================================
    # 1. MCP Discovery
    # ========================================================

    print()
    print("[1] MCP Tool Discovery")

    async with Client(mcp) as client:

        tools_result = (
            await client.list_tools()
        )

    discovered_tools = {
        tool.name
        for tool in tools_result.tools
    }

    print(
        f"Expected:   "
        f"{sorted(EXPECTED_TOOLS)}"
    )

    print(
        f"Discovered: "
        f"{sorted(discovered_tools)}"
    )

    tools_ok = (
        discovered_tools
        == EXPECTED_TOOLS
    )

    print(
        f"PASS: {tools_ok}"
    )

    passed = (
        passed and tools_ok
    )

    # ========================================================
    # 2. RAG Permission Policy
    # ========================================================

    print()
    print(
        "[2] RAG Permission Policy"
    )

    rag_policy = (
        get_tool_policy(
            "search_project_knowledge"
        )
    )

    rag_ok = (
        rag_policy["permission"]
        == AUTO
    )

    print(
        f"Permission: "
        f"{rag_policy['permission']}"
    )

    print(
        f"PASS: {rag_ok}"
    )

    passed = (
        passed and rag_ok
    )

    # ========================================================
    # 3. SUMO Permission Policy
    # ========================================================

    print()
    print(
        "[3] SUMO Permission Policy"
    )

    sumo_policy = (
        get_tool_policy(
            "run_sumo_experiment"
        )
    )

    sumo_ok = (
        sumo_policy["permission"]
        == APPROVAL
    )

    print(
        f"Permission: "
        f"{sumo_policy['permission']}"
    )

    print(
        f"PASS: {sumo_ok}"
    )

    passed = (
        passed and sumo_ok
    )

    # ========================================================
    # Summary
    # ========================================================

    print()
    print("=" * 80)
    print("Smoke Test Summary")
    print("=" * 80)

    if passed:

        print(
            "PROJECT SMOKE TEST: PASS"
        )

    else:

        print(
            "PROJECT SMOKE TEST: FAIL"
        )

        raise SystemExit(1)


if __name__ == "__main__":

    asyncio.run(
        main()
    )