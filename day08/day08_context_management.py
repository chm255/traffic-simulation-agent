from __future__ import annotations

from typing import Any


# ============================================================
# Context Configuration
# ============================================================

MAX_RECENT_MESSAGES = 6


# ============================================================
# Build LLM Context
# ============================================================

def build_llm_context(
    messages: list[dict[str, Any]],
    max_recent_messages: int = MAX_RECENT_MESSAGES,
) -> list[dict[str, Any]]:

    if not messages:
        return []

    # --------------------------------------------------------
    # 1. Preserve the System Prompt
    # --------------------------------------------------------

    system_messages = [
        message
        for message in messages
        if message.get("role") == "system"
    ]

    system_message = (
        system_messages[0]
        if system_messages
        else None
    )

    # --------------------------------------------------------
    # 2. Everything except System
    # --------------------------------------------------------

    non_system_messages = [
        message
        for message in messages
        if message.get("role") != "system"
    ]

    # --------------------------------------------------------
    # 3. Keep only recent messages
    # --------------------------------------------------------

    recent_messages = (
        non_system_messages[
            -max_recent_messages:
        ]
    )

    # --------------------------------------------------------
    # 4. Build final context
    # --------------------------------------------------------

    context = []

    if system_message is not None:
        context.append(
            system_message
        )

    context.extend(
        recent_messages
    )

    return context


# ============================================================
# Test
# ============================================================

def main():

    messages = [
        {
            "role": "system",
            "content": "You are Traffic Simulation Agent."
        },
        {
            "role": "user",
            "content": "Message 1"
        },
        {
            "role": "assistant",
            "content": "Answer 1"
        },
        {
            "role": "user",
            "content": "Message 2"
        },
        {
            "role": "assistant",
            "content": "Answer 2"
        },
        {
            "role": "user",
            "content": "Message 3"
        },
        {
            "role": "assistant",
            "content": "Answer 3"
        },
        {
            "role": "user",
            "content": "Message 4"
        },
        {
            "role": "assistant",
            "content": "Answer 4"
        },
    ]

    context = build_llm_context(
        messages,
        max_recent_messages=4,
    )

    print(
        f"Full message count: "
        f"{len(messages)}"
    )

    print(
        f"LLM context count: "
        f"{len(context)}"
    )

    print()

    for index, message in enumerate(
        context,
        start=1,
    ):

        print(
            f"{index}. "
            f"{message['role']}: "
            f"{message.get('content')}"
        )


if __name__ == "__main__":
    main()