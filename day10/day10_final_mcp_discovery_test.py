from __future__ import annotations

import asyncio
import json

from mcp import Client

from day10.day10_final_mcp_server import (
    mcp,
)


async def main() -> None:

    print()
    print("=" * 80)
    print(
        "Day 10 Final MCP Discovery Test"
    )
    print("=" * 80)

    async with Client(mcp) as client:

        tools_result = (
            await client.list_tools()
        )

        print()
        print(
            f"Tool Count: "
            f"{len(tools_result.tools)}"
        )

        for index, tool in enumerate(
            tools_result.tools,
            start=1,
        ):

            print()
            print("=" * 80)

            print(
                f"Tool {index}: "
                f"{tool.name}"
            )

            print(
                f"Title: "
                f"{tool.title}"
            )

            print()
            print(
                "Description:"
            )

            print(
                tool.description
            )

            print()
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

            print()
            print(
                "Output Schema:"
            )

            print(
                json.dumps(
                    tool.output_schema,
                    ensure_ascii=False,
                    indent=2,
                )
            )


if __name__ == "__main__":

    asyncio.run(
        main()
    )