from __future__ import annotations

import asyncio
import json
import operator
import sqlite3
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import (
    START,
    END,
    StateGraph,
)

from langgraph.types import (
    Command,
    interrupt,
)

from langgraph.checkpoint.sqlite import (
    SqliteSaver,
)

from mcp import Client


# ============================================================
# Existing Project Components
# ============================================================

from day06.day06_rag_tool_agent import (
    client as deepseek_client,
    CHAT_MODEL_NAME,
)

from day08.day08_context_management import (
    build_llm_context,
)

from day08.day08_tool_policy import (
    AUTO,
    APPROVAL,
    DENY,
    get_tool_policy,
)

from day09.day09_deepseek_mcp_agent import (
    convert_mcp_tools_to_llm_tools,
    mcp_result_to_json,
)

from day10.day10_final_mcp_server import (
    mcp,
)


# ============================================================
# 1. System Prompt
# ============================================================

SYSTEM_PROMPT = """
You are the final Traffic Simulation Agent.

You have access to project capabilities through MCP tools.

General rules:

1. Use search_project_knowledge when the user asks about
   project-specific metric definitions, scenarios,
   experiment rules, or knowledge stored in the local
   Traffic Simulation Agent knowledge base.

2. Do not rely on general model knowledge when a
   project-specific definition is available through
   search_project_knowledge.

3. Use run_sumo_experiment only when the user explicitly
   asks to run a simulation AND all three required parameters
   have been explicitly provided:
   - scenario
   - seed
   - duration

4. If any SUMO parameter is missing:
   - DO NOT call run_sumo_experiment.
   - DO NOT invent a value.
   - DO NOT infer a default value.
   - Ask the user for the missing parameter.

5. Tool calls are proposals. Runtime validation,
   permission policy, and human approval determine
   whether a tool is actually executed.

6. Never claim that a simulation was executed unless
   a tool result confirms successful execution.

7. Only report simulation metrics returned by the tool.

8. Distinguish observed simulation results from
   causal explanation or prediction.
"""


# ============================================================
# 2. LangGraph State
# ============================================================

class AgentState(TypedDict, total=False):

    messages: Annotated[
        list[dict[str, Any]],
        operator.add,
    ]

    approval_decision: bool | None


# ============================================================
# 3. Runtime MCP Tool Discovery
# ============================================================

async def discover_mcp_tools_async() -> list[dict[str, Any]]:

    async with Client(mcp) as client:

        tools_result = (
            await client.list_tools()
        )

        return (
            convert_mcp_tools_to_llm_tools(
                tools_result.tools
            )
        )


def discover_mcp_tools() -> list[dict[str, Any]]:

    return asyncio.run(
        discover_mcp_tools_async()
    )


# MCP becomes the capability source.
LLM_TOOLS = discover_mcp_tools()


# ============================================================
# 4. Helper: Last Tool Calls
# ============================================================

def get_last_tool_calls(
    state: AgentState,
) -> list[dict[str, Any]]:

    messages = state.get(
        "messages",
        [],
    )

    if not messages:
        return []

    last_message = messages[-1]

    return (
        last_message.get(
            "tool_calls",
            [],
        )
        or []
    )


# ============================================================
# 5. Runtime Validation
# ============================================================

def validate_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[bool, str]:

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    if tool_name == "search_project_knowledge":

        query = arguments.get(
            "query"
        )

        if not isinstance(
            query,
            str,
        ):

            return (
                False,
                "query must be a string",
            )

        if not query.strip():

            return (
                False,
                "query cannot be empty",
            )

        return (
            True,
            "valid",
        )

    # --------------------------------------------------------
    # SUMO
    # --------------------------------------------------------

    if tool_name == "run_sumo_experiment":

        scenario = arguments.get(
            "scenario"
        )

        seed = arguments.get(
            "seed"
        )

        duration = arguments.get(
            "duration"
        )

        if not isinstance(
            scenario,
            str,
        ):

            return (
                False,
                "scenario must be a string",
            )

        if not scenario.strip():

            return (
                False,
                "scenario cannot be empty",
            )

        # Important:
        # bool is a subclass of int in Python.
        if (
            not isinstance(
                seed,
                int,
            )
            or isinstance(
                seed,
                bool,
            )
        ):

            return (
                False,
                "seed must be an integer",
            )

        if (
            not isinstance(
                duration,
                int,
            )
            or isinstance(
                duration,
                bool,
            )
        ):

            return (
                False,
                "duration must be an integer",
            )

        if duration <= 0:

            return (
                False,
                "duration must be positive",
            )

        return (
            True,
            "valid",
        )

    # --------------------------------------------------------
    # Unknown Tool
    # --------------------------------------------------------

    return (
        False,
        f"unknown tool: {tool_name}",
    )


# ============================================================
# 6. LLM Node
# ============================================================

def llm_node(
    state: AgentState,
) -> dict[str, Any]:

    full_messages = (
        state["messages"]
    )

    # --------------------------------------------------------
    # Context Management
    # --------------------------------------------------------

    llm_context = (
        build_llm_context(
            full_messages,
            max_recent_messages=12,
        )
    )

    print()
    print("=" * 80)
    print("LLM Node")
    print("=" * 80)

    print(
        f"Full Messages: "
        f"{len(full_messages)}"
    )

    print(
        f"LLM Context: "
        f"{len(llm_context)}"
    )

    response = (
        deepseek_client
        .chat
        .completions
        .create(
            model=
                CHAT_MODEL_NAME,

            messages=
                llm_context,

            tools=
                LLM_TOOLS,

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

    message_object = (
        response
        .choices[0]
        .message
    )

    message = (
        message_object
        .model_dump(
            exclude_none=True
        )
    )

    return {
        "messages": [
            message
        ]
    }


# ============================================================
# 7. Router After LLM
# ============================================================

def route_after_llm(
    state: AgentState,
) -> str:

    tool_calls = (
        get_last_tool_calls(
            state
        )
    )

    # --------------------------------------------------------
    # No Tool Call
    # --------------------------------------------------------

    if not tool_calls:

        print()
        print(
            "Router: no tool call -> END"
        )

        return "end"

    print()
    print(
        f"Router: "
        f"{len(tool_calls)} tool call(s)"
    )

    # --------------------------------------------------------
    # Check Permission Policies
    # --------------------------------------------------------

    has_approval_tool = False

    for tool_call in tool_calls:

        tool_name = (
            tool_call[
                "function"
            ][
                "name"
            ]
        )

        policy = (
            get_tool_policy(
                tool_name
            )
        )

        permission = (
            policy[
                "permission"
            ]
        )

        print(
            f"Tool: {tool_name}"
        )

        print(
            f"Permission: {permission}"
        )

        if (
            permission
            == APPROVAL
        ):

            has_approval_tool = True

    if has_approval_tool:

        return "approval"

    return "tool"


# ============================================================
# 8. Human Approval Node
# ============================================================

def approval_node(
    state: AgentState,
) -> dict[str, Any]:

    tool_calls = (
        get_last_tool_calls(
            state
        )
    )

    approval_requests = []

    for tool_call in tool_calls:

        tool_name = (
            tool_call[
                "function"
            ][
                "name"
            ]
        )

        policy = (
            get_tool_policy(
                tool_name
            )
        )

        if (
            policy["permission"]
            != APPROVAL
        ):

            continue

        raw_arguments = (
            tool_call[
                "function"
            ][
                "arguments"
            ]
        )

        approval_requests.append(
            {
                "tool_name":
                    tool_name,

                "arguments":
                    raw_arguments,

                "reason":
                    policy.get(
                        "reason",
                        "",
                    ),
            }
        )

    print()
    print("=" * 80)
    print(
        "Human Approval Required"
    )
    print("=" * 80)

    for request in approval_requests:

        print(
            f"Tool: "
            f"{request['tool_name']}"
        )

        print(
            f"Arguments: "
            f"{request['arguments']}"
        )

        print(
            f"Reason: "
            f"{request['reason']}"
        )

        print()

    approved = interrupt(
        {
            "type":
                "tool_approval",

            "requests":
                approval_requests,
        }
    )

    return {
        "approval_decision":
            bool(approved)
    }


# ============================================================
# 9. MCP Tool Execution
# ============================================================

async def execute_mcp_calls_async(
    executable_calls: list[
        tuple[
            dict[str, Any],
            str,
            dict[str, Any],
        ]
    ],
) -> dict[str, str]:

    results: dict[str, str] = {}

    async with Client(mcp) as client:

        for (
            tool_call,
            tool_name,
            arguments,
        ) in executable_calls:

            tool_call_id = (
                tool_call["id"]
            )

            try:

                result = (
                    await client.call_tool(
                        tool_name,
                        arguments,
                    )
                )

                results[
                    tool_call_id
                ] = (
                    mcp_result_to_json(
                        result
                    )
                )

            except Exception as exc:

                results[
                    tool_call_id
                ] = json.dumps(
                    {
                        "status":
                            "mcp_call_error",

                        "error":
                            str(exc),
                    },
                    ensure_ascii=False,
                )

    return results


# ============================================================
# 10. Tool Node
# ============================================================

def tool_node(
    state: AgentState,
) -> dict[str, Any]:

    print()
    print("=" * 80)
    print("Tool Runtime Node")
    print("=" * 80)

    tool_calls = (
        get_last_tool_calls(
            state
        )
    )

    tool_messages = []

    executable_calls = []

    approval_decision = (
        state.get(
            "approval_decision"
        )
    )

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

        raw_arguments = (
            tool_call[
                "function"
            ][
                "arguments"
            ]
        )

        print()
        print(
            f"Processing Tool: "
            f"{tool_name}"
        )

        # ----------------------------------------------------
        # Parse arguments
        # ----------------------------------------------------

        try:

            arguments = (
                json.loads(
                    raw_arguments
                )
            )

        except json.JSONDecodeError as exc:

            tool_messages.append(
                {
                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call_id,

                    "content":
                        json.dumps(
                            {
                                "status":
                                    "argument_parse_error",

                                "error":
                                    str(exc),
                            },
                            ensure_ascii=False,
                        ),
                }
            )

            continue

        # ----------------------------------------------------
        # Runtime Validation
        # ----------------------------------------------------

        valid, reason = (
            validate_tool_call(
                tool_name,
                arguments,
            )
        )

        if not valid:

            print(
                f"Validation: FAIL "
                f"({reason})"
            )

            tool_messages.append(
                {
                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call_id,

                    "content":
                        json.dumps(
                            {
                                "status":
                                    "validation_error",

                                "error":
                                    reason,
                            },
                            ensure_ascii=False,
                        ),
                }
            )

            continue

        print(
            "Validation: PASS"
        )

        # ----------------------------------------------------
        # Permission Policy
        # ----------------------------------------------------

        policy = (
            get_tool_policy(
                tool_name
            )
        )

        permission = (
            policy[
                "permission"
            ]
        )

        print(
            f"Permission: "
            f"{permission}"
        )

        # ----------------------------------------------------
        # DENY
        # ----------------------------------------------------

        if permission == DENY:

            tool_messages.append(
                {
                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call_id,

                    "content":
                        json.dumps(
                            {
                                "status":
                                    "denied_by_policy",

                                "tool":
                                    tool_name,
                            },
                            ensure_ascii=False,
                        ),
                }
            )

            continue

        # ----------------------------------------------------
        # APPROVAL
        # ----------------------------------------------------

        if (
            permission
            == APPROVAL
            and approval_decision
            is not True
        ):

            print(
                "Human Approval: REJECTED"
            )

            tool_messages.append(
                {
                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call_id,

                    "content":
                        json.dumps(
                            {
                                "status":
                                    "rejected_by_human",

                                "tool":
                                    tool_name,
                            },
                            ensure_ascii=False,
                        ),
                }
            )

            continue

        # ----------------------------------------------------
        # AUTO or Approved Tool
        # ----------------------------------------------------

        executable_calls.append(
            (
                tool_call,
                tool_name,
                arguments,
            )
        )

    # ========================================================
    # Execute Approved Calls through MCP
    # ========================================================

    if executable_calls:

        print()
        print(
            "Executing through MCP..."
        )

        mcp_results = asyncio.run(
            execute_mcp_calls_async(
                executable_calls
            )
        )

        for (
            tool_call,
            tool_name,
            arguments,
        ) in executable_calls:

            tool_call_id = (
                tool_call["id"]
            )

            tool_messages.append(
                {
                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call_id,

                    "content":
                        mcp_results[
                            tool_call_id
                        ],
                }
            )

    return {
        "messages":
            tool_messages,

        # Clear approval state after this execution round.
        "approval_decision":
            None,
    }


# ============================================================
# 11. Build Graph
# ============================================================

def build_graph(
    checkpointer: SqliteSaver,
):

    builder = StateGraph(
        AgentState
    )

    builder.add_node(
        "llm",
        llm_node,
    )

    builder.add_node(
        "approval",
        approval_node,
    )

    builder.add_node(
        "tool",
        tool_node,
    )

    builder.add_edge(
        START,
        "llm",
    )

    builder.add_conditional_edges(
        "llm",
        route_after_llm,
        {
            "approval":
                "approval",

            "tool":
                "tool",

            "end":
                END,
        },
    )

    builder.add_edge(
        "approval",
        "tool",
    )

    builder.add_edge(
        "tool",
        "llm",
    )

    return builder.compile(
        checkpointer=
            checkpointer
    )


# ============================================================
# 12. Run One User Turn
# ============================================================

def run_user_turn(
    graph,
    user_input: str,
    thread_id: str,
) -> None:

    config = {
        "configurable": {
            "thread_id":
                thread_id
        }
    }

    # --------------------------------------------------------
    # Determine whether this thread already has memory
    # --------------------------------------------------------

    snapshot = (
        graph.get_state(
            config
        )
    )

    existing_messages = (
        snapshot.values.get(
            "messages",
            [],
        )
        if snapshot.values
        else []
    )

    # --------------------------------------------------------
    # First turn:
    # inject System Prompt
    # --------------------------------------------------------

    if not existing_messages:

        input_state = {
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

    # --------------------------------------------------------
    # Later turn:
    # only append User message
    # --------------------------------------------------------

    else:

        input_state = {
            "messages": [
                {
                    "role":
                        "user",

                    "content":
                        user_input,
                }
            ],

            "approval_decision":
                None,
        }

    result = (
        graph.invoke(
            input_state,
            config=config,
        )
    )

    # ========================================================
    # Handle Interrupt
    # ========================================================

    while (
        "__interrupt__"
        in result
    ):

        interrupts = (
            result[
                "__interrupt__"
            ]
        )

        print()
        print("=" * 80)
        print(
            "Graph Paused for Human Approval"
        )
        print("=" * 80)

        print(
            interrupts
        )

        human_input = input(
            "Approve? [y/n]: "
        ).strip().lower()

        approved = (
            human_input
            in {
                "y",
                "yes",
            }
        )

        result = (
            graph.invoke(
                Command(
                    resume=
                        approved
                ),
                config=config,
            )
        )

    # ========================================================
    # Final Answer
    # ========================================================

    messages = (
        result[
            "messages"
        ]
    )

    if messages:

        last_message = (
            messages[-1]
        )

        if (
            last_message.get(
                "role"
            )
            == "assistant"
        ):

            print()
            print("=" * 80)
            print("Final Answer")
            print("=" * 80)

            print(
                last_message.get(
                    "content",
                    "",
                )
            )


# ============================================================
# 13. Main
# ============================================================

def main() -> None:

    print()
    print("=" * 80)
    print(
        "Traffic Simulation Agent V4"
    )
    print("=" * 80)

    print(
        "LangGraph + MCP + Policy + "
        "HITL + Context + Checkpoint"
    )

    checkpoint_dir = Path(
        "checkpoints"
    )

    checkpoint_dir.mkdir(
        exist_ok=True
    )

    database_path = (
        checkpoint_dir
        /
        "traffic_agent_v4.sqlite"
    )

    connection = sqlite3.connect(
        database_path,
        check_same_thread=False,
    )

    checkpointer = SqliteSaver(
        connection
    )

    graph = build_graph(
        checkpointer
    )

    thread_id = (
        "traffic-agent-v4-final-demo"
    )

    print()
    print(
        f"Thread ID: "
        f"{thread_id}"
    )

    print(
        f"Checkpoint DB: "
        f"{database_path}"
    )

    print()
    print(
        "Type 'exit' to stop."
    )

    try:

        while True:

            print()

            user_input = input(
                "User: "
            ).strip()

            if (
                user_input.lower()
                in {
                    "exit",
                    "quit",
                }
            ):

                break

            if not user_input:
                continue

            run_user_turn(
                graph,
                user_input,
                thread_id,
            )

    finally:

        connection.close()


if __name__ == "__main__":

    main()