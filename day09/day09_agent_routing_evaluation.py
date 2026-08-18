from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import Client

from day09.day09_traffic_mcp_server import (
    mcp,
)

from day09.day09_deepseek_mcp_agent import (
    deepseek_client,
    CHAT_MODEL_NAME,
    SYSTEM_PROMPT,
    convert_mcp_tools_to_llm_tools,
)


# ============================================================
# 1. Evaluation Cases
# ============================================================

EVAL_CASES = [

    {
        "id": "case_01",
        "user_input":
            "你好，请简单介绍一下你自己。",

        "expected_tool":
            None,

        "expected_arguments":
            None,
    },

    {
        "id": "case_02",
        "user_input":
            "使用 cross 场景，"
            "seed=42，运行300秒。",

        "expected_tool":
            "run_sumo_experiment",

        "expected_arguments": {
            "scenario": "cross",
            "seed": 42,
            "duration": 300,
        },
    },

    {
        "id": "case_03",
        "user_input":
            "请运行 cross 场景，"
            "seed=7，duration=120。",

        "expected_tool":
            "run_sumo_experiment",

        "expected_arguments": {
            "scenario": "cross",
            "seed": 7,
            "duration": 120,
        },
    },

    {
        "id": "case_04",
        "user_input":
            "使用 cross 场景运行一个实验。",

        # Missing seed and duration.
        # Agent should NOT invent them.
        "expected_tool":
            None,

        "expected_arguments":
            None,
    },

    {
        "id": "case_05",
        "user_input":
            "seed=99，运行300秒。",

        # Missing scenario.
        "expected_tool":
            None,

        "expected_arguments":
            None,
    },

    {
        "id": "case_06",
        "user_input":
            "throughput 是什么意思？",

        # Current MCP server only exposes SUMO execution.
        # Asking a definition should not launch SUMO.
        "expected_tool":
            None,

        "expected_arguments":
            None,
    },
]


# ============================================================
# 2. Run One Planner Evaluation
# ============================================================

def evaluate_one_case(
    case: dict[str, Any],
    llm_tools: list[dict[str, Any]],
) -> dict[str, Any]:

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
                case["user_input"],
        },
    ]

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

    message = (
        response
        .choices[0]
        .message
    )

    # ========================================================
    # Predicted Tool
    # ========================================================

    if not message.tool_calls:

        predicted_tool = None
        predicted_arguments = None

    else:

        # For this basic evaluation,
        # only inspect the first Tool Call.

        first_tool_call = (
            message.tool_calls[0]
        )

        predicted_tool = (
            first_tool_call
            .function
            .name
        )

        try:

            predicted_arguments = (
                json.loads(
                    first_tool_call
                    .function
                    .arguments
                )
            )

        except json.JSONDecodeError:

            predicted_arguments = (
                "__INVALID_JSON__"
            )

    # ========================================================
    # Deterministic Evaluation
    # ========================================================

    expected_tool = (
        case["expected_tool"]
    )

    expected_arguments = (
        case["expected_arguments"]
    )

    tool_correct = (
        predicted_tool
        == expected_tool
    )

    arguments_correct = True

    if expected_tool is not None:

        arguments_correct = (
            predicted_arguments
            == expected_arguments
        )

    passed = (
        tool_correct
        and arguments_correct
    )

    return {
        "id":
            case["id"],

        "user_input":
            case["user_input"],

        "expected_tool":
            expected_tool,

        "predicted_tool":
            predicted_tool,

        "expected_arguments":
            expected_arguments,

        "predicted_arguments":
            predicted_arguments,

        "tool_correct":
            tool_correct,

        "arguments_correct":
            arguments_correct,

        "passed":
            passed,

        "assistant_content":
            message.content,
    }


# ============================================================
# 3. Main Evaluation
# ============================================================

async def main() -> None:

    print()
    print("=" * 80)
    print(
        "Traffic Agent Routing Evaluation"
    )
    print("=" * 80)

    # ========================================================
    # Discover MCP Tools
    # ========================================================

    async with Client(mcp) as mcp_client:

        tools_result = (
            await mcp_client.list_tools()
        )

        llm_tools = (
            convert_mcp_tools_to_llm_tools(
                tools_result.tools
            )
        )

    # ========================================================
    # Run Dataset
    # ========================================================

    results = []

    for case in EVAL_CASES:

        print()
        print("=" * 80)
        print(
            f"Running {case['id']}"
        )
        print("=" * 80)

        print(
            f"User: "
            f"{case['user_input']}"
        )

        result = evaluate_one_case(
            case,
            llm_tools,
        )

        results.append(
            result
        )

        print()
        print(
            f"Expected Tool: "
            f"{result['expected_tool']}"
        )

        print(
            f"Predicted Tool: "
            f"{result['predicted_tool']}"
        )

        print(
            f"Expected Arguments: "
            f"{result['expected_arguments']}"
        )

        print(
            f"Predicted Arguments: "
            f"{result['predicted_arguments']}"
        )

        print(
            f"Tool Correct: "
            f"{result['tool_correct']}"
        )

        print(
            f"Arguments Correct: "
            f"{result['arguments_correct']}"
        )

        print(
            f"PASS: "
            f"{result['passed']}"
        )

        if result[
            "assistant_content"
        ]:

            print(
                "Assistant Response:"
            )

            print(
                result[
                    "assistant_content"
                ]
            )

    # ========================================================
    # Summary
    # ========================================================

    total = len(results)

    passed_count = sum(
        result["passed"]
        for result in results
    )

    pass_rate = (
        passed_count
        /
        total
    )

    tool_accuracy = (
        sum(
            result["tool_correct"]
            for result in results
        )
        /
        total
    )

    argument_cases = [
        result
        for result in results
        if (
            result[
                "expected_tool"
            ]
            is not None
        )
    ]

    argument_accuracy = (
        sum(
            result[
                "arguments_correct"
            ]
            for result in argument_cases
        )
        /
        len(argument_cases)
    )

    print()
    print("=" * 80)
    print(
        "Evaluation Summary"
    )
    print("=" * 80)

    print(
        f"Total Cases: "
        f"{total}"
    )

    print(
        f"Passed Cases: "
        f"{passed_count}"
    )

    print(
        f"Pass Rate: "
        f"{pass_rate:.2%}"
    )

    print(
        f"Tool Selection Accuracy: "
        f"{tool_accuracy:.2%}"
    )

    print(
        f"Argument Accuracy: "
        f"{argument_accuracy:.2%}"
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )