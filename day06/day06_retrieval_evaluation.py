from pathlib import Path

from openai import OpenAI
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


# ============================================================
# 1. Project Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
API_KEY_PATH = PROJECT_ROOT / "api.txt"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

CHAT_MODEL_NAME = "deepseek-v4-flash"
TEST_CASES = [
    {
        "query": "我们项目里的吞吐量是怎么定义的？",
        "expected_title": "throughput",
        "known": True,
    },
    {
        "query": "average_queue 是什么意思？",
        "expected_title": "average_queue",
        "known": True,
    },
    {
        "query": "平均车辆等待时间是怎么定义的？",
        "expected_title": "mean_vehicle_waiting_time",
        "known": True,
    },
    {
        "query": "cross 场景监测哪些车道？",
        "expected_title": "Monitored Approach Lanes",
        "known": True,
    },
    {
        "query": "seed 有什么规则？",
        "expected_title": "Seed Rules",
        "known": True,
    },

    {
        "query": "当前项目使用的强化学习 reward function 是什么？",
        "expected_title": None,
        "known": False,
    },
    {
        "query": "当前 PPO 的 learning rate 是多少？",
        "expected_title": None,
        "known": False,
    },
    {
        "query": "当前交通信号周期是多少秒？",
        "expected_title": None,
        "known": False,
    },
    {
        "query": "可变车道多久切换一次？",
        "expected_title": None,
        "known": False,
    },
    {
        "query": "模型训练了多少个 episodes？",
        "expected_title": None,
        "known": False,
    },
]

# ============================================================
# 2. DeepSeek Client
# ============================================================

api_key = API_KEY_PATH.read_text(
    encoding="utf-8"
).strip()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# ============================================================
# 3. Knowledge Base Loader
# ============================================================

def load_knowledge_documents() -> list[dict]:
    documents = []

    for file_path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = file_path.read_text(
            encoding="utf-8"
        )

        document = {
            "source": file_path.name,
            "path": str(file_path),
            "content": content,
        }

        documents.append(document)

    return documents


# ============================================================
# 4. Chunking
# ============================================================

def split_markdown_document(
    document: dict,
) -> list[dict]:

    content = document["content"]

    sections = content.split("\n## ")

    chunks = []

    for chunk_id, section in enumerate(sections):
        section = section.strip()

        if not section:
            continue

        lines = section.splitlines()

        title = lines[0].lstrip("# ").strip()

        chunk = {
            "source": document["source"],
            "path": document["path"],
            "chunk_id": chunk_id,
            "title": title,
            "content": section,
        }

        chunks.append(chunk)

    return chunks


def build_chunks(
    documents: list[dict],
) -> list[dict]:

    all_chunks = []

    for document in documents:
        chunks = split_markdown_document(
            document
        )

        all_chunks.extend(chunks)

    return all_chunks


# ============================================================
# 5. Embedding Retrieval
# ============================================================

def retrieve_chunks_by_embedding(
    query: str,
    chunks: list[dict],
    model: SentenceTransformer,
    top_k: int = 3,
) -> list[dict]:

    query_embedding = model.encode(query)

    scored_chunks = []

    for chunk in chunks:

        chunk_text = f"""
Title: {chunk["title"]}

Content:
{chunk["content"]}
""".strip()

        chunk_embedding = model.encode(
            chunk_text
        )

        similarity = cos_sim(
            query_embedding,
            chunk_embedding,
        ).item()

        result = {
            **chunk,
            "score": similarity,
        }

        scored_chunks.append(result)

    scored_chunks.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return scored_chunks[:top_k]

def main():
    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        local_files_only=True,
    )

    documents = load_knowledge_documents()
    chunks = build_chunks(documents)

    for case in TEST_CASES:
        results = retrieve_chunks_by_embedding(
            query=case["query"],
            chunks=chunks,
            model=embedding_model,
            top_k=3,
        )

        top1 = results[0]
        top2 = results[1]

        margin = (
            top1["score"]
            - top2["score"]
        )

        if case["known"]:
            hit = (
                top1["title"]
                == case["expected_title"]
            )
        else:
            hit = None

        print("=" * 80)
        print(f"Query: {case['query']}")
        print(f"Known: {case['known']}")
        print(f"Expected: {case['expected_title']}")

        print(
            f"Top1: {top1['title']} "
            f"({top1['score']:.4f})"
        )

        print(
            f"Top2: {top2['title']} "
            f"({top2['score']:.4f})"
        )

        print(f"Margin: {margin:.4f}")
        print(f"Hit: {hit}")

if __name__ == "__main__":
    main()