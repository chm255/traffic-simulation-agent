from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Annotated, Any, Literal

from openai import OpenAI
from typing_extensions import TypedDict

from langgraph.graph import (
    StateGraph,
    START,
    END,
)


# ============================================================
# 1. Project Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_KEY_PATH = PROJECT_ROOT / "api.txt"

CHAT_MODEL_NAME = "deepseek-v4-flash"


# ============================================================
# 2. DeepSeek Client
# ============================================================

api_key = API_KEY_PATH.read_text(
    encoding="utf-8"
).strip()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# ============================================================
# 3. Graph State
# ============================================================

class AgentState(TypedDict):

    # operator.add means:
    #
    # old messages
    # +
    # newly returned messages
    #
    # rather than replacing the whole list.
    messages: Annotated[
        list[dict[str, Any]],
        operator.add,
    ]


# ============================================================
# 4. Real Python Tool
# ============================================================

def multiply(
    a: float,
    b: float,
) -> dict[str, Any]:

    print()
    print(">>> Running Python Tool: multiply")

    return {
        "status": "success",
        "a": a,
        "b": b,
        "result": a * b,
    }


# ============================================================
# 5. Tool Schema
# ============================================================

MULTIPLY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "multiply",
        "description": (
            "Multiply two numbers using a "
            "deterministic Python tool. "
            "Use this tool when the user asks "
            "for multiplication."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "a": {
                    "type": "number",
                },
                "b": {
                    "type": "number",
                },
            },
            "required": [
                "a",
                "b",
            ],
            "additionalProperties": False,
        },
    },
}


TOOLS = [
    MULTIPLY_TOOL_SCHEMA,
]


TOOL_MAP = {
    "multiply": multiply,
}


# ============================================================
# 6. LLM Node
# ============================================================

def llm_node(
    state: AgentState,
) -> dict:

    print()
    print("=" * 60)
    print("Running Node: llm_node")
    print("=" * 60)

    response = client.chat.completions.create(
        model=CHAT_MODEL_NAME,
        messages=state["messages"],
        tools=TOOLS,
        tool_choice="auto",
        extra_body={
            "thinking": {
                "type": "disabled",
            }
        },
    )

    message = (
        response
        .choices[0]
        .message
    )

    # Convert the SDK object into a normal dict
    assistant_message = (
        message.model_dump(
            exclude_none=True
        )
    )

    print(
        "LLM Tool Calls:",
        bool(message.tool_calls),
    )

    return {
        "messages": [
            assistant_message
        ]
    }


# ============================================================
# 7. Conditional Router
# ============================================================

def should_continue(
    state: AgentState,
) -> Literal[
    "tool_node",
    "__end__",
]:

    print()
    print("Running Router: should_continue")

    last_message = state["messages"][-1]

    tool_calls = (
        last_message.get("tool_calls")
    )

    if tool_calls:
        print(
            "Routing Decision: tool_node"
        )

        return "tool_node"

    print(
        "Routing Decision: END"
    )

    return END


# ============================================================
# 8. Tool Node
# ============================================================

def tool_node(
    state: AgentState,
) -> dict:

    print()
    print("=" * 60)
    print("Running Node: tool_node")
    print("=" * 60)

    last_message = state["messages"][-1]

    tool_calls = (
        last_message.get(
            "tool_calls",
            [],
        )
    )

    tool_messages = []

    for tool_call in tool_calls:

        tool_call_id = (
            tool_call["id"]
        )

        function_data = (
            tool_call["function"]
        )

        tool_name = (
            function_data["name"]
        )

        raw_arguments = (
            function_data["arguments"]
        )

        print(
            f"Tool Name: {tool_name}"
        )

        print(
            f"Raw Arguments: "
            f"{raw_arguments}"
        )

        # ----------------------------------------------------
        # Validate tool name
        # ----------------------------------------------------

        if tool_name not in TOOL_MAP:

            result = {
                "status": "tool_error",
                "error": (
                    f"Unknown tool: "
                    f"{tool_name}"
                ),
            }

        else:

            # ------------------------------------------------
            # Parse arguments
            # ------------------------------------------------

            try:
                arguments = json.loads(
                    raw_arguments
                )

                tool_function = (
                    TOOL_MAP[
                        tool_name
                    ]
                )

                result = tool_function(
                    **arguments
                )

            except Exception as exc:

                result = {
                    "status": "tool_error",
                    "error": str(exc),
                }

        print(
            "Tool Result:",
            result,
        )

        # ----------------------------------------------------
        # Tool result must go back to LLM
        # ----------------------------------------------------

        tool_message = {
            "role": "tool",
            "tool_call_id":
                tool_call_id,
            "content": json.dumps(
                result,
                ensure_ascii=False,
            ),
        }

        tool_messages.append(
            tool_message
        )

    return {
        "messages": tool_messages
    }


# ============================================================
# 9. Build LangGraph
# ============================================================

builder = StateGraph(
    AgentState
)


# Register Nodes
builder.add_node(
    "llm_node",
    llm_node,
)

builder.add_node(
    "tool_node",
    tool_node,
)


# START -> LLM
builder.add_edge(
    START,
    "llm_node",
)


# LLM -> Tool OR END
builder.add_conditional_edges(
    "llm_node",
    should_continue,
    {
        "tool_node":
            "tool_node",

        END:
            END,
    },
)


# Tool -> LLM
builder.add_edge(
    "tool_node",
    "llm_node",
)


# Compile
graph = builder.compile()


# ============================================================
# 10. Run
# ============================================================

def main():

    user_input = input(
        "User: "
    ).strip()

    initial_state: AgentState = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful Agent. "
                    "Use tools when needed. "
                    "Do not calculate multiplication "
                    "yourself when the multiply tool "
                    "is appropriate."
                ),
            },
            {
                "role": "user",
                "content": user_input,
            },
        ]
    }

    final_state = graph.invoke(
        initial_state
    )

    print()
    print("=" * 60)
    print("Final Answer")
    print("=" * 60)

    final_message = (
        final_state["messages"][-1]
    )

    print(
        final_message.get(
            "content",
            "",
        )
    )


if __name__ == "__main__":
    main()