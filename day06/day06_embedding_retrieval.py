from pathlib import Path

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_knowledge_documents() -> list[dict]:
    documents = []

    for file_path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = file_path.read_text(encoding="utf-8")

        document = {
            "source": file_path.name,
            "path": str(file_path),
            "content": content,
        }

        documents.append(document)

    return documents


def split_markdown_document(document: dict) -> list[dict]:
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


def build_chunks(documents: list[dict]) -> list[dict]:
    all_chunks = []

    for document in documents:
        chunks = split_markdown_document(document)
        all_chunks.extend(chunks)

    return all_chunks


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

        chunk_embedding = model.encode(chunk_text)

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
    model = SentenceTransformer(
        MODEL_NAME,
        local_files_only=True,
    )

    documents = load_knowledge_documents()
    chunks = build_chunks(documents)

    queries = [
    "我们项目里的吞吐量是怎么定义的？",
    "average_queue 是什么意思？",
    "平均车辆等待时间是怎么定义的？",
    "cross 场景监测哪些车道？",
    "seed 有什么规则？",
]

    for query in queries:
        results = retrieve_chunks_by_embedding(
            query=query,
            chunks=chunks,
            model=model,
            top_k=3,
        )

        print("=" * 80)
        print(f"Query: {query}")

        for rank, result in enumerate(results, start=1):
            print(
                f"{rank}. "
                f"{result['title']} "
                f"(score={result['score']:.4f})"
            )


if __name__ == "__main__":
    main()