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
# 2. 导入已经通过的 Batch Runner
# ============================================================

from day05.day05_batch_runner import (
    run_batch_experiment,
)


# ============================================================
# 3. 当前支持场景
# ============================================================

SUPPORTED_SCENARIOS = {
    "cross",
}


# ============================================================
# 4. 项目指标定义
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
        "然后将所有车辆累计等待时间求和，"
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
# 6. Tool Schema
#
# 注意：
#
# Tool 本身仍然只是：
#
# run_batch_sumo_experiment(
#     scenario,
#     seeds,
#     duration,
# )
#
# initial / extra 的概念属于 Agent Task，
# 而不是 Batch Tool 本身。
# ============================================================

TOOLS = [

    {
        "type": "function",

        "function": {

            "name":
                "run_batch_sumo_experiment",

            "description": (
                "针对同一个 SUMO 场景，"
                "使用一组用户明确批准的随机种子"
                "运行多次真实 SUMO 实验，"
                "并由 Python 自动计算"
                "mean、sample std、min 和 max。"
                "动态实验中，每次调用只能执行"
                "当前阶段允许的一组 seeds。"
            ),

            "parameters": {

                "type": "object",

                "properties": {

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


                    "seeds": {

                        "type": "array",

                        "items": {
                            "type": "integer"
                        },

                        "description": (
                            "本轮 Batch Experiment "
                            "需要执行的随机种子列表。"
                            "必须来自用户明确批准的 seed 组，"
                            "不得自行创建、增加、删除或修改。"
                        ),
                    },


                    "duration": {

                        "type": "integer",

                        "description": (
                            "本轮每个 seed 的仿真时长，"
                            "单位为秒。"
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
# 8. 提取指定名称的 seed group
#
# 支持：
#
# initial_seeds=42、43、44
# extra_seeds=45、46、47
#
# ============================================================

def extract_named_seed_group(
    user_query: str,
    group_name: str,
) -> list[int] | None:

    pattern = (
        rf"{re.escape(group_name)}"
        r"\s*"
        r"(?:=|:|为|是)?"
        r"\s*"
        r"([-0-9,\s、，]+)"
    )


    match = re.search(
        pattern,
        user_query,
        re.IGNORECASE,
    )


    if not match:

        return None


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

        return None


    return [

        int(value)

        for value
        in seed_strings
    ]


# ============================================================
# 9. 提取 duration
# ============================================================

def extract_duration_from_user_query(
    user_query: str,
) -> int | None:

    patterns = [

        (
            r"duration\s*"
            r"(?:=|:|为|是)?\s*"
            r"(\d+)"
        ),

        (
            r"(?:每个|每次|运行|仿真时长|时长)"
            r"\s*(\d+)\s*秒"
        ),

        (
            r"(\d+)\s*秒"
        ),
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
# 10. 提取 average_queue sample std 阈值
#
# 支持例如：
#
# average_queue 的 sample std > 0.08
# average_queue 标准差 > 0.08
#
# ============================================================

def extract_queue_std_threshold(
    user_query: str,
) -> float | None:

    patterns = [

        (
            r"average_queue"
            r".*?"
            r"(?:sample\s*)?std"
            r"\s*>\s*"
            r"(\d+(?:\.\d+)?)"
        ),

        (
            r"average_queue"
            r".*?"
            r"(?:样本)?标准差"
            r"\s*>\s*"
            r"(\d+(?:\.\d+)?)"
        ),
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            user_query,
            re.IGNORECASE
            | re.DOTALL,
        )


        if match:

            return float(
                match.group(1)
            )


    return None


# ============================================================
# 11. Tool Arguments Parsing
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
# 12. Runtime Validation
#
# Part 4 的核心升级之一。
#
# 除了验证：
#
# - 类型
# - 合法性
# - 来源
#
# 还要验证：
#
# - 当前到底应该运行 initial 还是 extra？
# - extra 是否真的满足触发条件？
#
# ============================================================

def validate_tool_arguments(
    tool_name: str,
    arguments: dict,
    user_query: str,
    dynamic_state: dict,
) -> dict:

    errors = []


    # ========================================================
    # 12.1 Tool Name
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
    # 12.2 Unknown Arguments
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
    # 12.3 Scenario
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
    # 12.4 Seeds 基础检查
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
    # 12.5 从用户请求读取两组 seed
    # ========================================================

    initial_seeds = (
        extract_named_seed_group(
            user_query,
            "initial_seeds",
        )
    )


    extra_seeds = (
        extract_named_seed_group(
            user_query,
            "extra_seeds",
        )
    )


    if initial_seeds is None:

        errors.append(
            "用户没有明确提供 initial_seeds。"
        )


    if extra_seeds is None:

        errors.append(
            "用户没有明确提供 extra_seeds。"
        )


    # ========================================================
    # 12.6 动态阶段 Validation
    #
    # Stage 1:
    # 必须运行 initial_seeds
    #
    # Stage 2:
    # 只有满足 threshold 条件后
    # 才允许运行 extra_seeds
    #
    # ========================================================

    if (
        isinstance(seeds, list)
        and all(
            isinstance(seed, int)
            and not isinstance(seed, bool)
            for seed in seeds
        )
        and initial_seeds is not None
        and extra_seeds is not None
    ):

        tool_seed_group = (
            sorted(seeds)
        )


        expected_initial_group = (
            sorted(
                initial_seeds
            )
        )


        expected_extra_group = (
            sorted(
                extra_seeds
            )
        )


        # ----------------------------------------------------
        # Initial 尚未执行
        # ----------------------------------------------------

        if not dynamic_state[
            "initial_completed"
        ]:

            if (
                tool_seed_group
                != expected_initial_group
            ):

                errors.append(
                    "第一轮必须只运行 "
                    "用户提供的 initial_seeds。"
                    f"用户 initial_seeds="
                    f"{initial_seeds}，"
                    f"Tool 生成 seeds={seeds}"
                )


        # ----------------------------------------------------
        # Initial 已执行
        # ----------------------------------------------------

        else:

            # extra 已经执行过
            if dynamic_state[
                "extra_completed"
            ]:

                errors.append(
                    "extra_seeds 已经执行完成，"
                    "不得重复运行第二轮实验。"
                )


            else:

                initial_queue_std = (
                    dynamic_state[
                        "initial_queue_std"
                    ]
                )


                threshold = (
                    dynamic_state[
                        "threshold"
                    ]
                )


                # --------------------------------------------
                # 没有可靠第一轮统计
                # --------------------------------------------

                if initial_queue_std is None:

                    errors.append(
                        "第一轮没有可用的 "
                        "average_queue std，"
                        "不能启动 extra_seeds。"
                    )


                elif threshold is None:

                    errors.append(
                        "用户没有提供有效的 "
                        "average_queue std 判断阈值。"
                    )


                # --------------------------------------------
                # 条件满足
                # --------------------------------------------

                elif (
                    initial_queue_std
                    > threshold
                ):

                    if (
                        tool_seed_group
                        != expected_extra_group
                    ):

                        errors.append(
                            "触发第二轮后，"
                            "只能运行用户提供的 "
                            "extra_seeds。"
                            f"用户 extra_seeds="
                            f"{extra_seeds}，"
                            f"Tool 生成 seeds={seeds}"
                        )


                # --------------------------------------------
                # 条件不满足
                # --------------------------------------------

                else:

                    errors.append(
                        "当前不满足第二轮触发条件："
                        f"第一轮 average_queue std="
                        f"{initial_queue_std}，"
                        f"threshold={threshold}，"
                        "因为 std <= threshold，"
                        "不允许运行 extra_seeds。"
                    )


    # ========================================================
    # 12.7 Duration
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
    # 12.8 Duration 来源检查
    # ========================================================

    user_duration = (
        extract_duration_from_user_query(
            user_query
        )
    )


    if user_duration is None:

        errors.append(
            "用户没有明确提供 duration。"
        )


    elif (
        isinstance(duration, int)
        and not isinstance(duration, bool)
        and duration != user_duration
    ):

        errors.append(
            "duration 与用户输入不一致："
            f"用户提供 {user_duration}，"
            f"Tool 生成 {duration}"
        )


    # ========================================================
    # 12.9 Return
    # ========================================================

    return {

        "valid":
            len(errors) == 0,

        "errors":
            errors,
    }


# ============================================================
# 13. Batch Tool Wrapper
# ============================================================

def run_batch_sumo_experiment(
    scenario: str,
    seeds: list[int],
    duration: int,
) -> dict:

    print(
        "\n===================================="
    )

    print(
        "Dynamic Agent → Real Batch SUMO Tool"
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
# 14. Execute Tool
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
# 15. Call Model
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
                    2500,

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
# 16. 更新 Dynamic State
#
# Tool真正执行完成后，
# Runtime记录目前进行到哪一步。
# ============================================================

def update_dynamic_state(
    dynamic_state: dict,
    arguments: dict,
    tool_result: dict,
    user_query: str,
) -> None:

    # --------------------------------------------------------
    # 实验失败，不推进阶段
    # --------------------------------------------------------

    if (
        tool_result.get("status")
        != "success"
    ):

        return


    seeds = arguments.get(
        "seeds"
    )


    if not isinstance(
        seeds,
        list,
    ):

        return


    initial_seeds = (
        extract_named_seed_group(
            user_query,
            "initial_seeds",
        )
    )


    extra_seeds = (
        extract_named_seed_group(
            user_query,
            "extra_seeds",
        )
    )


    # ========================================================
    # Initial Batch 完成
    # ========================================================

    if (
        initial_seeds is not None
        and sorted(seeds)
        == sorted(initial_seeds)
    ):

        dynamic_state[
            "initial_completed"
        ] = True


        queue_statistics = (
            tool_result
            .get(
                "aggregated_metrics",
                {}
            )
            .get(
                "average_queue",
                {}
            )
        )


        dynamic_state[
            "initial_queue_std"
        ] = (
            queue_statistics
            .get(
                "std"
            )
        )


        print(
            "\n===== Dynamic State Updated ====="
        )

        print(
            "Initial Completed:",
            True,
        )

        print(
            "Initial average_queue std:",
            dynamic_state[
                "initial_queue_std"
            ],
        )

        print(
            "Threshold:",
            dynamic_state[
                "threshold"
            ],
        )


    # ========================================================
    # Extra Batch 完成
    # ========================================================

    elif (
        extra_seeds is not None
        and sorted(seeds)
        == sorted(extra_seeds)
    ):

        dynamic_state[
            "extra_completed"
        ] = True


        print(
            "\n===== Dynamic State Updated ====="
        )

        print(
            "Extra Completed:",
            True,
        )


# ============================================================
# 17. Agent Loop
# ============================================================

def run_agent(
    user_query: str,
    max_steps: int = 10,
) -> str:

    # ========================================================
    # 17.1 从用户任务中提取动态配置
    # ========================================================

    initial_seeds = (
        extract_named_seed_group(
            user_query,
            "initial_seeds",
        )
    )


    extra_seeds = (
        extract_named_seed_group(
            user_query,
            "extra_seeds",
        )
    )


    threshold = (
        extract_queue_std_threshold(
            user_query
        )
    )


    duration = (
        extract_duration_from_user_query(
            user_query
        )
    )


    print(
        "\n===== Parsed Dynamic Task ====="
    )

    print(
        "Initial Seeds:",
        initial_seeds,
    )

    print(
        "Extra Seeds:",
        extra_seeds,
    )

    print(
        "Queue Std Threshold:",
        threshold,
    )

    print(
        "Duration:",
        duration,
    )


    # ========================================================
    # 17.2 Dynamic State
    #
    # 这是 Runtime 内部状态，
    # 和 messages 不完全是一回事。
    #
    # messages:
    #   给 LLM 看
    #
    # dynamic_state:
    #   Runtime 自己用于控制和验证
    # ========================================================

    dynamic_state = {

        "initial_completed":
            False,

        "initial_queue_std":
            None,

        "extra_completed":
            False,

        "threshold":
            threshold,
    }


    # ========================================================
    # 17.3 Metric Definitions
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
    # 17.4 System Prompt
    # ========================================================

    messages = [

        {

            "role":
                "system",

            "content": (

                "你是一个 Traffic Simulation Agent V1。"

                "你可以通过 Batch Tool 运行真实的 "
                "SUMO 多 seed 实验。"

                "当前支持动态两阶段实验。"

                "用户会明确提供："
                "initial_seeds、extra_seeds、duration，"
                "以及 average_queue sample std 的判断阈值。"

                "你必须严格执行以下动态规则："

                "第一步只能运行 initial_seeds。"

                "禁止第一轮同时运行 initial_seeds "
                "和 extra_seeds。"

                "第一轮 Tool Result 返回后，"
                "读取 aggregated_metrics 中 "
                "average_queue 的 std。"

                "如果第一轮 average_queue std "
                "严格大于用户提供的 threshold，"
                "你必须继续调用 Batch Tool，"
                "并且第二轮只能使用 extra_seeds。"

                "如果第一轮 average_queue std "
                "小于或等于 threshold，"
                "不得运行 extra_seeds，"
                "应直接给出最终回答。"

                "不得自行创建新的 seed。"

                "不得增加、删除或修改"
                "用户提供的 seed。"

                "不得修改用户提供的 threshold。"

                "不得自行修改 duration。"

                "每一次模型决策应基于"
                "此前真实 Tool Result。"

                "第二轮是否运行，"
                "必须根据第一轮结果决定，"
                "不能在第一轮结果产生之前"
                "提前决定。"

                "如果工具返回 validation_error，"
                "必须遵守 Runtime Validation，"
                "不得绕过。"

                "如果工具返回 tool_execution_error、"
                "batch_execution_error 或 partial_success，"
                "必须如实说明实验执行状态。"

                "mean、std、min、max "
                "均由 Python 确定性计算。"
                "不得重新计算或修改 Python 给出的统计值。"

                "当前 std 为 statistics.stdev "
                "计算的样本标准差。"

                "如果执行第二轮，"
                "最终回答应明确说明："
                "第一轮结果、threshold、"
                "为什么触发第二轮、"
                "第二轮结果。"

                "目前没有 Python 提供"
                "两轮合并后的总体统计。"
                "因此不得自行把 initial 和 extra "
                "六个 seed 合并后计算新的 mean/std。"

                "只能分别报告两轮"
                "Python 已提供的统计结果。"

                "如果只使用少量 seed，"
                "可以描述观察到的波动，"
                "不得声称具有统计显著性或高鲁棒性。"

                "不要根据这些性能指标"
                "虚构交通拥堵的具体原因。"

                "seed 只影响场景中实际使用随机数的过程。"
                "不得未经证据声称某个具体模块"
                "一定受到 seed 影响。"

                "必须严格遵循以下指标定义：\n"

                f"{metric_definition_text}\n"

                "真实实验的数据来源必须明确说明为 SUMO。"
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
    # 17.5 Agent Loop
    # ========================================================

    for step in range(
        1,
        max_steps + 1,
    ):

        print(
            f"\n===== Agent Step {step} ====="
        )


        # ====================================================
        # 调用 LLM
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
        # No Tool Call → Agent结束
        # ====================================================

        if not message.tool_calls:

            return (
                message.content
                or ""
            )


        # ====================================================
        # Assistant Tool Calls → Messages
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
        # 执行 Tool Calls
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
                        "Tool Arguments JSON "
                        "解析失败，"
                        "本次实验未执行。"
                    ),

                    "error":
                        parse_result[
                            "error"
                        ],

                    "instruction": (
                        "请重新生成符合 "
                        "Tool Schema 的参数。"
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
            # Dynamic Runtime Validation
            # ================================================

            validation = (
                validate_tool_arguments(

                    tool_name=
                        tool_name,

                    arguments=
                        arguments,

                    user_query=
                        user_query,

                    dynamic_state=
                        dynamic_state,
                )
            )


            print(
                "Validation:",
                validation,
            )


            # ================================================
            # Validation Failed
            # ================================================

            if not validation[
                "valid"
            ]:

                tool_result = {

                    "status":
                        "validation_error",

                    "message": (
                        "Dynamic Batch Tool 未执行，"
                        "因为 Runtime Validation "
                        "验证失败。"
                    ),

                    "errors":
                        validation[
                            "errors"
                        ],

                    "instruction": (
                        "必须严格遵守用户提供的"
                        " initial_seeds、extra_seeds、"
                        "threshold 和 duration，"
                        "不得绕过动态实验规则。"
                    ),
                }


            # ================================================
            # Validation PASS → Real SUMO
            # ================================================

            else:

                tool_result = (
                    execute_tool(

                        tool_name=
                            tool_name,

                        arguments=
                            arguments,
                    )
                )


                # ============================================
                # Tool完成后更新 Runtime状态
                # ============================================

                update_dynamic_state(

                    dynamic_state=
                        dynamic_state,

                    arguments=
                        arguments,

                    tool_result=
                        tool_result,

                    user_query=
                        user_query,
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
    # max_steps Guard
    # ========================================================

    return (
        "Agent 达到最大执行步骤，"
        "任务未能正常结束。"
    )


# ============================================================
# 18. Main
# ============================================================

if __name__ == "__main__":

    print(
        "\n===================================="
    )

    print(
        "Traffic Simulation Agent V1"
    )

    print(
        "Day 5 Part 4 - Dynamic Decision"
    )

    print(
        "===================================="
    )


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