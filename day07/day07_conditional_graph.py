from typing_extensions import TypedDict

from langgraph.graph import (
    StateGraph,
    START,
    END,
)


# ============================================================
# 1. State
# ============================================================

class NumberState(TypedDict):
    number: int
    category: str
    result: str


# ============================================================
# 2. Nodes
# ============================================================

def check_number(
    state: NumberState,
) -> dict:

    print("Running node: check_number")

    number = state["number"]

    if number >= 10:
        category = "big"
    else:
        category = "small"

    return {
        "category": category,
    }


def big_number_node(
    state: NumberState,
) -> dict:

    print("Running node: big_number_node")

    return {
        "result": (
            f"{state['number']} is a big number."
        )
    }


def small_number_node(
    state: NumberState,
) -> dict:

    print("Running node: small_number_node")

    return {
        "result": (
            f"{state['number']} is a small number."
        )
    }


# ============================================================
# 3. Conditional Routing Function
# ============================================================

def route_number(
    state: NumberState,
) -> str:

    print(
        f"Routing decision: "
        f"{state['category']}"
    )

    if state["category"] == "big":
        return "big"

    return "small"


# ============================================================
# 4. Build Graph
# ============================================================

builder = StateGraph(
    NumberState
)

builder.add_node(
    "check_number",
    check_number,
)

builder.add_node(
    "big_number_node",
    big_number_node,
)

builder.add_node(
    "small_number_node",
    small_number_node,
)


# START
builder.add_edge(
    START,
    "check_number",
)


# Conditional Edge
builder.add_conditional_edges(
    "check_number",
    route_number,
    {
        "big": "big_number_node",
        "small": "small_number_node",
    },
)


# END
builder.add_edge(
    "big_number_node",
    END,
)

builder.add_edge(
    "small_number_node",
    END,
)


# ============================================================
# 5. Compile
# ============================================================

graph = builder.compile()


# ============================================================
# 6. Run
# ============================================================

def main():

    initial_state = {
        "number": 5,
        "category": "",
        "result": "",
    }

    final_state = graph.invoke(
        initial_state
    )

    print()
    print("Final State:")
    print(final_state)


if __name__ == "__main__":
    main()