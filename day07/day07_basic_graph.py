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
    result: int


# ============================================================
# 2. Node
# ============================================================

def double_number(
    state: NumberState,
) -> dict:

    print("Running node: double_number")

    number = state["number"]

    return {
        "result": number * 2,
    }


# ============================================================
# 3. Build Graph
# ============================================================

builder = StateGraph(
    NumberState
)

builder.add_node(
    "double_number",
    double_number,
)

builder.add_edge(
    START,
    "double_number",
)

builder.add_edge(
    "double_number",
    END,
)


# ============================================================
# 4. Compile
# ============================================================

graph = builder.compile()


# ============================================================
# 5. Run
# ============================================================

def main():

    initial_state = {
        "number": 5,
        "result": 0,
    }

    final_state = graph.invoke(
        initial_state
    )

    print()
    print("Final State:")
    print(final_state)


if __name__ == "__main__":
    main()