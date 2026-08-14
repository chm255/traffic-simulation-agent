import statistics
import sys
from pathlib import Path


# ============================================================
# 1. 项目根目录
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# 保证可以 import day04
if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from day04.day04_sumo_metrics import (
    run_sumo_metrics,
)


# ============================================================
# 2. 场景注册表
# ============================================================

SCENARIO_MAP = {

    "cross":
        PROJECT_ROOT
        / "sumotest"
        / "cross.sumocfg",
}


# ============================================================
# 3. 需要做跨 seed 汇总的指标
# ============================================================

AGGREGATED_METRICS = [

    "average_queue",

    "mean_network_waiting_time",

    "mean_vehicle_waiting_time",

    "throughput",

    "completion_rate",
]


# ============================================================
# 4. Batch Arguments Validation
# ============================================================

def validate_batch_arguments(
    scenario: str,
    seeds: list[int],
    duration: int,
) -> dict:

    errors = []


    # --------------------------------------------------------
    # scenario
    # --------------------------------------------------------

    if not isinstance(
        scenario,
        str,
    ):

        errors.append(
            "scenario 必须是字符串"
        )


    elif scenario not in SCENARIO_MAP:

        errors.append(
            f"不支持的 scenario：{scenario}"
        )


    else:

        scenario_path = (
            SCENARIO_MAP[
                scenario
            ]
        )


        if not scenario_path.exists():

            errors.append(
                "场景文件不存在："
                f"{scenario_path}"
            )


    # --------------------------------------------------------
    # seeds
    # --------------------------------------------------------

    if not isinstance(
        seeds,
        list,
    ):

        errors.append(
            "seeds 必须是 list"
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


        # 不允许重复 seed
        if (
            len(seeds)
            != len(set(seeds))
        ):

            errors.append(
                "seeds 中存在重复值"
            )


    # --------------------------------------------------------
    # duration
    # --------------------------------------------------------

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


    return {

        "valid":
            len(errors) == 0,

        "errors":
            errors,
    }


# ============================================================
# 5. 从单次实验结果中提取简洁指标
# ============================================================

def extract_run_metrics(
    result: dict,
) -> dict:

    metrics = result[
        "metrics"
    ]


    return {

        metric_name:
            metrics[
                metric_name
            ][
                "value"
            ]

        for metric_name
        in AGGREGATED_METRICS
    }


# ============================================================
# 6. 跨 seed 统计
# ============================================================

def aggregate_results(
    successful_runs: list[dict],
) -> dict:

    if len(
        successful_runs
    ) == 0:

        return {}


    aggregated = {}


    for metric_name in (
        AGGREGATED_METRICS
    ):

        values = [

            run[
                "metrics"
            ][
                metric_name
            ]

            for run
            in successful_runs
        ]


        # -----------------------------------------------
        # Mean
        # -----------------------------------------------

        mean_value = (
            statistics.mean(
                values
            )
        )


        # -----------------------------------------------
        # Standard Deviation
        #
        # 这里使用 sample standard deviation。
        #
        # 只有1个seed时无法计算样本标准差，
        # 教学阶段定义为0。
        # -----------------------------------------------

        if len(values) >= 2:

            std_value = (
                statistics.stdev(
                    values
                )
            )

        else:

            std_value = 0.0


        aggregated[
            metric_name
        ] = {

            "mean":
                round(
                    mean_value,
                    3
                ),

            "std":
                round(
                    std_value,
                    3
                ),

            "min":
                round(
                    min(values),
                    3
                ),

            "max":
                round(
                    max(values),
                    3
                ),

            "values":
                values,
        }


    return aggregated


# ============================================================
# 7. Batch Experiment
# ============================================================

def run_batch_experiment(
    scenario: str,
    seeds: list[int],
    duration: int,
) -> dict:

    """
    对同一个 SUMO 场景运行多个 seed。

    每个 seed 对应一次独立 SUMO 仿真实验。

    最终返回：
    1. 每个 seed 的实验结果
    2. 成功 / 失败数量
    3. 跨 seed 统计结果
    """

    # ========================================================
    # 7.1 Validation
    # ========================================================

    validation = (
        validate_batch_arguments(

            scenario=
                scenario,

            seeds=
                seeds,

            duration=
                duration,
        )
    )


    if not validation[
        "valid"
    ]:

        return {

            "status":
                "validation_error",

            "errors":
                validation[
                    "errors"
                ],
        }


    # ========================================================
    # 7.2 场景路径
    # ========================================================

    scenario_path = (
        SCENARIO_MAP[
            scenario
        ]
    )


    # ========================================================
    # 7.3 Runs
    # ========================================================

    successful_runs = []

    failed_runs = []


    print(
        "\n===================================="
    )

    print(
        "Start Batch SUMO Experiment"
    )

    print(
        "===================================="
    )

    print(
        "Scenario:",
        scenario,
    )

    print(
        "Duration:",
        duration,
    )

    print(
        "Seeds:",
        seeds,
    )


    # ========================================================
    # 7.4 每个 seed 启动一次真实 SUMO
    # ========================================================

    for index, seed in enumerate(
        seeds,
        start=1,
    ):

        print(
            "\n------------------------------------"
        )

        print(
            f"Run {index}/{len(seeds)}"
        )

        print(
            "Seed:",
            seed,
        )

        print(
            "------------------------------------"
        )


        result = run_sumo_metrics(

            sumocfg_path=str(
                scenario_path
            ),

            duration=
                duration,

            seed=
                seed,
        )


        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        if (
            result.get("status")
            == "success"
        ):

            run_metrics = (
                extract_run_metrics(
                    result
                )
            )


            successful_runs.append(
                {

                    "seed":
                        seed,

                    "status":
                        "success",

                    "counts":
                        result[
                            "counts"
                        ],

                    "metrics":
                        run_metrics,
                }
            )


            print(
                "\nRun Result: SUCCESS"
            )

            print(
                "Metrics:",
                run_metrics,
            )


        # ----------------------------------------------------
        # Failure
        # ----------------------------------------------------

        else:

            failed_run = {

                "seed":
                    seed,

                "status":
                    result.get(
                        "status",
                        "unknown_error",
                    ),

                "error_type":
                    result.get(
                        "error_type"
                    ),

                "message":
                    result.get(
                        "message"
                    ),
            }


            failed_runs.append(
                failed_run
            )


            print(
                "\nRun Result: FAILED"
            )

            print(
                failed_run
            )


    # ========================================================
    # 7.5 Aggregation
    # ========================================================

    aggregated_metrics = (
        aggregate_results(
            successful_runs
        )
    )


    # ========================================================
    # 7.6 Batch Status
    # ========================================================

    if (
        len(successful_runs)
        == len(seeds)
    ):

        batch_status = (
            "success"
        )


    elif (
        len(successful_runs)
        > 0
    ):

        batch_status = (
            "partial_success"
        )


    else:

        batch_status = (
            "batch_execution_error"
        )


    # ========================================================
    # 7.7 返回结果
    # ========================================================

    return {

        "status":
            batch_status,

        "data_source":
            "sumo",

        "experiment_config": {

            "scenario":
                scenario,

            "duration":
                duration,

            "seeds":
                seeds,

            "requested_runs":
                len(seeds),
        },


        "run_summary": {

            "successful_runs":
                len(
                    successful_runs
                ),

            "failed_runs":
                len(
                    failed_runs
                ),
        },


        "runs":
            successful_runs,


        "failures":
            failed_runs,


        "aggregated_metrics":
            aggregated_metrics,
    }


# ============================================================
# 8. Main
# ============================================================

if __name__ == "__main__":

    result = run_batch_experiment(

        scenario="cross",

        seeds=[
            42,
            43,
            44,
        ],

        duration=300,
    )


    print(
        "\n===================================="
    )

    print(
        "Batch Experiment Result"
    )

    print(
        "===================================="
    )


    print(
        "Status:",
        result[
            "status"
        ],
    )


    if (
        result["status"]
        == "validation_error"
    ):

        print(
            "Errors:",
            result[
                "errors"
            ],
        )


    else:

        print(
            "\nExperiment Config:"
        )

        print(
            result[
                "experiment_config"
            ]
        )


        print(
            "\nRun Summary:"
        )

        print(
            result[
                "run_summary"
            ]
        )


        print(
            "\nIndividual Runs:"
        )


        for run in result[
            "runs"
        ]:

            print(
                f"\nSeed={run['seed']}"
            )

            print(
                run[
                    "metrics"
                ]
            )


        if result[
            "failures"
        ]:

            print(
                "\nFailures:"
            )

            for failure in (
                result[
                    "failures"
                ]
            ):

                print(
                    failure
                )


        print(
            "\nAggregated Metrics:"
        )


        for (
            metric_name,
            statistics_info
        ) in result[
            "aggregated_metrics"
        ].items():

            print(
                f"\n{metric_name}:"
            )

            print(
                "  values:",
                statistics_info[
                    "values"
                ],
            )

            print(
                "  mean:",
                statistics_info[
                    "mean"
                ],
            )

            print(
                "  std:",
                statistics_info[
                    "std"
                ],
            )

            print(
                "  min:",
                statistics_info[
                    "min"
                ],
            )

            print(
                "  max:",
                statistics_info[
                    "max"
                ],
            )