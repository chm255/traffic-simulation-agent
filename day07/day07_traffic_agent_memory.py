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

from langgraph.checkpoint.memory import (
    InMemorySaver,
)


# ============================================================
# 1. Reuse Day 6 Capabilities
# ============================================================

from day06.day06_rag_tool_agent import (
    client,
    CHAT_MODEL_NAME,
    TOOLS,
    TOOL_MAP,
    SYSTEM_PROMPT,
)


# ============================================================
# 2. Graph State
# ============================================================

class TrafficAgentState(TypedDict):

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

    print(
        f"Current message count: "
        f"{len(state['messages'])}"
    )

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
# 4. Router
# ============================================================

def should_continue(
    state: TrafficAgentState,
) -> Literal[
    "tool_node",
    "__end__",
]:

    print()
    print(
        "Running Router: "
        "should_continue"
    )

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
        # Tool validation
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

                tool_function = (
                    TOOL_MAP[
                        tool_name
                    ]
                )

                result = tool_function(
                    **arguments
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
# 6. Build Graph
# ============================================================

builder = StateGraph(
    TrafficAgentState
)

builder.add_node(
    "llm_node",
    llm_node,
)

builder.add_node(
    "tool_node",
    tool_node,
)

builder.add_edge(
    START,
    "llm_node",
)

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

builder.add_edge(
    "tool_node",
    "llm_node",
)


# ============================================================
# 7. NEW: Checkpointer
# ============================================================

checkpointer = InMemorySaver()


graph = builder.compile(
    checkpointer=checkpointer
)


# ============================================================
# 8. Thread Configuration
# ============================================================

THREAD_ID = "traffic-agent-demo"


GRAPH_CONFIG = {
    "configurable": {
        "thread_id":
            THREAD_ID
    }
}


# ============================================================
# 9. First Turn
# ============================================================

def run_first_turn(
    user_input: str,
) -> TrafficAgentState:

    input_state: TrafficAgentState = {
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

    return graph.invoke(
        input_state,
        config=GRAPH_CONFIG,
    )


# ============================================================
# 10. Following Turns
# ============================================================

def run_following_turn(
    user_input: str,
) -> TrafficAgentState:

    # IMPORTANT:
    #
    # We only provide the NEW user message.
    #
    # Previous messages will be recovered from
    # the checkpoint associated with THREAD_ID.

    input_state: TrafficAgentState = {
        "messages": [
            {
                "role": "user",
                "content":
                    user_input,
            }
        ]
    }

    return graph.invoke(
        input_state,
        config=GRAPH_CONFIG,
    )


# ============================================================
# 11. Interactive Multi-turn Conversation
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
        "Checkpoint: InMemorySaver"
    )

    print(
        f"Thread ID: {THREAD_ID}"
    )

    print()

    print(
        "Type 'exit' to stop."
    )

    print()

    first_turn = True

    while True:

        user_input = input(
            "User: "
        ).strip()

        if user_input.lower() == "exit":

            print(
                "Conversation ended."
            )

            break

        if not user_input:

            continue

        # ----------------------------------------------------
        # First turn includes System Prompt
        # ----------------------------------------------------

        if first_turn:

            final_state = run_first_turn(
                user_input
            )

            first_turn = False

        # ----------------------------------------------------
        # Following turns only add new User Message
        # ----------------------------------------------------

        else:

            final_state = (
                run_following_turn(
                    user_input
                )
            )

        final_message = (
            final_state[
                "messages"
            ][-1]
        )

        print()
        print("=" * 80)
        print("Assistant")
        print("=" * 80)

        print(
            final_message.get(
                "content",
                "",
            )
        )

        print()


if __name__ == "__main__":
    main()