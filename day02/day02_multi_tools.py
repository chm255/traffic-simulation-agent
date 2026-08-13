import json
from pathlib import Path

from openai import OpenAI


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
# Tool 1：排队长度
# =========================

def get_queue_length(
    direction: str = "overall"
) -> dict:

    queue_data = {
        "overall": 32.5,
        "east": 41.2,
        "west": 28.7,
        "south": 18.6,
        "north": 21.4,
    }

    if direction not in queue_data:
        return {
            "status": "error",
            "message": f"未知方向：{direction}",
        }

    return {
        "direction": direction,
        "average_queue_length": queue_data[direction],
        "unit": "m",
    }


# =========================
# Tool 2：平均等待时间
# =========================

def get_waiting_time() -> dict:

    return {
        "average_waiting_time": 88.2,
        "unit": "s",
    }


# =========================
# Tool 3：通过量
# =========================

def get_throughput() -> dict:

    return {
        "throughput": 1171,
        "unit": "veh",
    }

tools = [
   {
    "type": "function",
    "function": {
        "name": "get_queue_length",
        "description": (
            "获取当前交叉口实时平均排队长度。"
            "如果用户询问整个交叉口或没有指定方向，"
            "只使用 direction='overall'，"
            "不要额外查询东西南北各进口。"
            "只有当用户明确指定某个进口方向时，"
            "才查询对应方向。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": [
                        "overall",
                        "east",
                        "west",
                        "south",
                        "north",
                    ],
                    "description": (
                        "查询方向。"
                        "overall表示整个交叉口；"
                        "east、west、south、north"
                        "分别表示东、西、南、北进口。"
                        "用户未指定方向时使用overall。"
                    ),
                }
            },
        },
    },
},

    {
        "type": "function",
        "function": {
            "name": "get_waiting_time",
            "description": (
                "获取当前交叉口实时平均等待时间。"
                "仅当完成用户任务确实需要等待时间，"
                "且用户没有提供该数据时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_throughput",
            "description": (
                "获取当前交叉口当前统计周期的车辆通过量。"
                "仅当用户询问通过量，"
                "或完成当前分析确实需要通过量时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

TOOL_MAP = {
    "get_queue_length": get_queue_length,
    "get_waiting_time": get_waiting_time,
    "get_throughput": get_throughput,
}

user_query = input(
    "\nUser: "
).strip()

messages = [
    {
        "role": "system",
        "content": (
            "你是一名交通工程分析助手。"
            "优先使用用户已经提供的数据。"
            "只有当完成任务所必需的信息缺失时，"
            "才调用工具获取数据。"
            "不要重复查询用户已经提供的数据。"
            "不要编造工具没有提供的交通数据、"
            "固定拥堵阈值、信号周期或拥堵原因。"
            "如果已有信息不足以支持可靠结论，"
            "应说明信息不足。"
            "只调用完成当前任务所必需的最少工具，"
            "不要获取用户没有要求且回答问题不需要的数据。"
        ),
    },
    {
        "role": "user",
        "content": user_query,
    },
]

response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=messages,
    tools=tools,

    # 明确让模型自主决定：
    # 直接回答 or 调哪个Tool
    tool_choice="auto",

    extra_body={
        "thinking": {
            "type": "disabled"
        }
    },

    stream=False,
)


message = response.choices[0].message


print("\n===== Model Decision =====")

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

    print("\n===== Final Answer =====")
    print(message.content)

    raise SystemExit

assistant_tool_message = {
    "role": "assistant",
    "content": message.content,
    "tool_calls": [],
}


for tool_call in message.tool_calls:

    assistant_tool_message["tool_calls"].append(
        {
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.function.name,
                "arguments":
                    tool_call.function.arguments,
            },
        }
    )


messages.append(
    assistant_tool_message
)

print("\n===== Execute Tools =====")


for tool_call in message.tool_calls:

    tool_name = tool_call.function.name

    print(
        "\nTool Name:",
        tool_name,
    )

    print(
        "Raw Arguments:",
        tool_call.function.arguments,
    )


    # -------------------------
    # 解析模型提供的JSON参数
    # -------------------------

    try:

        arguments = json.loads(
            tool_call.function.arguments
        )

    except json.JSONDecodeError:

        arguments = {}


    print(
        "Parsed Arguments:",
        arguments,
    )


    # -------------------------
    # 查询Python函数
    # -------------------------

    if tool_name not in TOOL_MAP:

        tool_result = {
            "status": "error",
            "message":
                f"未知工具：{tool_name}",
        }

    else:

        tool_function = TOOL_MAP[
            tool_name
        ]

        tool_result = tool_function(
            **arguments
        )


    print(
        "Tool Result:",
        tool_result,
    )


    # -------------------------
    # 把执行结果加入messages
    # -------------------------

    messages.append(
        {
            "role": "tool",
            "tool_call_id":
                tool_call.id,

            "content": json.dumps(
                tool_result,
                ensure_ascii=False,
            ),
        }
    )

response2 = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=messages,
    tools=tools,
    tool_choice="auto",

    extra_body={
        "thinking": {
            "type": "disabled"
        }
    },

    stream=False,
)


final_message = response2.choices[0].message


print("\n===== Final Answer =====")

print(
    "Finish Reason:",
    response2.choices[0].finish_reason,
)

print(
    "Content:",
    final_message.content,
)