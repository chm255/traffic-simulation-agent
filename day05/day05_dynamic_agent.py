import json
import re
import sys
from pathlib import Path

import openai
from openai import OpenAI


# ============================================================
# 1. 项目根目录
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# ============================================================
# 2. 导入 Day 5 Batch Runner
# ============================================================

from day05.day05_batch_runner import (
    run_batch_experiment,
)


# ============================================================
# 3. 场景
# ============================================================

SUPPORTED_SCENARIOS = {
    "cross",
}


# ============================================================
# 4. 当前项目指标定义
# ============================================================

METRIC_DEFINITIONS = {

    "average_queue": (
        "监测进口车道每个仿真步的停车车辆数之和，"
        "再对所有仿真时间步取平均。"
        "单位为 veh。"
    ),

    "mean_network_waiting_time": (
        "每个仿真时间步，将所有监测进口车道上"
        "车辆当前 waiting time 求和，"
        "得到该时间步的网络等待状态量，"
        "再对所有仿真时间步取平均。"
        "它不是平均每辆车等待时间。"
        "单位为 s。"
    ),

    "mean_vehicle_waiting_time": (
        "记录观察窗口内所有曾出现在监测进口车道上的车辆，"
        "累计每辆车在监测进口车道内处于等待状态的时间，"
        "然后将总累计等待时间除以 observed_vehicle_count。"
        "包括仿真结束时尚未完成行程的车辆。"
        "单位为 s/veh。"
    ),

    "throughput": (
        "仿真期间累计完成路线并离开网络的车辆数，"
        "即累计 arrived 数。"
        "单位为 veh。"
    ),

    "completion_rate": (
        "有限仿真观察窗口内累计 arrived "
        "除以累计 departed。"
        "单位为 ratio。"
    ),
}


# ============================================================
# 5. API Key
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
# 6. Batch Tool Schema
# ============================================================

TOOLS = [

    {
        "type": "function",

        "function": {

            "name":
                "run_batch_sumo_experiment",

            "description": (
                "针对同一个 SUMO 场景，"
                "使用多个用户明确提供的随机种子"
                "运行多次真实 SUMO 仿真实验，"
                "并由 Python 自动汇总每个 seed 的结果，"
                "计算 mean、sample std、min 和 max。"
                "当用户要求运行多个 seeds、"
                "批量实验、稳定性分析或重复实验时使用。"
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
                            "SUMO 场景名称。"
                            "当前仅支持 cross。"
                        ),
                    },


                    # ========================================
                    # seeds
                    # ========================================

                    "seeds": {

                        "type": "array",

                        "items": {
                            "type": "integer"
                        },

                        "description": (
                            "需要运行的随机种子列表。"
                            "每个 seed 必须由用户明确提供，"
                            "不得由模型自行补充或生成。"
                            "例如 [42, 43, 44]。"
                        ),
                    },


                    # ========================================
                    # duration
                    # ========================================

                    "duration": {

                        "type": "integer",

                        "description": (
                            "每一个 seed 对应的"
                            "SUMO 仿真时长，单位秒。"
                        ),
                    },
                },


                "required": [
                    "scenario",
                    "seeds",
                    "duration",
                ],
            },
        },
    },
]


# ============================================================
# 7. Tool Map
# ============================================================

TOOL_MAP = {}


# ============================================================
# 8. 从用户输入提取 seeds
#
# 当前教学版本支持：
#
# seeds=42,43,44
# seeds 42、43、44
# seed 42, 43, 44
# 随机种子 42、43、44
#
# 暂时不支持：
#
# seeds=42-44
# ============================================================

def extract_seeds_from_user_query(
    user_query: str,
) -> list[int] | None:

    patterns = [

        (
            r"(?:seeds?|随机种子|种子)"
            r"\s*"
            r"(?:=|:|为|是|使用)?"
            r"\s*"
            r"([-0-9,\s、，]+)"
        ),
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            user_query,
            re.IGNORECASE,
        )


        if not match:

            continue


        seed_text = (
            match.group(1)
        )


        seed_strings = (
            re.findall(
                r"-?\d+",
                seed_text,
            )
        )


        if not seed_strings:

            continue


        return [
            int(value)
            for value
            in seed_strings
        ]


    return None


# ============================================================
# 9. 从用户输入提取 duration
#
# 当前支持例如：
#
# duration=300
# 运行300秒
# 每个300秒
# 仿真时长300秒
# ============================================================

def extract_duration_from_user_query(
    user_query: str,
) -> int | None:

    patterns = [

        r"duration\s*"
        r"(?:=|:|为|是)?\s*"
        r"(\d+)",

        r"(?:每个|每次|运行|仿真时长|时长)"
        r"\s*(\d+)\s*秒",

        r"(\d+)\s*秒",
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
# 10. Parse Tool Arguments
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
# 11. Agent Runtime Validation
# ============================================================

def validate_tool_arguments(
    tool_name: str,
    arguments: dict,
    user_query: str,
) -> dict:

    errors = []


    # ========================================================
    # 11.1 Tool Name
    # ========================================================

    if (
        tool_name
        != "run_batch_sumo_experiment"
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
    # 11.2 Unknown Arguments
    # ========================================================

    allowed_arguments = {

        "scenario",
        "seeds",
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
    # 11.3 Scenario
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
        not in SUPPORTED_SCENARIOS
    ):

        errors.append(
            f"不支持的 scenario："
            f"{scenario}"
        )


    # ========================================================
    # 11.4 Seeds
    # ========================================================

    seeds = arguments.get(
        "seeds"
    )


    if seeds is None:

        errors.append(
            "缺少必要参数 seeds"
        )


    elif not isinstance(
        seeds,
        list,
    ):

        errors.append(
            "seeds 必须是列表"
        )


    elif len(seeds) == 0:

        errors.append(
            "seeds 不能为空"
        )


    else:

        for seed in seeds:

            if (
                not isinstance(seed, int)
                or isinstance(seed, bool)
            ):

                errors.append(
                    f"非法 seed：{seed}，"
                    "seed 必须是整数"
                )

                continue


            if seed < 0:

                errors.append(
                    f"非法 seed：{seed}，"
                    "seed 必须 >= 0"
                )


        if (
            len(seeds)
            != len(set(seeds))
        ):

            errors.append(
                "seeds 中存在重复值"
            )


    # ========================================================
    # 11.5 Seeds 来源验证
    # ========================================================

    user_seeds = (
        extract_seeds_from_user_query(
            user_query
        )
    )


    if user_seeds is None:

        errors.append(
            "用户没有明确提供 seeds。"
            "禁止模型自行生成随机种子列表。"
        )


    elif isinstance(
        seeds,
        list,
    ):

        # -----------------------------------------------
        # 不要求顺序完全一致。
        #
        # 用户 [42,43,44]
        # 模型 [44,42,43]
        #
        # 实验集合仍然相同。
        # -----------------------------------------------

        valid_seed_types = all(

            isinstance(seed, int)
            and not isinstance(seed, bool)

            for seed in seeds
        )


        if valid_seed_types:

            if (
                sorted(seeds)
                != sorted(user_seeds)
            ):

                errors.append(
                    "seeds 与用户输入不一致："
                    f"用户提供 {user_seeds}，"
                    f"模型生成 {seeds}"
                )


    # ========================================================
    # 11.6 Duration
    # ========================================================

    duration = arguments.get(
        "duration"
    )


    if duration is None:

        errors.append(
            "缺少必要参数 duration"
        )


    elif (
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


    # ========================================================
    # 11.7 Duration 来源验证
    # ========================================================

    user_duration = (
        extract_duration_from_user_query(
            user_query
        )
    )


    if user_duration is None:

        errors.append(
            "用户没有明确提供 duration。"
            "禁止模型自行生成仿真时长。"
        )


    elif (
        isinstance(duration, int)
        and not isinstance(duration, bool)
        and duration != user_duration
    ):

        errors.append(
            "duration 与用户输入不一致："
            f"用户提供 {user_duration}，"
            f"模型生成 {duration}"
        )


    # ========================================================
    # 11.8 Return
    # ========================================================

    return {

        "valid":
            len(errors) == 0,

        "errors":
            errors,
    }


# ============================================================
# 12. Batch Tool Wrapper
# ============================================================

def run_batch_sumo_experiment(
    scenario: str,
    seeds: list[int],
    duration: int,
) -> dict:

    """
    Agent Tool Wrapper。

    Agent 使用语义参数：
        scenario
        seeds
        duration

    真正的实验由：
        run_batch_experiment()

    负责。
    """

    print(
        "\n===================================="
    )

    print(
        "Real Batch SUMO Tool"
    )

    print(
        "===================================="
    )

    print(
        "Scenario:",
        scenario,
    )

    print(
        "Seeds:",
        seeds,
    )

    print(
        "Duration:",
        duration,
    )


    result = (
        run_batch_experiment(

            scenario=
                scenario,

            seeds=
                seeds,

            duration=
                duration,
        )
    )


    return result


TOOL_MAP[
    "run_batch_sumo_experiment"
] = run_batch_sumo_experiment


# ============================================================
# 13. Execute Tool
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


        return tool_function(
            **arguments
        )


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
# 14. Call Model
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
                    2000,

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
# 15. Agent Loop
# ============================================================

def run_agent(
    user_query: str,
    max_steps: int = 10,
) -> str:

    # ========================================================
    # 15.1 Metric Definitions → Prompt
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


    # ========================================================
    # 15.2 Messages
    # ========================================================

    messages = [

        {
            "role":
                "system",

            "content": (

                "你是一个 Traffic Simulation Agent。"

                "你可以通过工具运行真实的多 seed "
                "SUMO 批量交通仿真实验。"

                "当前可用场景只有 cross。"

                "批量实验必须获得用户明确提供的："
                "scenario、seeds 和 duration。"

                "不得自行添加、删除或修改用户的 seeds。"

                "不得自行猜测 duration。"

                "如果缺少必要参数，"
                "直接向用户询问，"
                "不要调用工具。"

                "如果用户只询问概念、指标含义或一般知识，"
                "不要调用 SUMO 工具。"

                "如果工具返回 validation_error，"
                "根据错误信息向用户说明，"
                "不得绕过验证。"

                "如果工具返回 tool_execution_error "
                "或 batch_execution_error，"
                "说明实验执行失败，"
                "不得将失败结果描述为成功。"

                "如果 status 为 partial_success，"
                "必须明确说明只有部分 seed 成功，"
                "并指出失败数量。"

                "工具返回的 mean、std、min、max "
                "均由 Python 确定性计算完成。"
                "不得自行重新计算或修改这些数值。"

                "当前 std 使用 statistics.stdev，"
                "即样本标准差。"

                "当 seed 数量很少时，"
                "可以描述观察到的波动，"
                "但不得仅凭少量 seed "
                "声称系统具有高鲁棒性或统计显著性。"

                "必须严格遵循以下项目指标定义：\n"

                f"{metric_definition_text}\n"

                "分析结果时区分事实与推断。"

                "可以描述："
                "哪个 seed 较高、较低，"
                "mean/std/range 如何，"
                "观察到的跨 seed 波动。"

                "不要根据这些指标虚构拥堵原因。"

                "真实实验结果的数据来源应明确说明为 SUMO。"
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
    # 15.3 Agent Loop
    # ========================================================

    for step in range(
        1,
        max_steps + 1,
    ):

        print(
            f"\n===== Agent Step {step} ====="
        )


        # ----------------------------------------------------
        # LLM
        # ----------------------------------------------------

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
        # 15.4 No Tool → Finish
        # ====================================================

        if not message.tool_calls:

            return (
                message.content
                or ""
            )


        # ====================================================
        # 15.5 Assistant Tool Calls → Messages
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
        # 15.6 Execute All Tool Calls
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
                        "工具参数 JSON 解析失败，"
                        "本次 Batch Tool 未执行。"
                    ),

                    "error":
                        parse_result[
                            "error"
                        ],

                    "instruction": (
                        "重新生成符合 "
                        "Tool Schema 的合法参数。"
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
                        "Batch Tool 未执行，"
                        "因为参数验证失败。"
                    ),

                    "errors":
                        validation[
                            "errors"
                        ],

                    "instruction": (
                        "不得猜测、添加或修改"
                        "用户未明确提供的实验参数。"
                    ),
                }


            else:

                # ============================================
                # Real Batch SUMO Experiment
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
                "\nTool Result:",
                tool_result,
            )


            # ================================================
            # Tool Result → Messages
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
# 16. Main
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