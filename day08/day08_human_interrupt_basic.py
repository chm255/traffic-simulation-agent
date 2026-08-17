from __future__ import annotations

from typing import Literal

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
# 1. State
# ============================================================

class ApprovalState(TypedDict):

    action: str

    approved: bool | None

    result: str


# ============================================================
# 2. Human Approval Node
# ============================================================

def request_approval(
    state: ApprovalState,
) -> dict:

    print()
    print("=" * 60)
    print("Running Node: request_approval")
    print("=" * 60)

    print(
        f"Pending Action: "
        f"{state['action']}"
    )

    # --------------------------------------------------------
    # Pause Graph here
    # --------------------------------------------------------

    human_decision = interrupt(
        {
            "type": "approval_request",
            "message": "是否批准执行这个操作？",
            "action": state["action"],
        }
    )

    print()
    print(
        "Graph resumed."
    )

    print(
        f"Human Decision: "
        f"{human_decision}"
    )

    return {
        "approved":
            bool(human_decision)
    }


# ============================================================
# 3. Router
# ============================================================

def route_after_approval(
    state: ApprovalState,
) -> Literal[
    "execute_action",
    "cancel_action",
]:

    print()
    print(
        "Running Router: "
        "route_after_approval"
    )

    if state["approved"]:

        print(
            "Routing Decision: execute_action"
        )

        return "execute_action"

    print(
        "Routing Decision: cancel_action"
    )

    return "cancel_action"


# ============================================================
# 4. Execute Node
# ============================================================

def execute_action(
    state: ApprovalState,
) -> dict:

    print()
    print("=" * 60)
    print("Running Node: execute_action")
    print("=" * 60)

    return {
        "result": (
            f"Action executed: "
            f"{state['action']}"
        )
    }


# ============================================================
# 5. Cancel Node
# ============================================================

def cancel_action(
    state: ApprovalState,
) -> dict:

    print()
    print("=" * 60)
    print("Running Node: cancel_action")
    print("=" * 60)

    return {
        "result": (
            f"Action cancelled: "
            f"{state['action']}"
        )
    }


# ============================================================
# 6. Build Graph
# ============================================================

builder = StateGraph(
    ApprovalState
)

builder.add_node(
    "request_approval",
    request_approval,
)

builder.add_node(
    "execute_action",
    execute_action,
)

builder.add_node(
    "cancel_action",
    cancel_action,
)


builder.add_edge(
    START,
    "request_approval",
)


builder.add_conditional_edges(
    "request_approval",
    route_after_approval,
    {
        "execute_action":
            "execute_action",

        "cancel_action":
            "cancel_action",
    },
)


builder.add_edge(
    "execute_action",
    END,
)

builder.add_edge(
    "cancel_action",
    END,
)


# ============================================================
# 7. Checkpointer
# ============================================================

checkpointer = (
    InMemorySaver()
)


graph = builder.compile(
    checkpointer=checkpointer
)


# ============================================================
# 8. Thread
# ============================================================

GRAPH_CONFIG = {
    "configurable": {
        "thread_id":
            "day08-approval-demo"
    }
}


# ============================================================
# 9. Main
# ============================================================

def main():

    initial_state: ApprovalState = {
        "action":
            "运行一个耗时较长的交通仿真实验",

        "approved":
            None,

        "result":
            "",
    }

    print()
    print("=" * 60)
    print("Step 1: Start Graph")
    print("=" * 60)

    result = graph.invoke(
        initial_state,
        config=GRAPH_CONFIG,
    )

    # --------------------------------------------------------
    # Graph has paused
    # --------------------------------------------------------

    interrupts = result.get(
        "__interrupt__",
        ()
    )

    if not interrupts:

        print(
            "No interrupt detected."
        )

        return

    interrupt_data = (
        interrupts[0].value
    )

    print()
    print("=" * 60)
    print("Graph Paused")
    print("=" * 60)

    print(
        "Interrupt Data:"
    )

    print(
        interrupt_data
    )

    print()

    human_input = input(
        "Approve? (yes/no): "
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

    # --------------------------------------------------------
    # Resume Graph
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("Step 2: Resume Graph")
    print("=" * 60)

    final_state = graph.invoke(
        Command(
            resume=approved
        ),
        config=GRAPH_CONFIG,
    )

    print()
    print("=" * 60)
    print("Final State")
    print("=" * 60)

    print(
        final_state
    )


if __name__ == "__main__":
    main()