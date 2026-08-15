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
# 3. Evaluation Test Cases
# ============================================================

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

    # --------------------------------------------------------
    # Unknown Questions
    # --------------------------------------------------------

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
# 4. Knowledge Base Loader
# ============================================================

def load_knowledge_documents() -> list[dict]:
    documents = []

    for file_path in sorted(
        KNOWLEDGE_DIR.glob("*.md")
    ):
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
# 5. Chunking
# ============================================================

def split_markdown_document(
    document: dict,
) -> list[dict]:

    content = document["content"]

    sections = content.split("\n## ")

    chunks = []

    for chunk_id, section in enumerate(
        sections
    ):
        section = section.strip()

        if not section:
            continue

        lines = section.splitlines()

        title = (
            lines[0]
            .lstrip("# ")
            .strip()
        )

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
        chunks = (
            split_markdown_document(
                document
            )
        )

        all_chunks.extend(chunks)

    return all_chunks


# ============================================================
# 6. Embedding Retrieval
# ============================================================

def retrieve_chunks_by_embedding(
    query: str,
    chunks: list[dict],
    model: SentenceTransformer,
    top_k: int = 3,
) -> list[dict]:

    query_embedding = model.encode(
        query
    )

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


# ============================================================
# 7. Build Context
# ============================================================

def build_context(
    results: list[dict],
) -> str:

    context_parts = []

    for index, result in enumerate(
        results,
        start=1,
    ):

        context_part = f"""
[Context {index}]

Source: {result["source"]}
Title: {result["title"]}

{result["content"]}
""".strip()

        context_parts.append(
            context_part
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# 8. Answerability Check
# ============================================================

def check_answerability(
    query: str,
    context: str,
) -> bool:

    messages = [
        {
            "role": "system",
            "content": (
                "You are an answerability checker. "
                "Determine whether the provided retrieved "
                "context contains sufficient information "
                "to answer the user's question. "
                "Do not use outside knowledge. "
                "Do not infer missing project-specific facts. "
                "Return only YES or NO."
            ),
        },
        {
            "role": "user",
            "content": f"""
Question:

{query}


Retrieved Context:

{context}
""".strip(),
        },
    ]

    response = client.chat.completions.create(
        model=CHAT_MODEL_NAME,
        messages=messages,
        extra_body={
            "thinking": {
                "type": "disabled"
            }
        },
    )

    result = (
        response
        .choices[0]
        .message
        .content
        .strip()
        .upper()
    )

    if result == "YES":
        return True

    if result == "NO":
        return False

    raise ValueError(
        "Unexpected answerability "
        f"result: {result}"
    )


# ============================================================
# 9. Main Evaluation
# ============================================================

def main():

    # --------------------------------------------------------
    # Load local embedding model
    # --------------------------------------------------------

    embedding_model = (
        SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            local_files_only=True,
        )
    )

    # --------------------------------------------------------
    # Build knowledge chunks
    # --------------------------------------------------------

    documents = (
        load_knowledge_documents()
    )

    chunks = build_chunks(
        documents
    )

    print(
        f"Document Count: "
        f"{len(documents)}"
    )

    print(
        f"Chunk Count: "
        f"{len(chunks)}"
    )

    print()

    # --------------------------------------------------------
    # Evaluation Counters
    # --------------------------------------------------------

    correct_count = 0

    known_correct = 0
    known_total = 0

    unknown_correct = 0
    unknown_total = 0

    # --------------------------------------------------------
    # Evaluate every test case
    # --------------------------------------------------------

    for case in TEST_CASES:

        query = case["query"]
        expected_known = case["known"]

        # ----------------------------------------------------
        # Retrieval
        # ----------------------------------------------------

        results = (
            retrieve_chunks_by_embedding(
                query=query,
                chunks=chunks,
                model=embedding_model,
                top_k=3,
            )
        )

        # ----------------------------------------------------
        # Context
        # ----------------------------------------------------

        context = build_context(
            results
        )

        # ----------------------------------------------------
        # Answerability
        # ----------------------------------------------------

        answerable = (
            check_answerability(
                query=query,
                context=context,
            )
        )

        # ----------------------------------------------------
        # Evaluation
        # ----------------------------------------------------

        correct = (
            answerable
            == expected_known
        )

        if correct:
            correct_count += 1

        if expected_known:
            known_total += 1

            if correct:
                known_correct += 1

        else:
            unknown_total += 1

            if correct:
                unknown_correct += 1

        # ----------------------------------------------------
        # Output
        # ----------------------------------------------------

        print("=" * 80)

        print(f"Query: {query}")

        print(
            f"Expected Known: "
            f"{expected_known}"
        )

        print(
            f"Answerable: "
            f"{answerable}"
        )

        print(
            f"Correct: "
            f"{correct}"
        )

        print()

        print("Retrieved Top-3:")

        for rank, result in enumerate(
            results,
            start=1,
        ):
            print(
                f"{rank}. "
                f"{result['title']} "
                f"(score="
                f"{result['score']:.4f}) "
                f"[source="
                f"{result['source']}]"
            )

        print()

    # --------------------------------------------------------
    # Final Summary
    # --------------------------------------------------------

    total_cases = len(TEST_CASES)

    print("=" * 80)
    print("Evaluation Summary")
    print("=" * 80)

    print(
        f"Overall Accuracy: "
        f"{correct_count} / "
        f"{total_cases}"
    )

    print(
        f"Known Accuracy: "
        f"{known_correct} / "
        f"{known_total}"
    )

    print(
        f"Unknown Accuracy: "
        f"{unknown_correct} / "
        f"{unknown_total}"
    )


if __name__ == "__main__":
    main()