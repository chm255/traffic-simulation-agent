from pathlib import Path

from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent
API_FILE = BASE_DIR / "api.txt"


if not API_FILE.exists():
    raise FileNotFoundError(
        f"未找到 API Key 文件：{API_FILE}"
    )


api_key = API_FILE.read_text(encoding="utf-8").strip()


if not api_key:
    raise ValueError("api.txt 为空，请写入 DeepSeek API Key。")


client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

def analyze_traffic_state(
    queue: float,
    waiting_time: float,
    throughput: int,
    completion_rate: float,
) -> str:
    #role角色，content内容，messages是一个列表，包含system和user，system主要告诉模型你是谁，你的工作规则是什么；user告诉模型当前这一次具体让它干什么
    #system岗位说明书，user当前任务
    user_prompt = f"""
某交叉口当前交通运行指标如下：

平均排队长度：{queue}米
平均等待时间：{waiting_time} 秒
通过量：{throughput} 辆
车辆完成率：{completion_rate}

请分析当前交通运行状态。
"""

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一名交通工程分析助手。"
                    "请根据用户提供的数据进行客观分析，"
                    "不要编造不存在的数据。"
                ),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        stream=False,
    )

    return response.choices[0].message.content

if __name__ == "__main__":

    result = analyze_traffic_state(
        queue=55,
        waiting_time=160,
        throughput=900,
        completion_rate=0.70,
    )

print("\n===== Traffic Analysis =====")
print(result)