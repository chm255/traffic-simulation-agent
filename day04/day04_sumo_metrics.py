import shutil
from pathlib import Path

import traci


# ============================================================
# 1. 监测车道
# ============================================================

MONITORED_LANES = [
    "E_C_0",
    "N_C_0",
    "S_C_0",
    "W_C_0",
]


# ============================================================
# 2. 运行 SUMO 并提取交通指标
# ============================================================

def run_sumo_metrics(
    sumocfg_path: str,
    duration: int = 300,
    seed: int = 42,
) -> dict:

    """
    运行真实 SUMO 仿真，并收集交通指标。

    当前指标：

    1. average_queue
       监测进口道停车车辆数的时间平均值

    2. mean_network_waiting_time
       每个时间步监测进口道所有车辆
       当前 waiting time 总和的时间平均值

    3. mean_vehicle_waiting_time
       仿真观察窗口内曾出现在监测进口道上的车辆，
       在监测进口道内累计等待时间的平均值

    4. throughput
       仿真期间累计 arrived 车辆数

    5. completion_rate
       total_arrived / total_departed
    """


    # ========================================================
    # 1. 检查 duration,seed
    # ========================================================
    if (
        not isinstance(seed, int)
        or isinstance(seed, bool)
    ):

        return {
            "status": "error",
            "message": "seed 必须是整数",
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


    # ========================================================
    # 2. 查找 SUMO
    # ========================================================

    sumo_binary = shutil.which(
        "sumo"
    )


    if sumo_binary is None:

        return {
            "status": "error",
            "message": "找不到 sumo 可执行文件。",
        }


    # ========================================================
    # 3. 检查 .sumocfg
    # ========================================================

    config_path = Path(
        sumocfg_path
    ).resolve()


    if not config_path.exists():

        return {
            "status": "error",

            "message": (
                f"SUMO 配置文件不存在："
                f"{config_path}"
            ),
        }


    if (
        config_path.suffix.lower()
        != ".sumocfg"
    ):

        return {
            "status": "error",

            "message": (
                "输入文件不是 .sumocfg 文件："
                f"{config_path}"
            ),
        }


    sumo_started = False


    try:

        # ====================================================
        # 4. 启动 SUMO
        # ====================================================

        print(
            "\n===== Start SUMO ====="
        )

        print(
            "SUMO Binary:",
            sumo_binary,
        )

        print(
            "SUMO Config:",
            config_path,
        )


        traci.start(
            [
                sumo_binary,
                "-c",
                str(config_path),
                 "--seed",
                str(seed),
            ]
        )


        sumo_started = True


        print(
            "TraCI Connection: SUCCESS"
        )


        # ====================================================
        # 5. 获取 simulation step length
        # ====================================================

        delta_t = (
            traci
            .simulation
            .getDeltaT()
        )


        print(
            "Simulation Step Length:",
            delta_t,
            "s",
        )


        # ====================================================
        # 6. 获取所有 Lane
        # ====================================================

        all_lane_ids = (
            traci
            .lane
            .getIDList()
        )


        print(
            "\n===== Lane Information ====="
        )

        print(
            "All Lane Count:",
            len(all_lane_ids),
        )

        print(
            "All Lane IDs:",
            all_lane_ids,
        )


        # ====================================================
        # 7. 检查监测车道
        # ====================================================

        for lane_id in MONITORED_LANES:

            if lane_id not in all_lane_ids:

                return {
                    "status": "error",

                    "message": (
                        f"监测车道不存在："
                        f"{lane_id}"
                    ),
                }


        print(
            "Monitored Lanes:",
            MONITORED_LANES,
        )


        # ====================================================
        # 8. 指标累计变量
        # ====================================================

        total_queue = 0.0

        total_network_waiting_time = 0.0

        total_departed = 0

        total_arrived = 0

        actual_steps = 0


        # ====================================================
        # Part 2.3 新增
        #
        # 每辆车累计等待时间
        #
        # 例如：
        #
        # {
        #     "veh_1": 15.0,
        #     "veh_2": 8.0,
        #     "veh_3": 0.0,
        # }
        # ====================================================

        vehicle_waiting_times = {}


        # 记录所有曾经出现在监测进口道上的车辆
        observed_vehicle_ids = set()


        # ====================================================
        # 9. SUMO 仿真循环
        # ====================================================

        print(
            "\n===== Run Simulation ====="
        )


        for _ in range(
            duration
        ):

            # -----------------------------------------------
            # 推进一个仿真步
            # -----------------------------------------------

            traci.simulationStep()

            actual_steps += 1


            # =================================================
            # 9.1 Queue
            # =================================================

            step_queue = 0


            for lane_id in MONITORED_LANES:

                halting_number = (
                    traci
                    .lane
                    .getLastStepHaltingNumber(
                        lane_id
                    )
                )


                step_queue += (
                    halting_number
                )


            total_queue += (
                step_queue
            )


            # =================================================
            # 9.2 Network Waiting Time
            # =================================================

            step_network_waiting_time = 0.0


            for lane_id in MONITORED_LANES:

                lane_waiting_time = (
                    traci
                    .lane
                    .getWaitingTime(
                        lane_id
                    )
                )


                step_network_waiting_time += (
                    lane_waiting_time
                )


            total_network_waiting_time += (
                step_network_waiting_time
            )


            # =================================================
            # 9.3 Part 2.3
            #     Vehicle-level Waiting Time
            # =================================================

            # -----------------------------------------------
            # 获取当前仍存在于网络中的车辆
            # -----------------------------------------------

            active_vehicle_ids = set(
                traci
                .vehicle
                .getIDList()
            )


            # -----------------------------------------------
            # 当前时间步位于监测进口道上的车辆
            # -----------------------------------------------

            monitored_vehicle_ids = set()


            for lane_id in MONITORED_LANES:

                lane_vehicle_ids = (
                    traci
                    .lane
                    .getLastStepVehicleIDs(
                        lane_id
                    )
                )


                for vehicle_id in lane_vehicle_ids:

                    # 防止车辆恰好在这一时间步
                    # 已经离开网络
                    if (
                        vehicle_id
                        in active_vehicle_ids
                    ):

                        monitored_vehicle_ids.add(
                            vehicle_id
                        )


            # -----------------------------------------------
            # 给车辆累计等待时间
            # -----------------------------------------------

            for vehicle_id in monitored_vehicle_ids:

                # 这辆车已经进入过监测区域
                observed_vehicle_ids.add(
                    vehicle_id
                )


                # 第一次出现时初始化为0
                if (
                    vehicle_id
                    not in vehicle_waiting_times
                ):

                    vehicle_waiting_times[
                        vehicle_id
                    ] = 0.0


                # 当前连续等待时间
                current_waiting_time = (
                    traci
                    .vehicle
                    .getWaitingTime(
                        vehicle_id
                    )
                )


                # 如果当前车辆处于等待状态，
                # 就累计一个仿真步长度
                if current_waiting_time > 0:

                    vehicle_waiting_times[
                        vehicle_id
                    ] += delta_t


            # =================================================
            # 9.4 Departed
            # =================================================

            departed_this_step = (
                traci
                .simulation
                .getDepartedNumber()
            )


            total_departed += (
                departed_this_step
            )


            # =================================================
            # 9.5 Arrived
            # =================================================

            arrived_this_step = (
                traci
                .simulation
                .getArrivedNumber()
            )


            total_arrived += (
                arrived_this_step
            )


            # =================================================
            # 9.6 调试输出
            # =================================================

            if (
                actual_steps % 50 == 0
            ):

                simulation_time = (
                    traci
                    .simulation
                    .getTime()
                )


                # 当前已经累计的车辆等待时间
                current_total_vehicle_waiting = (
                    sum(
                        vehicle_waiting_times.values()
                    )
                )


                if len(
                    observed_vehicle_ids
                ) > 0:

                    current_mean_vehicle_waiting = (
                        current_total_vehicle_waiting
                        / len(
                            observed_vehicle_ids
                        )
                    )

                else:

                    current_mean_vehicle_waiting = 0.0


                print(
                    f"Step={actual_steps}, "
                    f"time={simulation_time:.1f}, "
                    f"queue={step_queue}, "
                    f"network_waiting="
                    f"{step_network_waiting_time:.2f}, "
                    f"monitored_vehicles="
                    f"{len(monitored_vehicle_ids)}, "
                    f"observed_vehicles="
                    f"{len(observed_vehicle_ids)}, "
                    f"mean_vehicle_waiting="
                    f"{current_mean_vehicle_waiting:.2f}, "
                    f"total_departed="
                    f"{total_departed}, "
                    f"total_arrived="
                    f"{total_arrived}"
                )


        # ====================================================
        # 10. 检查实际仿真步数
        # ====================================================

        if actual_steps == 0:

            return {
                "status": "error",
                "message": (
                    "仿真没有执行任何时间步。"
                ),
            }


        # ====================================================
        # 11. Average Queue
        # ====================================================

        average_queue = (
            total_queue
            / actual_steps
        )


        # ====================================================
        # 12. Mean Network Waiting Time
        # ====================================================

        mean_network_waiting_time = (
            total_network_waiting_time
            / actual_steps
        )


        # ====================================================
        # 13. Part 2.3
        #     Mean Vehicle Waiting Time
        # ====================================================

        total_vehicle_waiting_time = (
            sum(
                vehicle_waiting_times.values()
            )
        )


        observed_vehicle_count = (
            len(
                observed_vehicle_ids
            )
        )


        if observed_vehicle_count > 0:

            mean_vehicle_waiting_time = (
                total_vehicle_waiting_time
                / observed_vehicle_count
            )

        else:

            mean_vehicle_waiting_time = 0.0


        # ====================================================
        # 14. Throughput
        # ====================================================

        throughput = (
            total_arrived
        )


        # ====================================================
        # 15. Completion Rate
        # ====================================================

        if total_departed > 0:

            completion_rate = (
                total_arrived
                / total_departed
            )

        else:

            completion_rate = 0.0


        # ====================================================
        # 16. 最终仿真时间
        # ====================================================

        final_simulation_time = (
            traci
            .simulation
            .getTime()
        )


        # ====================================================
        # 17. 返回结果
        # ====================================================

        return {

            "status":
                "success",

            "data_source":
                "sumo",


            # =================================================
            # Simulation Config
            # =================================================

            "simulation_config": {

                "sumocfg":
                    str(
                        config_path
                    ),

                "duration":
                    duration,
                "seed":
                    seed,
                "actual_steps":
                    actual_steps,

                "simulation_time":
                    final_simulation_time,

                "step_length":
                    delta_t,

                "monitored_lanes":
                    MONITORED_LANES,
            },


            # =================================================
            # Vehicle Counts
            # =================================================

            "counts": {

                "departed":
                    total_departed,

                "arrived":
                    total_arrived,

                "observed_vehicles":
                    observed_vehicle_count,
            },


            # =================================================
            # Raw accumulated values
            # =================================================

            "accumulated": {

                "total_vehicle_waiting_time": {

                    "value":
                        round(
                            total_vehicle_waiting_time,
                            2
                        ),

                    "unit":
                        "veh*s",
                },
            },


            # =================================================
            # Traffic Metrics
            # =================================================

            "metrics": {


                # ---------------------------------------------
                # Average Queue
                # ---------------------------------------------

                "average_queue": {

                    "value":
                        round(
                            average_queue,
                            2
                        ),

                    "unit":
                        "veh",

                    "definition": (
                        "监测进口车道每个仿真步"
                        "停车车辆数之和的时间平均值"
                    ),
                },


                # ---------------------------------------------
                # Mean Network Waiting Time
                # ---------------------------------------------

                "mean_network_waiting_time": {

                    "value":
                        round(
                            mean_network_waiting_time,
                            2
                        ),

                    "unit":
                        "s",

                    "definition": (
                        "监测进口车道车辆当前 waiting time "
                        "总和在各仿真时间步上的平均值；"
                        "不是平均每辆车等待时间"
                    ),
                },


                # ---------------------------------------------
                # Part 2.3
                # Mean Vehicle Waiting Time
                # ---------------------------------------------

                "mean_vehicle_waiting_time": {

                    "value":
                        round(
                            mean_vehicle_waiting_time,
                            2
                        ),

                    "unit":
                        "s/veh",

                    "definition": (
                        "仿真观察窗口内曾出现在监测进口车道上的"
                        "每辆车辆，在监测进口车道内累计等待时间"
                        "的平均值；包括仿真结束时尚未完成行程的车辆"
                    ),
                },


                # ---------------------------------------------
                # Throughput
                # ---------------------------------------------

                "throughput": {

                    "value":
                        throughput,

                    "unit":
                        "veh",

                    "definition": (
                        "仿真期间累计完成路线"
                        "并离开网络的车辆数"
                    ),
                },


                # ---------------------------------------------
                # Completion Rate
                # ---------------------------------------------

                "completion_rate": {

                    "value":
                        round(
                            completion_rate,
                            3
                        ),

                    "unit":
                        "ratio",

                    "definition": (
                        "仿真期间累计 arrived 车辆数"
                        "除以累计 departed 车辆数"
                    ),
                },
            },
        }


    # ========================================================
    # 18. SUMO / TraCI Error
    # ========================================================

    except Exception as e:

        return {
            "status":
                "sumo_execution_error",

            "error_type":
                type(e).__name__,

            "message":
                str(e),
        }


    # ========================================================
    # 19. 关闭 TraCI
    # ========================================================

    finally:

        if sumo_started:

            try:

                traci.close()


                print(
                    "\nTraCI Connection: CLOSED"
                )


            except Exception as close_error:

                print(
                    "\nWarning: "
                    "TraCI 关闭失败：",
                    close_error,
                )


# ============================================================
# 20. 程序入口
# ============================================================

if __name__ == "__main__":

    sumocfg_path = input(
        "\n请输入 SUMO .sumocfg 文件路径："
    ).strip().strip('"')


    result = run_sumo_metrics(
        sumocfg_path=sumocfg_path,
        duration=300,
        seed=42,
    )


    print(
        "\n===== SUMO Metrics Result ====="
    )


    # ========================================================
    # 错误
    # ========================================================

    if result["status"] != "success":

        print(
            "Status:",
            result["status"],
        )

        print(
            "Message:",
            result.get(
                "message"
            ),
        )


    # ========================================================
    # 成功
    # ========================================================

    else:

        print(
            "Status:",
            result["status"],
        )

        print(
            "Data Source:",
            result["data_source"],
        )


        # ----------------------------------------------------
        # Simulation Config
        # ----------------------------------------------------

        print(
            "\n===== Simulation Config ====="
        )


        for key, value in (
            result[
                "simulation_config"
            ].items()
        ):

            print(
                f"{key}: {value}"
            )


        # ----------------------------------------------------
        # Counts
        # ----------------------------------------------------

        print(
            "\n===== Vehicle Counts ====="
        )


        for key, value in (
            result[
                "counts"
            ].items()
        ):

            print(
                f"{key}: {value}"
            )


        # ----------------------------------------------------
        # Accumulated
        # ----------------------------------------------------

        print(
            "\n===== Accumulated Values ====="
        )


        for (
            metric_name,
            metric_info
        ) in result[
            "accumulated"
        ].items():

            print(
                f"{metric_name}: "
                f"{metric_info['value']} "
                f"{metric_info['unit']}"
            )


        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        print(
            "\n===== Traffic Metrics ====="
        )


        for (
            metric_name,
            metric_info
        ) in result[
            "metrics"
        ].items():

            print(
                f"\n{metric_name}:"
            )

            print(
                "  Value:",
                metric_info[
                    "value"
                ],
            )

            print(
                "  Unit:",
                metric_info[
                    "unit"
                ],
            )

            print(
                "  Definition:",
                metric_info[
                    "definition"
                ],
            )