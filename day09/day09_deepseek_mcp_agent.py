from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import Client

from day09.day09_traffic_mcp_server import (
    mcp,
)

from day06.day06_rag_tool_agent import (
    client as deepseek_client,
    CHAT_MODEL_NAME,
)


# ============================================================
# 1. System Prompt
# ============================================================

SYSTEM_PROMPT = """
You are a Traffic Simulation Agent.

You can use tools provided by an MCP server.

Rules:

1. If the user asks you to run a traffic simulation,
   use the available MCP simulation tool ONLY when all required
   experiment parameters have been explicitly provided.

2. For run_sumo_experiment, the required parameters are:
   - scenario
   - seed
   - duration

3. If ANY required parameter is missing:
   - DO NOT call run_sumo_experiment.
   - DO NOT invent a value.
   - DO NOT use a default value.
   - DO NOT infer a value from examples.
   - Ask the user to provide the missing parameter(s).

4. Never invent scenario, seed, or duration.

5. Only report simulation results actually returned by the tool.

6. Distinguish observed simulation results from causal explanations.

7. Do not predict what would happen under another seed,
   duration, or scenario unless that experiment was actually run.
"""


# ============================================================
# 2. Convert MCP Tool -> DeepSeek Tool Schema
# ============================================================

def convert_mcp_tools_to_llm_tools(
    mcp_tools: list[Any],
) -> list[dict[str, Any]]:

    llm_tools = []

    for tool in mcp_tools:

        llm_tool = {
            "type": "function",

            "function": {
                "name":
                    tool.name,

                "description":
                    tool.description
                    or "",

                "parameters":
                    tool.input_schema,
            },
        }

        llm_tools.append(
            llm_tool
        )

    return llm_tools


# ============================================================
# 3. Convert MCP Result -> Tool Message Content
# ============================================================

def mcp_result_to_json(
    result: Any,
) -> str:

    # --------------------------------------------------------
    # Prefer structured MCP output
    # --------------------------------------------------------

    if (
        result.structured_content
        is not None
    ):

        return json.dumps(
            result.structured_content,
            ensure_ascii=False,
            default=str,
        )

    # --------------------------------------------------------
    # Fallback:
    # use MCP content blocks
    # --------------------------------------------------------

    content_items = []

    for block in result.content:

        block_text = getattr(
            block,
            "text",
            None,
        )

        if block_text is not None:

            content_items.append(
                block_text
            )

        else:

            content_items.append(
                str(block)
            )

    return json.dumps(
        {
            "is_error":
                result.is_error,

            "content":
                content_items,
        },
        ensure_ascii=False,
    )


# ============================================================
# 4. Agent Loop
# ============================================================

async def run_agent(
    user_input: str,
) -> None:

    print()
    print("=" * 80)
    print(
        "DeepSeek + MCP Traffic Agent"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # MCP Client Connection
    # --------------------------------------------------------

    async with Client(mcp) as mcp_client:

        # ====================================================
        # Step 1:
        # Discover MCP Tools
        # ====================================================

        print()
        print("=" * 80)
        print(
            "Step 1: Discover MCP Tools"
        )
        print("=" * 80)

        tools_result = (
            await mcp_client.list_tools()
        )

        mcp_tools = (
            tools_result.tools
        )

        for tool in mcp_tools:

            print()
            print(
                f"MCP Tool: "
                f"{tool.name}"
            )

            print(
                f"Description:"
            )

            print(
                tool.description
            )

        # ====================================================
        # Step 2:
        # MCP Tool -> DeepSeek Tool Schema
        # ====================================================

        llm_tools = (
            convert_mcp_tools_to_llm_tools(
                mcp_tools
            )
        )

        print()
        print("=" * 80)
        print(
            "Step 2: Convert MCP Tools "
            "to LLM Tools"
        )
        print("=" * 80)

        print(
            json.dumps(
                llm_tools,
                ensure_ascii=False,
                indent=2,
            )
        )

        # ====================================================
        # Step 3:
        # Initialize Conversation
        # ====================================================

        messages = [
            {
                "role":
                    "system",

                "content":
                    SYSTEM_PROMPT,
            },
            {
                "role":
                    "user",

                "content":
                    user_input,
            },
        ]

        # ====================================================
        # Step 4:
        # Agent Loop
        # ====================================================

        max_steps = 6

        for step in range(
            1,
            max_steps + 1,
        ):

            print()
            print("=" * 80)
            print(
                f"Agent Step {step}"
            )
            print("=" * 80)

            # ------------------------------------------------
            # LLM Decision
            # ------------------------------------------------

            response = (
                deepseek_client
                .chat
                .completions
                .create(
                    model=
                        CHAT_MODEL_NAME,

                    messages=
                        messages,

                    tools=
                        llm_tools,

                    tool_choice=
                        "auto",

                    extra_body={
                        "thinking": {
                            "type":
                                "disabled",
                        }
                    },
                )
            )

            assistant_message_obj = (
                response
                .choices[0]
                .message
            )

            assistant_message = (
                assistant_message_obj
                .model_dump(
                    exclude_none=True
                )
            )

            messages.append(
                assistant_message
            )

            tool_calls = (
                assistant_message_obj
                .tool_calls
            )

            # =================================================
            # No Tool Call -> Final Answer
            # =================================================

            if not tool_calls:

                print()
                print(
                    "LLM Decision: "
                    "Final Answer"
                )

                print()
                print("=" * 80)
                print("Final Answer")
                print("=" * 80)

                print(
                    assistant_message_obj
                    .content
                )

                return

            # =================================================
            # Tool Calls Exist
            # =================================================

            print()
            print(
                "LLM Decision: "
                "Call MCP Tool"
            )

            for tool_call in tool_calls:

                tool_name = (
                    tool_call
                    .function
                    .name
                )

                raw_arguments = (
                    tool_call
                    .function
                    .arguments
                )

                print()
                print("-" * 80)
                print(
                    "Proposed MCP Tool Call"
                )
                print("-" * 80)

                print(
                    f"Tool Name: "
                    f"{tool_name}"
                )

                print(
                    f"Raw Arguments: "
                    f"{raw_arguments}"
                )

                # =============================================
                # Parse arguments
                # =============================================

                try:

                    arguments = (
                        json.loads(
                            raw_arguments
                        )
                    )

                except json.JSONDecodeError as exc:

                    tool_result_content = (
                        json.dumps(
                            {
                                "status":
                                    "argument_parse_error",

                                "error":
                                    str(exc),
                            },
                            ensure_ascii=False,
                        )
                    )

                    messages.append(
                        {
                            "role":
                                "tool",

                            "tool_call_id":
                                tool_call.id,

                            "content":
                                tool_result_content,
                        }
                    )

                    continue

                # =============================================
                # Execute through MCP Client
                # =============================================

                print()
                print(
                    "Calling MCP Client..."
                )

                try:

                    mcp_result = (
                        await mcp_client
                        .call_tool(
                            tool_name,
                            arguments,
                        )
                    )

                    print(
                        f"MCP Is Error: "
                        f"{mcp_result.is_error}"
                    )

                    tool_result_content = (
                        mcp_result_to_json(
                            mcp_result
                        )
                    )

                except Exception as exc:

                    tool_result_content = (
                        json.dumps(
                            {
                                "status":
                                    "mcp_call_error",

                                "error":
                                    str(exc),
                            },
                            ensure_ascii=False,
                        )
                    )

                # =============================================
                # MCP Result -> LLM Tool Message
                # =============================================

                print()
                print(
                    "MCP Result:"
                )

                print(
                    tool_result_content
                )

                messages.append(
                    {
                        "role":
                            "tool",

                        "tool_call_id":
                            tool_call.id,

                        "content":
                            tool_result_content,
                    }
                )

        # ====================================================
        # Max Steps
        # ====================================================

        print()
        print(
            "Agent stopped because "
            "max_steps was reached."
        )


# ============================================================
# 5. Main
# ============================================================

def main() -> None:

    print()
    print("=" * 80)
    print(
        "Traffic Simulation Agent "
        "- DeepSeek + MCP"
    )
    print("=" * 80)

    user_input = input(
        "User: "
    ).strip()

    if not user_input:

        print(
            "User input is empty."
        )

        return

    asyncio.run(
        run_agent(
            user_input
        )
    )


if __name__ == "__main__":
    main()