import json
import random
import re
from pathlib import Path

import openai
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
) -> dict:

    try:

        response = (
            client
            .chat
            .completions
            .create(
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
        )


        return {
            "status": "success",
            "response": response,
        }


    # ==========================================
    # 网络 / 连接问题
    # ==========================================

    except openai.APIConnectionError as e:

        return {
            "status": "api_error",

            "error_type":
                "APIConnectionError",

            "message":
                str(e),
        }


    # ==========================================
    # 429限流
    # ==========================================

    except openai.RateLimitError as e:

        return {
            "status": "api_error",

            "error_type":
                "RateLimitError",

            "message":
                str(e),
        }


    # ==========================================
    # 其他HTTP API错误
    # ==========================================

    except openai.APIStatusError as e:

        return {
            "status": "api_error",

            "error_type":
                type(e).__name__,

            "status_code":
                e.status_code,

            "message":
                str(e),
        }


    # ==========================================
    # 最后保险
    # ==========================================

    except Exception as e:

        return {
            "status": "unexpected_error",

            "error_type":
                type(e).__name__,

            "message":
                str(e),
        }

def extract_seed_from_user_query(
    user_query: str,
) -> int | None:
    """
    尝试从用户原始文本中提取明确提供的 seed。

    Day 3 教学版本，只处理常见表达。
    """

    patterns = [
    r"seed\s*(?:=|:|为|是|用|使用)?\s*(-?\d+)",

    r"(?:随机种子|种子)\s*"
    r"(?:=|:|为|是|用|使用)?\s*"
    r"(-?\d+)",
]

    for pattern in patterns:

        match = re.search(
            pattern,
            user_query,
            flags=re.IGNORECASE,
        )

        if match:

            return int(
                match.group(1)
            )


    return None

def parse_tool_arguments(
    raw_arguments: str,
) -> dict:
    """
    将模型返回的 Tool Arguments JSON 字符串解析成 dict。
    """

    try:

        arguments = json.loads(
            raw_arguments
        )

    except json.JSONDecodeError as e:

        return {
            "success": False,
            "arguments": None,
            "error": (
                f"Tool Arguments JSON 解析失败：{e}"
            ),
        }


    # Tool arguments 最终必须是一个 object / dict
    if not isinstance(arguments, dict):

        return {
            "success": False,
            "arguments": None,
            "error": (
                "Tool Arguments 必须解析为 JSON object。"
            ),
        }


    return {
        "success": True,
        "arguments": arguments,
        "error": None,
    }
    
def validate_tool_arguments(
    tool_name: str,
    arguments: dict,
    user_query: str,
) -> dict:
    """
    验证 LLM 生成的 Tool Arguments。

    返回格式：

    {
        "valid": True / False,
        "errors": [...]
    }
    """

    errors = []


    # ============================================
    # 1. Tool 是否存在
    # ============================================

    if tool_name not in TOOL_MAP:

        errors.append(
            f"未知工具：{tool_name}"
        )

        return {
            "valid": False,
            "errors": errors,
        }


    # ============================================
    # 2. 针对实验工具验证
    # ============================================

    if tool_name == "run_simulation_experiment":

        allowed_arguments = {
            "controller",
            "seed",
            "duration",
            "demand_level",
        }


        # ----------------------------------------
        # 是否出现未知参数
        # ----------------------------------------

        unknown_arguments = (
            set(arguments.keys())
            - allowed_arguments
        )

        if unknown_arguments:

            errors.append(
                "出现未定义参数："
                + ", ".join(
                    sorted(unknown_arguments)
                )
            )


        # ========================================
        # controller
        # ========================================

        controller = arguments.get(
            "controller"
        )

        valid_controllers = {
            "fixed_left",
            "fixed_straight",
            "adaptive_rule",
        }


        if controller is None:

            errors.append(
                "缺少必要参数 controller"
            )

        elif not isinstance(
            controller,
            str,
        ):

            errors.append(
                "controller 必须是字符串"
            )

        elif controller not in valid_controllers:

            errors.append(
                f"不支持的 controller：{controller}"
            )


        # ========================================
        # seed
        # ========================================

        seed = arguments.get(
            "seed"
        )


        if seed is None:

            errors.append(
                "缺少必要参数 seed"
            )

        elif (
            not isinstance(seed, int)
            or isinstance(seed, bool)
        ):

            errors.append(
                "seed 必须是整数"
            )

        elif seed < 0:

            errors.append(
                "seed 必须 >= 0"
            )

        
        # ========================================
        # duration
        # ========================================

        if "duration" in arguments:

            duration = arguments[
                "duration"
            ]

            if (
                not isinstance(duration, int)
                or isinstance(duration, bool)
            ):

                errors.append(
                    "duration 必须是整数"
                )

            elif duration <= 0:

                errors.append(
                    "duration 必须 > 0"
                )
        # ========================================
        # seed 来源验证
        # ========================================

        user_seed = (
            extract_seed_from_user_query(
                user_query
            )
        )


        if user_seed is None:

            errors.append(
                "用户没有明确提供 seed。"
                "禁止模型自行生成随机种子，"
                "应询问用户。"
            )


        elif (
            isinstance(seed, int)
            and not isinstance(seed, bool)
            and seed != user_seed
        ):

            errors.append(
                f"seed 与用户输入不一致："
                f"用户提供 {user_seed}，"
                f"模型生成 {seed}"
            )
        # ========================================
        # demand_level
        # ========================================

        if "demand_level" in arguments:

            demand_level = arguments[
                "demand_level"
            ]

            valid_demand_levels = {
                "low",
                "medium",
                "high",
            }

            if not isinstance(
                demand_level,
                str,
            ):

                errors.append(
                    "demand_level 必须是字符串"
                )

            elif (
                demand_level
                not in valid_demand_levels
            ):

                errors.append(
                    "demand_level 必须是 "
                    "low / medium / high"
                )


    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }

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
            "status": "tool_execution_error",

            "tool_name": tool_name,

            "error_type":
                type(e).__name__,

            "message":
                str(e),
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
                "不要自行创造用户没有提供的必要实验参数。"
                "特别是seed必须由用户明确提供。"
                "如果工具返回validation_error，"
                "应根据错误信息向用户请求或修正参数，"
                "不要猜测缺失参数。"

                "如果工具返回argument_parse_error，"
                "说明工具参数JSON格式错误，"
                "应重新生成符合Tool Schema的合法参数。"

                "如果工具返回tool_execution_error，"
                "说明工具实际执行失败，"
                "不得把失败当作实验结果，"
                "应向用户说明执行失败及错误原因。"
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
        model_result = call_model(
            messages
        )


        print(
            "Model Call Status:",
            model_result["status"],
        )

        if model_result["status"] != "success":

            return (
                "模型调用失败。\n"
                f"错误类型："
                f"{model_result.get('error_type')}\n"
                f"错误信息："
                f"{model_result.get('message')}"
            )
        response = model_result[
            "response"
        ]
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
            parse_result = parse_tool_arguments(
                raw_arguments
            )


            print(
                "Parse Result:",
                parse_result,
            )
            if not parse_result["success"]:

                tool_result = {
                    "status": "argument_parse_error",

                    "message": (
                        "工具参数解析失败，"
                        "本次工具没有执行。"
                    ),

                    "error":
                        parse_result["error"],

                    "instruction": (
                        "请重新生成符合 Tool Schema 的"
                        "合法 JSON 参数。"
                    ),
                }


                print(
                    "Tool Result:",
                    tool_result,
                )


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


                # 当前这个 Tool Call 处理结束
                # 继续处理本轮其他 Tool Call
                continue
            arguments = parse_result[
                "arguments"
            ]

            print(
                "Parsed Arguments:",
                arguments,
            )

            validation = validate_tool_arguments(
                tool_name,
                arguments,
                user_query,
            )

            print(
                "Validation:",
                validation,
            )


            if not validation["valid"]:

                tool_result = {
                    "status": "validation_error",

                    "message": (
                        "工具调用未执行，"
                        "因为参数验证失败。"
                    ),

                    "errors":
                        validation["errors"],

                    "instruction": (
                        "不要猜测缺失的参数。"
                        "如果缺少用户必须明确提供的参数，"
                        "请向用户询问。"
                    ),
                }


            else:

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