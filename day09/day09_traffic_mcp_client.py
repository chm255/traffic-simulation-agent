from __future__ import annotations

import asyncio
import json

from mcp import Client

from day09.day09_traffic_mcp_server import (
    mcp,
)


# ============================================================
# Main
# ============================================================

async def main() -> None:

    print()
    print("=" * 80)
    print(
        "Traffic MCP Client"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # In-memory MCP transport
    # --------------------------------------------------------

    async with Client(mcp) as client:

        # ====================================================
        # 1. Discover MCP Tools
        # ====================================================

        print()
        print("=" * 80)
        print(
            "Step 1: Discover MCP Tools"
        )
        print("=" * 80)

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
                f"Title: "
                f"{tool.title}"
            )

            print(
                f"Description:"
            )

            print(
                tool.description
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

            print(
                "Output Schema:"
            )

            print(
                json.dumps(
                    tool.output_schema,
                    ensure_ascii=False,
                    indent=2,
                )
                if tool.output_schema
                else "None"
            )

        # ====================================================
        # 2. Call Real SUMO MCP Tool
        # ====================================================

        print()
        print("=" * 80)
        print(
            "Step 2: Call MCP Tool"
        )
        print("=" * 80)

        print(
            "Calling:"
        )

        print(
            "run_sumo_experiment("
            "scenario='cross', "
            "seed=42, "
            "duration=300"
            ")"
        )

        result = await client.call_tool(
            "run_sumo_experiment",
            {
                "scenario":
                    "cross",

                "seed":
                    42,

                "duration":
                    300,
            },
        )

        # ====================================================
        # 3. Inspect MCP Result
        # ====================================================

        print()
        print("=" * 80)
        print(
            "Step 3: MCP Tool Result"
        )
        print("=" * 80)

        print(
            f"Is Error: "
            f"{result.is_error}"
        )

        print()

        print(
            "Structured Content:"
        )

        print(
            json.dumps(
                result.structured_content,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        # ----------------------------------------------------
        # Also inspect model-readable content
        # ----------------------------------------------------

        print()
        print(
            "Content Blocks:"
        )

        for block in result.content:

            print(
                block
            )


if __name__ == "__main__":

    asyncio.run(
        main()
    )