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


    # Mock Simulation
    rng = random.Random(seed)

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

    demand_factor = {
        "low": 0.70,
        "medium": 0.85,
        "high": 1.00,
    }[demand_level]

    metrics = base_metrics[controller]

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


    return {
        "status": "success",

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
                "只有当用户明确要求运行、测试或比较控制方案时调用。"
                "当前返回Day 3教学用Mock Simulation结果，"
                "并非真实SUMO实验。"
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
                        ),
                    },

                    "seed": {
                        "type": "integer",

                        "description": (
                            "实验随机种子。"
                        ),
                    },

                    "duration": {
                        "type": "integer",

                        "description": (
                            "仿真时间，单位秒。"
                            "默认1800秒。"
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
                            "交通需求水平，"
                            "默认为high。"
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
# 4. Tool Registry
# ============================================================

TOOL_MAP = {
    "run_simulation_experiment":
        run_simulation_experiment,
}

def call_model(
    messages: list,
):
    """
    调用一次 DeepSeek。
    """

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

    return response

def execute_tool(
    tool_name: str,
    arguments: dict,
) -> dict:
    """
    根据工具名称执行对应Python函数。
    """

    if tool_name not in TOOL_MAP:

        return {
            "status": "error",
            "message": (
                f"未知工具：{tool_name}"
            ),
        }


    tool_function = TOOL_MAP[
        tool_name
    ]


    try:

        result = tool_function(
            **arguments
        )

        return result


    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }

def run_agent(
    user_query: str,
    max_steps: int = 10,
) -> str:

    messages = [
        {
            "role": "system",

            "content": (
                "你是一名交通仿真实验助手。"
                "如果用户只是询问概念或已有信息足够，"
                "直接回答。"
                "如果用户明确要求运行交通仿真实验，"
                "则使用提供的工具。"
                "不要编造实验结果。"
                "只有工具返回的数据才能被视为实验结果。"
                "当前实验工具返回的是Mock Simulation数据，"
                "必须明确说明不是真实SUMO结果。"
            ),
        },

        {
            "role": "user",
            "content": user_query,
        },
    ]


    # ========================================================
    # Agent Loop
    # ========================================================

    for step in range(
        1,
        max_steps + 1,
    ):

        print(
            f"\n===== Agent Step {step} ====="
        )
        # ------------------------
        # 1. 调用模型
        # ------------------------
        response = call_model(
            messages
        )

        message = (
            response
            .choices[0]
            .message
        )


        print(
            "Finish Reason:",
            response
            .choices[0]
            .finish_reason,
        )

        print(
            "Content:",
            repr(message.content),
        )

        print(
            "Tool Calls:",
            message.tool_calls,
        )


        # ====================================================
        # 2. 没有Tool Call
        #    → Agent结束
        # ====================================================

        if not message.tool_calls:

            return (
                message.content
                or ""
            )


        # ====================================================
        # 3. 有Tool Call
        #    → 保存assistant消息
        # ====================================================

        assistant_tool_message = {
            "role": "assistant",

            "content":
                message.content,

            "tool_calls": [],
        }


        for tool_call in message.tool_calls:

            assistant_tool_message[
                "tool_calls"
            ].append(
                {
                    "id":
                        tool_call.id,

                    "type":
                        "function",

                    "function": {
                        "name":
                            tool_call
                            .function
                            .name,

                        "arguments":
                            tool_call
                            .function
                            .arguments,
                    },
                }
            )


        messages.append(
            assistant_tool_message
        )


        # ====================================================
        # 4. 执行这一轮全部Tool
        # ====================================================

        for tool_call in message.tool_calls:

            tool_name = (
                tool_call
                .function
                .name
            )

            raw_arguments = (
                tool_call
                .function
                .arguments
            )


            print(
                "\nTool Name:",
                tool_name,
            )

            print(
                "Raw Arguments:",
                raw_arguments,
            )


            # ------------------------
            # JSON参数解析
            # ------------------------

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


            # ------------------------
            # 执行Tool
            # ------------------------

            tool_result = execute_tool(
                tool_name,
                arguments,
            )


            print(
                "Tool Result:",
                tool_result,
            )


            # ------------------------
            # Tool Result返回给模型
            # ------------------------

            messages.append(
                {
                    "role": "tool",

                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps(
                            tool_result,
                            ensure_ascii=False,
                        ),
                }
            )


        # ====================================================
        # 注意这里没有 response2！
        #
        # for loop自然进入下一次 step
        # 然后再次：
        #
        # response = call_model(messages)
        #
        # ====================================================


    # ========================================================
    # 超过最大步骤
    # ========================================================

    return (
        "Agent达到最大执行步骤，"
        "任务未能正常结束。"
    )

if __name__ == "__main__":

    user_query = input(
        "\nUser: "
    ).strip()


    answer = run_agent(
        user_query
    )


    print(
        "\n===== Final Answer ====="
    )

    print(answer)