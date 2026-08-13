import shutil
from pathlib import Path

import traci


def test_sumo_connection(
    sumocfg_path: str,
    steps: int = 10,
) -> dict:
    """
    启动一个真实 SUMO 场景，
    通过 TraCI 推进若干仿真步，
    并读取当前仿真时间。
    """

    # ========================================================
    # 1. 找 SUMO 可执行文件
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
    # 2. 检查 .sumocfg 文件
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


    if config_path.suffix.lower() != ".sumocfg":

        return {
            "status": "error",
            "message": (
                "输入文件不是 .sumocfg 文件："
                f"{config_path}"
            ),
        }


    # 记录 SUMO 是否已经成功启动
    sumo_started = False


    try:

        # ====================================================
        # 3. 启动 SUMO + 建立 TraCI 连接
        # ====================================================

        print("\n===== Start SUMO =====")

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
            ]
        )

        sumo_started = True

        print(
            "TraCI Connection: SUCCESS"
        )


        # ====================================================
        # 4. 推进仿真
        # ====================================================

        print(
            f"\n===== Run {steps} Simulation Steps ====="
        )


        for step in range(
            1,
            steps + 1,
        ):

            traci.simulationStep()

            simulation_time = (
                traci.simulation.getTime()
            )

            print(
                f"Step {step}: "
                f"simulation_time="
                f"{simulation_time}"
            )


        # ====================================================
        # 5. 获取最终状态
        # ====================================================

        final_time = (
            traci.simulation.getTime()
        )

        loaded_vehicles = (
            traci.simulation.getLoadedNumber()
        )

        departed_vehicles = (
            traci.simulation.getDepartedNumber()
        )

        arrived_vehicles = (
            traci.simulation.getArrivedNumber()
        )


        return {
            "status": "success",

            "sumo_binary":
                sumo_binary,

            "sumocfg":
                str(config_path),

            "steps":
                steps,

            "simulation_time":
                final_time,

            "last_step": {
                "loaded":
                    loaded_vehicles,

                "departed":
                    departed_vehicles,

                "arrived":
                    arrived_vehicles,
            },
        }


    except Exception as e:

        return {
            "status":
                "sumo_execution_error",

            "error_type":
                type(e).__name__,

            "message":
                str(e),
        }


    finally:

        # ====================================================
        # 6. 无论成功失败都尝试关闭 SUMO
        # ====================================================

        if sumo_started:

            try:

                traci.close()

                print(
                    "\nTraCI Connection: CLOSED"
                )

            except Exception as close_error:

                print(
                    "\nWarning: "
                    "TraCI关闭失败：",
                    close_error,
                )


if __name__ == "__main__":

    sumocfg_path = input(
        "\n请输入 SUMO .sumocfg 文件路径："
    ).strip().strip('"')


    result = test_sumo_connection(
        sumocfg_path=sumocfg_path,
        steps=10,
    )


    print(
        "\n===== SUMO Test Result ====="
    )


    for key, value in result.items():

        print(
            f"{key}: {value}"
        )