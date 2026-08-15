import json
import re
from pathlib import Path

import openai
from openai import OpenAI

from day04.day04_sumo_metrics import (
    run_sumo_metrics,
)


# ============================================================
# 1. 项目路径
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# ============================================================
# 2. 场景注册表
#
# Agent 不直接让 LLM 随便生成文件路径。
# LLM 只需要选择场景名称。
# Python Runtime 再把场景名称映射到真实文件。
# ============================================================

SCENARIO_MAP = {

    "cross":
        PROJECT_ROOT
        / "sumotest"
        / "cross.sumocfg",
}
METRIC_DEFINITIONS = {

    "average_queue": (
        "监测进口车道每个仿真步的"
        "停车车辆数之和，"
        "再对所有仿真时间步取平均。"
        "单位为 veh。"
    ),

    "mean_network_waiting_time": (
        "每个仿真时间步，"
        "将所有监测进口车道上车辆当前 waiting time "
        "求和，得到该时间步的网络等待状态量，"
        "再对所有仿真时间步取平均。"
        "它是时间平均的网络级状态指标，"
        "不是平均每辆车等待时间。"
        "单位为 s。"
    ),

    "mean_vehicle_waiting_time": (
        "记录仿真观察窗口内所有曾出现在"
        "监测进口车道上的车辆，"
        "累计每辆车在监测进口车道内处于等待状态的时间，"
        "将所有车辆累计等待时间求和后，"
        "除以 observed_vehicle_count。"
        "包括仿真结束时尚未完成行程的车辆。"
        "单位为 s/veh。"
    ),

    "throughput": (
        "仿真期间累计完成路线并离开网络的车辆数，"
        "即累计 arrived 数。"
        "单位为 veh。"
    ),

    "completion_rate": (
        "仿真观察窗口内累计 arrived "
        "除以累计 departed。"
        "它表示有限观察窗口内的完成比例。"
    ),
}

# ============================================================
# 3. 读取 API Key
# ============================================================

API_KEY_PATH = (
    PROJECT_ROOT
    / "api.txt"
)


api_key = (
    API_KEY_PATH
    .read_text(
        encoding="utf-8"
    )
    .strip()
)


client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# ============================================================
# 4. Tool Schema
# ============================================================

TOOLS = [

    {
        "type": "function",

        "function": {

            "name":
                "run_sumo_experiment",

            "description": (
                "运行一个真实的 SUMO 交通仿真实验，"
                "并返回交通性能指标。"
                "只有当用户明确要求运行、执行、测试"
                "或分析一个 SUMO 仿真实验时才使用。"
            ),

            "parameters": {

                "type": "object",

                "properties": {


                    # ========================================
                    # scenario
                    # ========================================

                    "scenario": {

                        "type": "string",

                        "enum": [
                            "cross",
                        ],

                        "description": (
                            "需要运行的 SUMO 场景名称。"
                            "当前支持 cross。"
                        ),
                    },


                    # ========================================
                    # seed
                    # ========================================

                    "seed": {

                        "type": "integer",

                        "description": (
                            "SUMO 随机种子。"
                            "必须由用户明确提供，"
                            "不得由模型自行猜测或生成。"
                        ),
                    },


                    # ========================================
                    # duration
                    # ========================================

                    "duration": {

                        "type": "integer",

                        "description": (
                            "仿真时长，单位秒。"
                        ),
                    },
                },


                "required": [
                    "scenario",
                    "seed",
                    "duration",
                ],
            },
        },
    },
]


# ============================================================
# 5. Tool Map
#
# 注意：
# 这里以后还会添加更多 Tool。
# ============================================================

TOOL_MAP = {}


# ============================================================
# 6. 从用户自然语言中提取 seed
#
# 用于检查：
# LLM 有没有偷偷修改用户提供的 seed。
# ============================================================

def extract_seed_from_user_query(
    user_query: str,
) -> int | None:

    patterns = [

        r"seed\s*"
        r"(?:=|:|为|是|用|使用)?\s*"
        r"(-?\d+)",

        r"(?:随机种子|种子)\s*"
        r"(?:=|:|为|是|用|使用)?\s*"
        r"(-?\d+)",
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            user_query,
            re.IGNORECASE,
        )


        if match:

            return int(
                match.group(1)
            )


    return None


# ============================================================
# 7. Tool Arguments JSON Parsing
# ============================================================

def parse_tool_arguments(
    raw_arguments: str,
) -> dict:

    try:

        arguments = json.loads(
            raw_arguments
        )


    except json.JSONDecodeError as e:

        return {

            "success":
                False,

            "arguments":
                None,

            "error": (
                "Tool Arguments JSON "
                f"解析失败：{e}"
            ),
        }


    if not isinstance(
        arguments,
        dict,
    ):

        return {

            "success":
                False,

            "arguments":
                None,

            "error": (
                "Tool Arguments 必须解析为 "
                "JSON object。"
            ),
        }


    return {

        "success":
            True,

        "arguments":
            arguments,

        "error":
            None,
    }


# ============================================================
# 8. Tool Arguments Validation
# ============================================================

def validate_tool_arguments(
    tool_name: str,
    arguments: dict,
    user_query: str,
) -> dict:

    errors = []


    # ========================================================
    # 8.1 Tool 是否存在
    # ========================================================

    if (
        tool_name
        != "run_sumo_experiment"
    ):

        errors.append(
            f"未知工具：{tool_name}"
        )

        return {

            "valid":
                False,

            "errors":
                errors,
        }


    # ========================================================
    # 8.2 未知参数
    # ========================================================

    allowed_arguments = {

        "scenario",
        "seed",
        "duration",
    }


    unknown_arguments = (
        set(
            arguments.keys()
        )
        - allowed_arguments
    )


    if unknown_arguments:

        errors.append(
            "出现未定义参数："
            + ", ".join(
                sorted(
                    unknown_arguments
                )
            )
        )


    # ========================================================
    # 8.3 scenario
    # ========================================================

    scenario = arguments.get(
        "scenario"
    )


    if scenario is None:

        errors.append(
            "缺少必要参数 scenario"
        )


    elif not isinstance(
        scenario,
        str,
    ):

        errors.append(
            "scenario 必须是字符串"
        )


    elif (
        scenario
        not in SCENARIO_MAP
    ):

        errors.append(
            f"不支持的 scenario："
            f"{scenario}"
        )


    # ========================================================
    # 8.4 seed
    # ========================================================

    seed = arguments.get(
        "seed"
    )


    if seed is None:

        errors.append(
            "缺少必要参数 seed"
        )


    elif (
        not isinstance(
            seed,
            int,
        )
        or isinstance(
            seed,
            bool,
        )
    ):

        errors.append(
            "seed 必须是整数"
        )


    elif seed < 0:

        errors.append(
            "seed 必须 >= 0"
        )


    # ========================================================
    # 8.5 seed 来源验证
    # ========================================================

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
        isinstance(
            seed,
            int,
        )
        and not isinstance(
            seed,
            bool,
        )
        and seed != user_seed
    ):

        errors.append(
            f"seed 与用户输入不一致："
            f"用户提供 {user_seed}，"
            f"模型生成 {seed}"
        )


    # ========================================================
    # 8.6 duration
    # ========================================================

    duration = arguments.get(
        "duration"
    )


    if duration is None:

        errors.append(
            "缺少必要参数 duration"
        )


    elif (
        not isinstance(
            duration,
            int,
        )
        or isinstance(
            duration,
            bool,
        )
    ):

        errors.append(
            "duration 必须是整数"
        )


    elif duration <= 0:

        errors.append(
            "duration 必须 > 0"
        )


    # ========================================================
    # 8.7 场景文件是否真实存在
    # ========================================================

    if (
        isinstance(
            scenario,
            str,
        )
        and scenario
        in SCENARIO_MAP
    ):

        scenario_path = (
            SCENARIO_MAP[
                scenario
            ]
        )


        if not scenario_path.exists():

            errors.append(
                "场景配置文件不存在："
                f"{scenario_path}"
            )


    # ========================================================
    # 8.8 返回 Validation
    # ========================================================

    return {

        "valid":
            len(errors) == 0,

        "errors":
            errors,
    }


# ============================================================
# 9. 真实 SUMO Tool
#
# 这是 Day 4 Part 3 的核心。
#
# LLM 只知道：
#
# scenario="cross"
#
# Python Runtime 再将 cross 映射成：
#
# sumotest/cross.sumocfg
#
# 最后调用真正的 run_sumo_metrics()
# ============================================================

def run_sumo_experiment(
    scenario: str,
    seed: int,
    duration: int,
) -> dict:

    scenario_path = (
        SCENARIO_MAP[
            scenario
        ]
    )


    print(
        "\n===== Real SUMO Experiment ====="
    )

    print(
        "Scenario:",
        scenario,
    )

    print(
        "SUMO Config:",
        scenario_path,
    )

    print(
        "Seed:",
        seed,
    )

    print(
        "Duration:",
        duration,
    )


    result = run_sumo_metrics(

        sumocfg_path=str(
            scenario_path
        ),

        duration=duration,

        seed=seed,
    )


    # 给结果补充场景名称
    if (
        result.get("status")
        == "success"
    ):

        result[
            "simulation_config"
        ][
            "scenario"
        ] = scenario


    return result


# Tool Map
TOOL_MAP[
    "run_sumo_experiment"
] = run_sumo_experiment


# ============================================================
# 10. 执行 Tool
# ============================================================

def execute_tool(
    tool_name: str,
    arguments: dict,
) -> dict:

    try:

        tool_function = (
            TOOL_MAP[
                tool_name
            ]
        )


        result = tool_function(
            **arguments
        )


        return result


    except Exception as e:

        return {

            "status":
                "tool_execution_error",

            "tool_name":
                tool_name,

            "error_type":
                type(e).__name__,

            "message":
                str(e),
        }


# ============================================================
# 11. 调用 LLM
# ============================================================

def call_model(
    messages: list,
) -> dict:

    try:

        response = (
            client
            .chat
            .completions
            .create(

                model=
                    "deepseek-v4-flash",

                messages=
                    messages,

                tools=
                    TOOLS,

                tool_choice=
                    "auto",

                max_tokens=
                    1500,

                extra_body={
                    "thinking": {
                        "type":
                            "disabled"
                    }
                },
            )
        )


        return {

            "status":
                "success",

            "response":
                response,
        }


    except openai.APIConnectionError as e:

        return {

            "status":
                "api_error",

            "error_type":
                "APIConnectionError",

            "message":
                str(e),
        }


    except openai.RateLimitError as e:

        return {

            "status":
                "api_error",

            "error_type":
                "RateLimitError",

            "message":
                str(e),
        }


    except openai.APIStatusError as e:

        return {

            "status":
                "api_error",

            "error_type":
                "APIStatusError",

            "status_code":
                e.status_code,

            "message":
                str(e),
        }


    except Exception as e:

        return {

            "status":
                "unexpected_error",

            "error_type":
                type(e).__name__,

            "message":
                str(e),
        }


# ============================================================
# 12. Agent Loop
# ============================================================

def run_agent(
    user_query: str,
    max_steps: int = 10,
) -> str:

    # ========================================================
    # System Prompt
    # ========================================================
    metric_definition_text = (
        "\n".join(
            [
                f"- {name}: {definition}"
                for name, definition
                in METRIC_DEFINITIONS.items()
            ]
        )
    )
    messages = [

        {
            "role": "system",

            "content": (
                "你是一个 Traffic Simulation Agent。"

                "你可以通过工具运行真实的 SUMO "
                "交通仿真实验。"

                "当前可用场景只有 cross。"

                "运行实验必须获得用户明确提供的 seed "
                "和 duration。"

                "seed 必须是大于等于0的整数。"

                "不得自行猜测或生成 seed。"

                "如果用户没有提供必要参数，"
                "应直接向用户询问，而不是调用工具。"

                "如果工具返回 validation_error，"
                "应根据错误信息向用户请求或修正参数，"
                "不要猜测缺失参数。"

                "如果工具返回 argument_parse_error，"
                "说明工具参数 JSON 格式错误，"
                "应重新生成符合 Tool Schema 的参数。"

                "如果工具返回 tool_execution_error "
                "或 sumo_execution_error，"
                "说明真实仿真实验执行失败。"
                "不得把失败当作实验结果。"

                "如果工具返回真实 SUMO 实验结果，"
                "必须明确说明数据来源是真实 SUMO 仿真，"
                "不得称为 Mock 数据。"

                "以下指标定义是当前项目的正式定义，"
                "无论是否调用工具，都必须严格按照这些定义解释，"
                "不得自行替换成其他交通工程定义：\n"

                f"{metric_definition_text}\n"

                "不要根据指标虚构交通拥堵原因。"
                "如果结果只能说明现象，就只说明现象。"
            ),
        },


        {
            "role":
                "user",

            "content":
                user_query,
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


        # ====================================================
        # 12.1 调用模型
        # ====================================================

        model_result = (
            call_model(
                messages
            )
        )


        print(
            "Model Call Status:",
            model_result[
                "status"
            ],
        )


        if (
            model_result[
                "status"
            ]
            != "success"
        ):

            return (
                "模型调用失败。\n"
                f"错误类型："
                f"{model_result.get('error_type')}\n"
                f"错误信息："
                f"{model_result.get('message')}"
            )


        response = (
            model_result[
                "response"
            ]
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
            repr(
                message.content
            ),
        )

        print(
            "Tool Calls:",
            message.tool_calls,
        )


        # ====================================================
        # 12.2 如果没有 Tool Call
        #      Agent结束
        # ====================================================

        if not message.tool_calls:

            return (
                message.content
                or ""
            )


        # ====================================================
        # 12.3 把 assistant tool_calls
        #      加入 messages
        # ====================================================

        messages.append(
            {
                "role":
                    "assistant",

                "content":
                    message.content,

                "tool_calls": [

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

                    for tool_call
                    in message.tool_calls
                ],
            }
        )


        # ====================================================
        # 12.4 执行所有 Tool Calls
        # ====================================================

        for tool_call in (
            message.tool_calls
        ):

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


            # ================================================
            # Parse
            # ================================================

            parse_result = (
                parse_tool_arguments(
                    raw_arguments
                )
            )


            print(
                "Parse Result:",
                parse_result,
            )


            if not parse_result[
                "success"
            ]:

                tool_result = {

                    "status":
                        "argument_parse_error",

                    "message": (
                        "工具参数解析失败，"
                        "本次工具没有执行。"
                    ),

                    "error":
                        parse_result[
                            "error"
                        ],

                    "instruction": (
                        "请重新生成符合 "
                        "Tool Schema 的合法 "
                        "JSON 参数。"
                    ),
                }


                messages.append(
                    {
                        "role":
                            "tool",

                        "tool_call_id":
                            tool_call.id,

                        "content":
                            json.dumps(
                                tool_result,
                                ensure_ascii=False,
                            ),
                    }
                )


                continue


            arguments = (
                parse_result[
                    "arguments"
                ]
            )


            print(
                "Parsed Arguments:",
                arguments,
            )


            # ================================================
            # Validation
            # ================================================

            validation = (
                validate_tool_arguments(

                    tool_name=
                        tool_name,

                    arguments=
                        arguments,

                    user_query=
                        user_query,
                )
            )


            print(
                "Validation:",
                validation,
            )


            if not validation[
                "valid"
            ]:

                tool_result = {

                    "status":
                        "validation_error",

                    "message": (
                        "工具调用未执行，"
                        "因为参数验证失败。"
                    ),

                    "errors":
                        validation[
                            "errors"
                        ],

                    "instruction": (
                        "不要猜测缺失参数。"
                        "如果参数需要由用户明确提供，"
                        "请向用户询问。"
                    ),
                }


            else:

                # ============================================
                # 真正执行 SUMO Tool
                # ============================================

                tool_result = (
                    execute_tool(
                        tool_name=
                            tool_name,

                        arguments=
                            arguments,
                    )
                )


            print(
                "Tool Result:",
                tool_result,
            )


            # ================================================
            # Tool Result → messages
            # ================================================

            messages.append(
                {
                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps(
                            tool_result,
                            ensure_ascii=False,
                        ),
                }
            )


    # ========================================================
    # max_steps
    # ========================================================

    return (
        "Agent 达到最大执行步骤，"
        "任务未能正常结束。"
    )


# ============================================================
# 13. 程序入口
# ============================================================

if __name__ == "__main__":

    user_query = input(
        "\nUser: "
    )


    final_answer = (
        run_agent(
            user_query
        )
    )


    print(
        "\n===== Final Answer ====="
    )

    print(
        final_answer
    )