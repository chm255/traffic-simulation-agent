from __future__ import annotations

import json
import operator
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

from langgraph.graph import (
    StateGraph,
    START,
    END,
)


# ============================================================
# 1. Reuse Day 6 Agent Capabilities
# ============================================================

from day06.day06_rag_tool_agent import (
    client,
    CHAT_MODEL_NAME,
    TOOLS,
    TOOL_MAP,
    SYSTEM_PROMPT,
)


# ============================================================
# 2. LangGraph State
# ============================================================

class TrafficAgentState(TypedDict):
    """
    Shared state of the Traffic Simulation Agent.

    messages:
        Complete working conversation used by the Agent.

    operator.add:
        New messages returned by Nodes are appended
        to existing messages rather than replacing them.
    """

    messages: Annotated[
        list[dict[str, Any]],
        operator.add,
    ]


# ============================================================
# 3. LLM Node
# ============================================================

def llm_node(
    state: TrafficAgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print("Running Node: llm_node")
    print("=" * 80)

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

    assistant_message = (
        message.model_dump(
            exclude_none=True
        )
    )

    print(
        "LLM Tool Calls:",
        bool(message.tool_calls),
    )

    if message.tool_calls:

        for tool_call in message.tool_calls:

            print(
                f"Proposed Tool: "
                f"{tool_call.function.name}"
            )

            print(
                f"Arguments: "
                f"{tool_call.function.arguments}"
            )

    return {
        "messages": [
            assistant_message
        ]
    }


# ============================================================
# 4. Conditional Router
# ============================================================

def should_continue(
    state: TrafficAgentState,
) -> Literal[
    "tool_node",
    "__end__",
]:

    print()
    print("Running Router: should_continue")

    last_message = (
        state["messages"][-1]
    )

    tool_calls = (
        last_message.get(
            "tool_calls"
        )
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
# 5. Tool Node
# ============================================================

def tool_node(
    state: TrafficAgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print("Running Node: tool_node")
    print("=" * 80)

    last_message = (
        state["messages"][-1]
    )

    tool_calls = (
        last_message.get(
            "tool_calls",
            [],
        )
    )

    tool_messages = []

    # ========================================================
    # Support multiple Tool Calls in one LLM step
    # ========================================================

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

        print()
        print("-" * 80)
        print("Executing Tool")
        print("-" * 80)

        print(
            f"Tool Name: {tool_name}"
        )

        print(
            f"Raw Arguments: "
            f"{raw_arguments}"
        )

        # ----------------------------------------------------
        # 5.1 Tool existence validation
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
            # 5.2 JSON argument parsing
            # ------------------------------------------------

            try:

                arguments = json.loads(
                    raw_arguments
                )

                if not isinstance(
                    arguments,
                    dict,
                ):
                    raise ValueError(
                        "Tool arguments must "
                        "be a JSON object."
                    )

                # --------------------------------------------
                # 5.3 Find real Python Tool
                # --------------------------------------------

                tool_function = (
                    TOOL_MAP[
                        tool_name
                    ]
                )

                # --------------------------------------------
                # 5.4 Execute Tool
                # --------------------------------------------

                result = (
                    tool_function(
                        **arguments
                    )
                )

            except json.JSONDecodeError as exc:

                result = {
                    "status":
                        "argument_parse_error",
                    "error":
                        str(exc),
                }

            except TypeError as exc:

                result = {
                    "status":
                        "argument_validation_error",
                    "error":
                        str(exc),
                }

            except Exception as exc:

                result = {
                    "status":
                        "tool_execution_error",
                    "error":
                        str(exc),
                }

        # ----------------------------------------------------
        # Print Observation
        # ----------------------------------------------------

        print()
        print("Tool Result:")

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        # ----------------------------------------------------
        # 5.5 Observation -> LLM
        # ----------------------------------------------------

        tool_message = {
            "role": "tool",
            "tool_call_id":
                tool_call_id,
            "content":
                json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str,
                ),
        }

        tool_messages.append(
            tool_message
        )

    return {
        "messages": tool_messages
    }


# ============================================================
# 6. Build Traffic Simulation Agent Graph
# ============================================================

builder = StateGraph(
    TrafficAgentState
)


# ------------------------------------------------------------
# Nodes
# ------------------------------------------------------------

builder.add_node(
    "llm_node",
    llm_node,
)

builder.add_node(
    "tool_node",
    tool_node,
)


# ------------------------------------------------------------
# START -> LLM
# ------------------------------------------------------------

builder.add_edge(
    START,
    "llm_node",
)


# ------------------------------------------------------------
# LLM
#   ├─ Tool Call -> Tool Node
#   └─ No Tool   -> END
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Tool -> LLM
#
# This Edge creates the Agent Loop.
# ------------------------------------------------------------

builder.add_edge(
    "tool_node",
    "llm_node",
)


# ============================================================
# 7. Compile Graph
# ============================================================

graph = builder.compile()


# ============================================================
# 8. Run Agent
# ============================================================

def run_agent(
    user_input: str,
) -> TrafficAgentState:

    initial_state: TrafficAgentState = {
        "messages": [
            {
                "role": "system",
                "content":
                    SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content":
                    user_input,
            },
        ]
    }

    final_state = graph.invoke(
        initial_state
    )

    return final_state


# ============================================================
# 9. Main
# ============================================================

def main():

    print()
    print("=" * 80)
    print(
        "Traffic Simulation Agent V3"
    )
    print("=" * 80)

    print(
        "Orchestration: LangGraph"
    )

    print(
        "Capabilities:"
    )

    print(
        "- Project Knowledge RAG"
    )

    print(
        "- Real SUMO Experiment Tool"
    )

    print()

    user_input = input(
        "User: "
    ).strip()

    if not user_input:

        print(
            "User input is empty."
        )

        return

    final_state = run_agent(
        user_input
    )

    final_message = (
        final_state[
            "messages"
        ][-1]
    )

    print()
    print("=" * 80)
    print("Final Answer")
    print("=" * 80)

    print(
        final_message.get(
            "content",
            "",
        )
    )


if __name__ == "__main__":
    main()