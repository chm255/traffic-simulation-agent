from __future__ import annotations

import json
import operator

from typing import (
    Annotated,
    Any,
    Literal,
)

from typing_extensions import TypedDict

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.checkpoint.memory import (
    InMemorySaver,
)

from langgraph.types import (
    interrupt,
    Command,
)


# ============================================================
# 1. Reuse Day 6-8 Agent Capabilities
# ============================================================

from day06.day06_rag_tool_agent import (
    client,
    CHAT_MODEL_NAME,
    TOOLS,
    TOOL_MAP,
    SYSTEM_PROMPT,
)
from day08.day08_context_management import (
    build_llm_context,
)
MAX_RECENT_MESSAGES = 10
# ============================================================
# 2. Tool Safety Policy
# ============================================================

from day08.day08_tool_policy import (
    AUTO,
    APPROVAL,
    DENY,
    get_tool_policy,
)

# ============================================================
# 3. Graph State
# ============================================================

class TrafficAgentState(TypedDict):

    messages: Annotated[
        list[dict[str, Any]],
        operator.add,
    ]

    approval_decision: bool | None


# ============================================================
# 4. LLM Node
# ============================================================

def llm_node(
    state: TrafficAgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print("Running Node: llm_node")
    print("=" * 80)

    # ========================================================
    # Build LLM Context
    # ========================================================

    full_messages = (
        state["messages"]
    )

    llm_context = (
        build_llm_context(
            full_messages,
            max_recent_messages=
                MAX_RECENT_MESSAGES,
        )
    )

    print(
        f"Full State Messages: "
        f"{len(full_messages)}"
    )

    print(
        f"LLM Context Messages: "
        f"{len(llm_context)}"
    )

    # ========================================================
    # Call LLM
    # ========================================================

    response = client.chat.completions.create(
        model=CHAT_MODEL_NAME,
        messages=llm_context,
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
# 5. LLM Router
# ============================================================

def route_after_llm(
    state: TrafficAgentState,
) -> Literal[
    "tool_node",
    "approval_node",
    "denied_tool_node",
    "__end__",
]:

    print()
    print(
        "Running Router: "
        "route_after_llm"
    )

    last_message = (
        state["messages"][-1]
    )

    tool_calls = last_message.get(
        "tool_calls",
        [],
    )

    # ========================================================
    # 1. No Tool Call
    # ========================================================

    if not tool_calls:

        print(
            "Routing Decision: END"
        )

        return END

    permissions = []

    # ========================================================
    # 2. Evaluate Tool Policies
    # ========================================================

    for tool_call in tool_calls:

        tool_name = (
            tool_call[
                "function"
            ][
                "name"
            ]
        )

        policy = get_tool_policy(
            tool_name
        )

        permission = (
            policy["permission"]
        )

        permissions.append(
            permission
        )

        print()
        print(
            f"Tool: {tool_name}"
        )

        print(
            f"Category: "
            f"{policy['category']}"
        )

        print(
            f"Permission: "
            f"{permission}"
        )

        print(
            f"Reason: "
            f"{policy['reason']}"
        )

    # ========================================================
    # 3. Permission Priority
    #
    # DENY > APPROVAL > AUTO
    # ========================================================

    if DENY in permissions:

        print()
        print(
            "Routing Decision: "
            "denied_tool_node"
        )

        return "denied_tool_node"

    if APPROVAL in permissions:

        print()
        print(
            "Routing Decision: "
            "approval_node"
        )

        return "approval_node"

    print()
    print(
        "Routing Decision: "
        "tool_node"
    )

    return "tool_node"


# ============================================================
# 6. Human Approval Node
# ============================================================

def approval_node(
    state: TrafficAgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print("Running Node: approval_node")
    print("=" * 80)

    last_message = (
        state["messages"][-1]
    )

    tool_calls = last_message.get(
        "tool_calls",
        [],
    )

    sensitive_actions = []

    for tool_call in tool_calls:

        tool_name = (
            tool_call[
                "function"
            ][
                "name"
            ]
        )
        policy = get_tool_policy(
            tool_name
        )

        if (
            policy["permission"]
            == APPROVAL
        ):

            raw_arguments = (
                tool_call[
                    "function"
                ][
                    "arguments"
                ]
            )

            try:

                arguments = json.loads(
                    raw_arguments
                )

            except Exception:

                arguments = (
                    raw_arguments
                )

            sensitive_actions.append(
                {
                    "tool":
                    tool_name,

                "category":
                    policy["category"],

                "permission":
                    policy["permission"],

                "reason":
                    policy["reason"],

                "arguments":
                    arguments,
                }
            )

    print(
        "Pending Sensitive Actions:"
    )

    print(
        json.dumps(
            sensitive_actions,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # No external side effect before interrupt().
    # --------------------------------------------------------

    human_decision = interrupt(
        {
            "type":
                "tool_approval_request",

            "message":
                "检测到需要人工审批的工具调用。",

            "actions":
                sensitive_actions,
        }
    )

    print()
    print(
        "Graph resumed."
    )

    print(
        "Human Approval Decision:",
        human_decision,
    )

    return {
        "approval_decision":
            bool(human_decision)
    }


# ============================================================
# 7. Router after Approval
# ============================================================

def route_after_approval(
    state: TrafficAgentState,
) -> Literal[
    "tool_node",
    "reject_tool_node",
]:

    print()
    print(
        "Running Router: "
        "route_after_approval"
    )

    if state["approval_decision"]:

        print(
            "Routing Decision: "
            "tool_node"
        )

        return "tool_node"

    print(
        "Routing Decision: "
        "reject_tool_node"
    )

    return "reject_tool_node"


# ============================================================
# 8. Execute One Tool
# ============================================================

def execute_one_tool(
    tool_name: str,
    raw_arguments: str,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # Tool existence validation
    # --------------------------------------------------------

    if tool_name not in TOOL_MAP:

        return {
            "status":
                "tool_error",

            "error":
                f"Unknown tool: {tool_name}",
        }

    # --------------------------------------------------------
    # Parse JSON arguments
    # --------------------------------------------------------

    try:

        arguments = json.loads(
            raw_arguments
        )

    except json.JSONDecodeError as exc:

        return {
            "status":
                "argument_parse_error",

            "error":
                str(exc),
        }

    if not isinstance(
        arguments,
        dict,
    ):

        return {
            "status":
                "argument_validation_error",

            "error":
                "Tool arguments must "
                "be a JSON object.",
        }

    # --------------------------------------------------------
    # Execute real Python Tool
    # --------------------------------------------------------

    try:

        tool_function = (
            TOOL_MAP[
                tool_name
            ]
        )

        return tool_function(
            **arguments
        )

    except TypeError as exc:

        return {
            "status":
                "argument_validation_error",

            "error":
                str(exc),
        }

    except Exception as exc:

        return {
            "status":
                "tool_execution_error",

            "error":
                str(exc),
        }


# ============================================================
# 9. Normal Tool Node
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

    tool_calls = last_message.get(
        "tool_calls",
        [],
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
            function_data[
                "arguments"
            ]
        )

        print()
        print("-" * 80)
        print("Executing Tool")
        print("-" * 80)

        print(
            f"Tool Name: "
            f"{tool_name}"
        )

        print(
            f"Raw Arguments: "
            f"{raw_arguments}"
        )

        result = execute_one_tool(
            tool_name,
            raw_arguments,
        )

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

        tool_messages.append(
            {
                "role":
                    "tool",

                "tool_call_id":
                    tool_call_id,

                "content":
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ),
            }
        )

    return {
        "messages":
            tool_messages,

        "approval_decision":
            None,
    }


# ============================================================
# 10. Rejected Tool Node
# ============================================================

def reject_tool_node(
    state: TrafficAgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print(
        "Running Node: reject_tool_node"
    )
    print("=" * 80)

    last_message = (
        state["messages"][-1]
    )

    tool_calls = last_message.get(
        "tool_calls",
        [],
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
            function_data[
                "arguments"
            ]
        )

        # ----------------------------------------------------
        # Sensitive Tool -> DO NOT EXECUTE
        # ----------------------------------------------------
        policy = get_tool_policy(
            tool_name
        )

        permission = (
            policy["permission"]
        )


        if permission == APPROVAL:

            print()
            print(
                f"Tool Rejected by Human: "
                f"{tool_name}"
            )

            result = {
                "status":
                    "rejected_by_human",

                "tool":
                    tool_name,

                "permission":
                    permission,

                "message":
                    "Human approval was denied.",
            }


        elif permission == AUTO:

            print()
            print(
                f"Executing Auto Tool: "
                f"{tool_name}"
            )

            result = execute_one_tool(
                tool_name,
                raw_arguments,
            )


        else:

            result = {
                "status":
                    "denied_by_policy",

                "tool":
                    tool_name,

                "permission":
                    permission,

                "message":
                    "Tool execution is denied "
                    "by runtime policy.",
            }

        tool_messages.append(
            {
                "role":
                    "tool",

                "tool_call_id":
                    tool_call_id,

                "content":
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ),
            }
        )

    return {
        "messages":
            tool_messages,

        "approval_decision":
            None,
    }

def denied_tool_node(
    state: TrafficAgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print(
        "Running Node: denied_tool_node"
    )
    print("=" * 80)

    last_message = (
        state["messages"][-1]
    )

    tool_calls = last_message.get(
        "tool_calls",
        [],
    )

    tool_messages = []

    for tool_call in tool_calls:

        tool_call_id = (
            tool_call["id"]
        )

        tool_name = (
            tool_call[
                "function"
            ][
                "name"
            ]
        )

        policy = get_tool_policy(
            tool_name
        )

        print()
        print(
            f"Tool Blocked: "
            f"{tool_name}"
        )

        print(
            f"Permission: "
            f"{policy['permission']}"
        )

        print(
            f"Reason: "
            f"{policy['reason']}"
        )

        result = {
            "status":
                "denied_by_policy",

            "tool":
                tool_name,

            "category":
                policy["category"],

            "permission":
                policy["permission"],

            "reason":
                policy["reason"],

            "message":
                "Tool execution was blocked "
                "by runtime permission policy.",
        }

        tool_messages.append(
            {
                "role":
                    "tool",

                "tool_call_id":
                    tool_call_id,

                "content":
                    json.dumps(
                        result,
                        ensure_ascii=False,
                    ),
            }
        )

    return {
        "messages":
            tool_messages,

        "approval_decision":
            None,
    }
# ============================================================
# 11. Build Graph
# ============================================================

builder = StateGraph(
    TrafficAgentState
)


builder.add_node(
    "llm_node",
    llm_node,
)

builder.add_node(
    "approval_node",
    approval_node,
)

builder.add_node(
    "tool_node",
    tool_node,
)

builder.add_node(
    "reject_tool_node",
    reject_tool_node,
)

builder.add_node(
    "denied_tool_node",
    denied_tool_node,
)

# START -> LLM

builder.add_edge(
    START,
    "llm_node",
)


# LLM
# ├─ END
# ├─ Safe Tool
# ├─ Approval
# └─ Denied Tool

builder.add_conditional_edges(
    "llm_node",
    route_after_llm,
    {
        "tool_node":
            "tool_node",

        "approval_node":
            "approval_node",

        "denied_tool_node":
            "denied_tool_node",

        END:
            END,
    },
)

# Approval
# ├─ Approve -> Tool
# └─ Reject  -> Reject Tool

builder.add_conditional_edges(
    "approval_node",
    route_after_approval,
    {
        "tool_node":
            "tool_node",

        "reject_tool_node":
            "reject_tool_node",
    },
)


# Both paths return to LLM

builder.add_edge(
    "tool_node",
    "llm_node",
)

builder.add_edge(
    "reject_tool_node",
    "llm_node",
)

builder.add_edge(
    "denied_tool_node",
    "llm_node",
)

# ============================================================
# 12. Checkpointer
# ============================================================

checkpointer = InMemorySaver()


graph = builder.compile(
    checkpointer=checkpointer
)


# ============================================================
# 13. Thread
# ============================================================

GRAPH_CONFIG = {
    "configurable": {
        "thread_id":
            "day08-traffic-approval"
    }
}


# ============================================================
# 14. Run Agent
# ============================================================

def run_agent(
    user_input: str,
) -> TrafficAgentState:

    initial_state: TrafficAgentState = {
        "messages": [
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
        ],

        "approval_decision":
            None,
    }

    result = graph.invoke(
        initial_state,
        config=GRAPH_CONFIG,
    )

    # ========================================================
    # Handle any Human Interrupt
    # ========================================================

    while True:

        interrupts = result.get(
            "__interrupt__",
            (),
        )

        if not interrupts:
            break

        interrupt_data = (
            interrupts[0].value
        )

        print()
        print("=" * 80)
        print(
            "HUMAN APPROVAL REQUIRED"
        )
        print("=" * 80)

        print(
            json.dumps(
                interrupt_data,
                ensure_ascii=False,
                indent=2,
            )
        )

        print()

        human_input = input(
            "Approve sensitive tool? "
            "(yes/no): "
        ).strip().lower()

        approved = (
            human_input
            in {
                "yes",
                "y",
                "是",
                "批准",
            }
        )

        result = graph.invoke(
            Command(
                resume=approved
            ),
            config=GRAPH_CONFIG,
        )

    return result


# ============================================================
# 15. Main
# ============================================================

def main():

    print()
    print("=" * 80)
    print(
        "Traffic Simulation Agent "
        "V3 + Human Approval"
    )
    print("=" * 80)

    print(
        "Safe Tool:"
    )

    print(
        "- search_project_knowledge"
    )

    print()

    print(
        "Approval Required Tool:"
    )

    print(
        "- run_sumo_experiment"
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