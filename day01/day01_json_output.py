import json
from pathlib import Path

from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent
API_FILE = BASE_DIR / "api.txt"

api_key = API_FILE.read_text(
    encoding="utf-8"
).strip()


client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


def analyze_traffic_state(
    queue: float,
    waiting_time: float,
    throughput: int,
    completion_rate: float,
) -> dict:#: float输入数据的类型标注，-> dict输出数据的类型标注，只是类型提示；def add(a: int, b: int) -> int:不影响函数本身

    system_prompt = """
你是一名交通工程分析助手。

请根据用户提供的交通运行指标分析交通状态。

必须使用 JSON 格式输出。

JSON 格式：

{
    "traffic_state": "free_flow | stable | congested | oversaturated",
    "severity": "low | medium | high",
    "main_reason": "主要原因",
    "recommended_action": "建议"
}

规则：

1. 只能输出 JSON；
2. 不要输出额外解释；
3. 不要编造用户没有提供的数据。
"""

    user_prompt = f"""
交通运行指标：

average_queue = {queue}米
average_waiting_time = {waiting_time}秒
throughput = {throughput}辆
completion_rate = {completion_rate}

请输出 JSON。
"""

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        response_format={
            "type": "json_object"
        },
        max_tokens=500,
        # 关闭 Thinking Mode
        extra_body={
            "thinking": {
                "type": "disabled"
            }
        },
        stream=False,
    )

    content = response.choices[0].message.content
    #content是字符串
    finish_reason = response.choices[0].finish_reason

    print("\n===== Response Debug =====")

    print(
        "Finish Reason:",
        finish_reason,
    )

    print(
        "Raw Content:",
        repr(content),
    )


    # 1. 检查是否为空
    if content is None or not content.strip():

        return {
            "status": "empty_response",
            "data": None,
            "finish_reason": finish_reason,
        }


    # 2. 尝试解析 JSON
    try:

        data = json.loads(content)

    except json.JSONDecodeError as e:

        return {
            "status": "invalid_json",
            "data": None,
            "error": str(e),
            "raw_content": content,
        }


    # 3. 正常结果
    return {
        "status": "success",
        "data": data,
    }

if __name__ == "__main__":

    result = analyze_traffic_state(
        queue=32.5,
        waiting_time=88.2,
        throughput=1172,
        completion_rate=0.888,
    )

    print("\n===== Parsed Result =====")
    print(result)


    if result["status"] == "success":

        data = result["data"]

        print("\nTraffic State:")
        print(data["traffic_state"])

        print("\nSeverity:")
        print(data["severity"])

        print("\nReason:")
        print(data["main_reason"])

        print("\nRecommended Action:")
        print(data["recommended_action"])

    else:

        print("\n分析失败。")
        print("Status:", result["status"])