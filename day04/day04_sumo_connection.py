import os
import shutil
from pathlib import Path

import traci


def check_sumo_environment() -> dict:
    """
    检查当前 Python 环境是否能够找到 SUMO 和 TraCI。
    """

    sumo_home = os.environ.get(
        "SUMO_HOME"
    )

    sumo_binary = shutil.which(
        "sumo"
    )

    sumo_gui_binary = shutil.which(
        "sumo-gui"
    )


    result = {
        "sumo_home": sumo_home,
        "sumo_binary": sumo_binary,
        "sumo_gui_binary": sumo_gui_binary,
        "traci_import": True,
    }


    if sumo_home is None:

        result["status"] = "warning"

        result["message"] = (
            "SUMO_HOME 未设置，"
            "但如果 sumo 已在 PATH 中，"
            "仍可能正常使用。"
        )

        return result


    if sumo_binary is None:

        result["status"] = "error"

        result["message"] = (
            "找不到 sumo 可执行文件。"
        )

        return result


    result["status"] = "success"

    result["message"] = (
        "SUMO / TraCI 环境检查通过。"
    )

    return result


if __name__ == "__main__":

    result = check_sumo_environment()

    print(
        "\n===== SUMO Environment Check ====="
    )

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )