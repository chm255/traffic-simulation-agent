import json
import random
from pathlib import Path

from openai import OpenAI


# ============================================================
# 1. DeepSeek 配置
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
API_FILE = BASE_DIR / "api.txt"

api_key = API_FILE.read_text(
    encoding="utf-8"
).strip()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# ============================================================
# 2. 实验 Tool
# ============================================================

def run_simulation_experiment(
    controller: str,
    seed: int,
    duration: int = 1800,
    demand_level: str = "high",
) -> dict:
    """
    运行一次交通仿真实验。

    Day 2 版本：
    暂时不真正调用 SUMO，
    而是生成可重复的模拟实验结果。
    """

    supported_controllers = {
        "fixed_left",
        "fixed_straight",
        "adaptive_rule",
    }

    supported_demand_levels = {
        "low",
        "medium",
        "high",
    }


    # ----------------------------
    # 参数检查
    # ----------------------------

    if controller not in supported_controllers:
        return {
            "status": "error",
            "message": f"不支持的控制器：{controller}",
        }

    if demand_level not in supported_demand_levels:
        return {
            "status": "error",
            "message": f"不支持的需求水平：{demand_level}",
        }

    if seed < 0:
        return {
            "status": "error",
            "message": "seed 必须 >= 0",
        }

    if duration <= 0:
        return {
            "status": "error",
            "message": "duration 必须 > 0",
        }


    # ----------------------------
    # Mock Simulation
    # ----------------------------
    # 同一个 seed 会产生可重复结果

    rng = random.Random(seed)


    # 不同控制器的基础表现
    base_metrics = {
        "fixed_left": {
            "queue": 35.0,
            "waiting": 95.0,
            "throughput": 1050,
            "completion_rate": 0.84,
        },

        "fixed_straight": {
            "queue": 38.0,
            "waiting": 102.0,
            "throughput": 1010,
            "completion_rate": 0.81,
        },

        "adaptive_rule": {
            "queue": 29.0,
            "waiting": 78.0,
            "throughput": 1120,
            "completion_rate": 0.90,
        },
    }


    metrics = base_metrics[controller]


    # 需求水平影响
    demand_factor = {
        "low": 0.70,
        "medium": 0.85,
        "high": 1.00,
    }[demand_level]


    average_queue = (
        metrics["queue"]
        * demand_factor
        + rng.uniform(-2.0, 2.0)
    )

    average_waiting_time = (
        metrics["waiting"]
        * demand_factor
        + rng.uniform(-5.0, 5.0)
    )


    # throughput 随仿真时长缩放
    duration_factor = duration / 1800

    throughput = int(
        metrics["throughput"]
        * duration_factor
        * demand_factor
        + rng.uniform(-20, 20)
    )


    completion_rate = (
        metrics["completion_rate"]
        + rng.uniform(-0.02, 0.02)
    )

    completion_rate = max(
        0.0,
        min(1.0, completion_rate)
    )


    # ----------------------------
    # 返回实验结果
    # ----------------------------

    return {
        "status": "success",

        # 非常重要：明确说明是假实验
        "data_source": "mock_simulation",

        "experiment_config": {
            "controller": controller,
            "seed": seed,
            "duration": duration,
            "demand_level": demand_level,
        },

        "metrics": {
            "average_queue": round(
                average_queue,
                2
            ),

            "average_waiting_time": round(
                average_waiting_time,
                2
            ),

            "throughput": throughput,

            "completion_rate": round(
                completion_rate,
                3
            ),
        },
    }


# ============================================================
# 3. Tool Schema
# ============================================================

tools = [
    {
        "type": "function",

        "function": {
            "name": "run_simulation_experiment",

            "description": (
                "运行一次交通控制仿真实验。"
                "当用户要求运行、测试或比较交通控制方案时使用。"
                "实验需要指定控制方案和随机种子。"
                "当前为Day 2教学用Mock Simulation，"
                "不是真实SUMO实验。"
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "controller": {
                        "type": "string",

                        "enum": [
                            "fixed_left",
                            "fixed_straight",
                            "adaptive_rule",
                        ],

                        "description": (
                            "交通控制方案。"
                            "fixed_left表示固定左转方案；"
                            "fixed_straight表示固定直行方案；"
                            "adaptive_rule表示自适应规则方案。"
                        ),
                    },

                    "seed": {
                        "type": "integer",

                        "description": (
                            "随机种子，用于保证实验可重复。"
                        ),
                    },

                    "duration": {
                        "type": "integer",

                        "description": (
                            "仿真持续时间，单位秒。"
                            "用户没有指定时默认1800秒。"
                        ),
                    },

                    "demand_level": {
                        "type": "string",

                        "enum": [
                            "low",
                            "medium",
                            "high",
                        ],

                        "description": (
                            "交通需求水平。"
                            "用户没有指定时默认high。"
                        ),
                    },
                },

                "required": [
                    "controller",
                    "seed",
                ],
            },
        },
    }
]


# ============================================================
# 4. Tool 注册表
# ============================================================

TOOL_MAP = {
    "run_simulation_experiment":
        run_simulation_experiment,
}


# ============================================================
# 5. 用户输入
# ============================================================

user_query = input(
    "\nUser: "
).strip()


messages = [
    {
        "role": "system",

        "content": (
            "你是一名交通仿真实验助手。"
            "当用户要求运行交通仿真实验时，"
            "应使用提供的实验工具。"
            "不要自己编造实验结果。"
            "只有工具返回的数据才能作为实验结果。"
            "当前工具返回的是教学用Mock Simulation结果，"
            "因此必须明确告诉用户这不是真实SUMO实验。"
            "如果用户只是询问概念，不需要运行实验，"
            "则直接回答，不要调用工具。"
        ),
    },

    {
        "role": "user",
        "content": user_query,
    },
]


# ============================================================
# 6. 第一次模型调用
# ============================================================

response = client.chat.completions.create(
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


# ============================================================
# 7. 不需要 Tool → 直接回答
# ============================================================

if not message.tool_calls:

    print("\n===== Final Answer =====")
    print(message.content)

    raise SystemExit


# ============================================================
# 8. 保存 Assistant Tool Calls
# ============================================================

assistant_tool_message = {
    "role": "assistant",
    "content": message.content,
    "tool_calls": [],
}


for tool_call in message.tool_calls:

    assistant_tool_message[
        "tool_calls"
    ].append(
        {
            "id": tool_call.id,

            "type": "function",

            "function": {
                "name":
                    tool_call.function.name,

                "arguments":
                    tool_call.function.arguments,
            },
        }
    )


messages.append(
    assistant_tool_message
)


# ============================================================
# 9. 执行全部 Tool
# ============================================================

print("\n===== Execute Tools =====")


for tool_call in message.tool_calls:

    tool_name = (
        tool_call.function.name
    )

    raw_arguments = (
        tool_call.function.arguments
    )


    print(
        "\nTool Name:",
        tool_name,
    )

    print(
        "Raw Arguments:",
        raw_arguments,
    )


    # JSON字符串 → dict

    try:

        arguments = json.loads(
            raw_arguments
        )

    except json.JSONDecodeError:

        arguments = {}


    print(
        "Parsed Arguments:",
        arguments,
    )


    # 查找对应Python函数

    if tool_name not in TOOL_MAP:

        tool_result = {
            "status": "error",
            "message":
                f"未知工具：{tool_name}",
        }

    else:

        tool_function = (
            TOOL_MAP[tool_name]
        )

        try:

            tool_result = tool_function(
                **arguments
            )

        except TypeError as e:

            tool_result = {
                "status": "error",
                "message": str(e),
            }


    print(
        "Tool Result:",
        tool_result,
    )


    # Tool Result 加回消息历史

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


# ============================================================
# 10. 第二次模型调用
# ============================================================

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


final_message = (
    response2.choices[0].message
)


print("\n===== Final Answer =====")

print(
    "Finish Reason:",
    response2.choices[0].finish_reason,
)

print(
    "Content:",
    final_message.content,
)