from __future__ import annotations

import asyncio
from typing import Any

from mcp import Client

from day09.day09_traffic_mcp_server import (
    mcp,
)

from day09.day09_agent_routing_evaluation import (
    EVAL_CASES,
    evaluate_one_case,
)

from day09.day09_deepseek_mcp_agent import (
    convert_mcp_tools_to_llm_tools,
)


# ============================================================
# 1. Failure Classification
# ============================================================

def classify_failure(
    result: dict[str, Any],
) -> list[str]:

    errors = []

    expected_tool = (
        result["expected_tool"]
    )

    predicted_tool = (
        result["predicted_tool"]
    )

    expected_arguments = (
        result["expected_arguments"]
    )

    predicted_arguments = (
        result["predicted_arguments"]
    )

    # --------------------------------------------------------
    # Case 1:
    # Should NOT call Tool, but did
    # --------------------------------------------------------

    if (
        expected_tool is None
        and predicted_tool is not None
    ):

        errors.append(
            "unexpected_tool_call"
        )

        # In our current experiment cases,
        # Tool arguments were not expected at all.
        # If the model still generated arguments,
        # flag them for manual provenance review.

        if isinstance(
            predicted_arguments,
            dict,
        ):

            errors.append(
                "possible_argument_fabrication"
            )

        return errors

    # --------------------------------------------------------
    # Case 2:
    # Should call Tool, but did not
    # --------------------------------------------------------

    if (
        expected_tool is not None
        and predicted_tool is None
    ):

        errors.append(
            "missed_tool_call"
        )

        return errors

    # --------------------------------------------------------
    # Case 3:
    # Wrong Tool
    # --------------------------------------------------------

    if (
        expected_tool is not None
        and predicted_tool is not None
        and expected_tool
        != predicted_tool
    ):

        errors.append(
            "wrong_tool"
        )

        return errors

    # --------------------------------------------------------
    # Case 4:
    # Correct Tool, wrong arguments
    # --------------------------------------------------------

    if (
        expected_tool
        is not None
        and predicted_tool
        == expected_tool
        and predicted_arguments
        != expected_arguments
    ):

        errors.append(
            "wrong_arguments"
        )

    return errors


# ============================================================
# 2. Root Cause Hint
# ============================================================

def suggest_root_cause(
    errors: list[str],
) -> list[str]:

    hints = []

    if (
        "unexpected_tool_call"
        in errors
    ):

        hints.append(
            "模型在不满足执行条件时"
            "仍然提前调用了 Tool。"
        )

    if (
        "possible_argument_fabrication"
        in errors
    ):

        hints.append(
            "模型可能为了满足 Tool Schema "
            "自行补齐了缺失参数，"
            "需要检查参数来源。"
        )

    if (
        "missed_tool_call"
        in errors
    ):

        hints.append(
            "模型没有识别出用户的执行意图，"
            "可能需要检查 Prompt 或 Tool Description。"
        )

    if (
        "wrong_tool"
        in errors
    ):

        hints.append(
            "模型选择了错误能力，"
            "需要检查 Tool 描述是否容易混淆。"
        )

    if (
        "wrong_arguments"
        in errors
    ):

        hints.append(
            "模型选择了正确 Tool，"
            "但参数抽取或映射出现错误。"
        )

    return hints


# ============================================================
# 3. Main
# ============================================================

async def main() -> None:

    print()
    print("=" * 80)
    print(
        "Traffic Agent Error Analysis"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # Discover MCP Tools
    # --------------------------------------------------------

    async with Client(mcp) as client:

        tools_result = (
            await client.list_tools()
        )

        llm_tools = (
            convert_mcp_tools_to_llm_tools(
                tools_result.tools
            )
        )

    # --------------------------------------------------------
    # Run Evaluation Again
    # --------------------------------------------------------

    results = []

    for case in EVAL_CASES:

        result = evaluate_one_case(
            case,
            llm_tools,
        )

        results.append(
            result
        )

    # --------------------------------------------------------
    # Analyze Failures
    # --------------------------------------------------------

    failed_results = [
        result
        for result in results
        if not result["passed"]
    ]

    print()
    print("=" * 80)
    print(
        "Failure Analysis"
    )
    print("=" * 80)

    if not failed_results:

        print(
            "No failed cases."
        )

        return

    for result in failed_results:

        errors = classify_failure(
            result
        )

        root_causes = (
            suggest_root_cause(
                errors
            )
        )

        print()
        print("-" * 80)

        print(
            f"Case: "
            f"{result['id']}"
        )

        print(
            f"User: "
            f"{result['user_input']}"
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
            f"Predicted Arguments: "
            f"{result['predicted_arguments']}"
        )

        print()

        print(
            "Failure Types:"
        )

        for error in errors:

            print(
                f"- {error}"
            )

        print()

        print(
            "Root Cause Hints:"
        )

        for cause in root_causes:

            print(
                f"- {cause}"
            )

        if result[
            "assistant_content"
        ]:

            print()
            print(
                "Assistant Reasoning / Response:"
            )

            print(
                result[
                    "assistant_content"
                ]
            )


if __name__ == "__main__":

    asyncio.run(
        main()
    )