import json
from pathlib import Path

from openai import OpenAI


# =========================
# 1. API 配置
# =========================

BASE_DIR = Path(__file__).resolve().parent
API_FILE = BASE_DIR / "api.txt"

api_key = API_FILE.read_text(
    encoding="utf-8"
).strip()


client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# =========================
# 2. 真正的 Python Tool
# =========================

def get_queue_length() -> dict:
    """
    获取当前交叉口平均排队长度。
    Day 2 暂时使用模拟数据。
    """

    return {
        "average_queue_length": 32.5,
        "unit": "m"
    }


# =========================
# 3. 告诉 DeepSeek 有什么 Tool
# =========================

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_queue_length",
            "description": (
                "获取当前交叉口的平均排队长度。"
                "当用户询问当前排队长度、排队状况"
                "或需要实时排队数据时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


# =========================
# 4. 用户提出问题
# =========================

messages = [
    {
        "role": "system",
        "content": (
            "你是一名交通工程分析助手。"
            "当回答需要实时交通数据时，不要猜测，"
            "应使用提供的工具获取数据后再回答。"
        ),
    },
    {
        "role": "user",
        "content": (
            "请帮我看看当前路口的平均排队情况怎么样？"
            "请基于实时工具数据回答。"
        ),
    },
]


# =========================
# 5. 第一次调用 DeepSeek
# =========================

response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=messages,
    tools=tools,

    # Day 2先关闭Thinking，方便理解Tool Calling过程
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    },

    stream=False,
)


message = response.choices[0].message


print("\n===== Step 1: Model Decision =====")

print(
    "Finish Reason:",
    response.choices[0].finish_reason,
)

print(
    "Content:",
    repr(message.content),
)

print(
    "Tool Calls:",
    message.tool_calls,
)

if not message.tool_calls:

    print("\n模型没有请求调用工具。")
    print("Model Answer:", message.content)

    raise SystemExit


tool_call = message.tool_calls[0]


print("\n===== Step 2: Tool Request =====")

print(
    "Tool Name:",
    tool_call.function.name,
)

print(
    "Tool Arguments:",
    tool_call.function.arguments,
)

if tool_call.function.name == "get_queue_length":

    tool_result = get_queue_length()

else:

    raise ValueError(
        f"未知工具：{tool_call.function.name}"
    )

print("\n===== Step 3: Execute Tool =====")

print(
    "Tool Result:",
    tool_result,
)

assistant_tool_message = {
    "role": "assistant",
    "content": message.content,
    "tool_calls": [
        {
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
        }
    ],
}

messages.append(assistant_tool_message)

tool_result_message = {
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": json.dumps(
        tool_result,
        ensure_ascii=False,
    ),
}

messages.append(tool_result_message)

print("\n===== Messages Before Second Request =====")

for index, msg in enumerate(messages):
    print(f"\nMessage {index}:")
    print(msg)

response2 = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=messages,
    tools=tools,

    extra_body={
        "thinking": {
            "type": "disabled"
        }
    },

    stream=False,
)


final_message = response2.choices[0].message


print("\n===== Step 4: Final Answer =====")
print("Finish Reason:", response2.choices[0].finish_reason)
print("Content:", final_message.content)