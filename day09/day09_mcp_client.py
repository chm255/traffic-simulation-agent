from __future__ import annotations

import asyncio
import json

from mcp import Client

from day09.day09_mcp_server import (
    mcp,
)


# ============================================================
# Main
# ============================================================

async def main() -> None:

    print()
    print("=" * 70)
    print("Connect MCP Client")
    print("=" * 70)

    # --------------------------------------------------------
    # In-memory MCP connection
    # --------------------------------------------------------

    async with Client(mcp) as client:

        # ====================================================
        # 1. Discover Tools
        # ====================================================

        print()
        print("=" * 70)
        print("List MCP Tools")
        print("=" * 70)

        tools_result = (
            await client.list_tools()
        )

        for tool in tools_result.tools:

            print()
            print(
                f"Tool Name: "
                f"{tool.name}"
            )

            print(
                f"Description: "
                f"{tool.description}"
            )

            print(
                "Input Schema:"
            )

            print(
                json.dumps(
                    tool.input_schema,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        # ====================================================
        # 2. Call multiply
        # ====================================================

        print()
        print("=" * 70)
        print("Call Tool: multiply")
        print("=" * 70)

        result = await client.call_tool(
            "multiply",
            {
                "a": 23,
                "b": 17,
            },
        )

        print(
            "Structured Result:"
        )

        print(
            result.structured_content
        )

        # ====================================================
        # 3. Call describe_scenario
        # ====================================================

        print()
        print("=" * 70)
        print(
            "Call Tool: describe_scenario"
        )
        print("=" * 70)

        scenario_result = (
            await client.call_tool(
                "describe_scenario",
                {
                    "scenario": "cross",
                },
            )
        )

        print(
            "Structured Result:"
        )

        print(
            json.dumps(
                scenario_result
                .structured_content,
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )