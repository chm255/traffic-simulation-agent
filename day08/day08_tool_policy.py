from __future__ import annotations

from typing import Any


# ============================================================
# Permission Types
# ============================================================

AUTO = "auto"
APPROVAL = "approval"
DENY = "deny"


# ============================================================
# Tool Categories
# ============================================================

READ = "read"
COMPUTE = "compute"
WRITE = "write"
DESTRUCTIVE = "destructive"


# ============================================================
# Tool Policy Registry
# ============================================================

TOOL_POLICIES = {

    "search_project_knowledge": {
        "category": READ,
        "permission": AUTO,
        "reason": (
            "只读取本地项目知识，"
            "不修改外部状态。"
        ),
    },

    "run_sumo_experiment": {
        "category": COMPUTE,
        "permission": APPROVAL,
        "reason": (
            "会启动真实 SUMO 仿真，"
            "消耗计算时间和系统资源。"
        ),
    },

}


# ============================================================
# Policy Decision
# ============================================================

def get_tool_policy(
    tool_name: str,
) -> dict[str, Any]:

    policy = TOOL_POLICIES.get(
        tool_name
    )

    # --------------------------------------------------------
    # Unknown Tool:
    # default deny
    # --------------------------------------------------------

    if policy is None:

        return {
            "tool": tool_name,
            "category": "unknown",
            "permission": DENY,
            "reason": (
                "该工具没有注册安全策略，"
                "默认禁止执行。"
            ),
        }

    return {
        "tool": tool_name,
        **policy,
    }


# ============================================================
# Test
# ============================================================

def main():

    test_tools = [
        "search_project_knowledge",
        "run_sumo_experiment",
        "unknown_tool",
    ]

    for tool_name in test_tools:

        policy = get_tool_policy(
            tool_name
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
            f"{policy['permission']}"
        )

        print(
            f"Reason: "
            f"{policy['reason']}"
        )


if __name__ == "__main__":
    main()