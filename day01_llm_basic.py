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


response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "system",
            "content": (
                "你是一名交通工程分析助手。"
                "请根据用户提供的交通运行指标进行简洁、客观的分析。"
            ),
        },
        {
            "role": "user",
            "content": """
某交叉口当前交通运行指标如下：

平均排队长度：32.5
平均等待时间：88.2 秒
通过量：1171 辆
车辆完成率：0.888

请分析当前交通运行状态。
""",
        },
    ],
    stream=False,
)


print(response.choices[0].message.content)