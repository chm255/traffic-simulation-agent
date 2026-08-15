from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
STOP_WORDS = {
    "what",
    "is",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "how",
    "are",
}

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

def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())

    return [
        token
        for token in tokens
        if token not in STOP_WORDS
    ]

def score_chunk(query: str, chunk: dict) -> int:
    query_tokens = tokenize(query)

    title_tokens = set(tokenize(chunk["title"]))
    content_tokens = set(tokenize(chunk["content"]))

    score = 0

    for token in query_tokens:
        if token in title_tokens:
            score += 2
        elif token in content_tokens:
            score += 1

    return score

def retrieve_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 3,
) -> list[dict]:

    scored_chunks = []

    for chunk in chunks:
        score = score_chunk(query, chunk)

        if score > 0:
            result = {
                **chunk,
                "score": score,
            }

            scored_chunks.append(result)

    scored_chunks.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return scored_chunks[:top_k]

def main():
    documents = load_knowledge_documents()
    chunks = build_chunks(documents)

    query = "我们项目里的吞吐量是怎么定义的？"

    results = retrieve_chunks(
        query=query,
        chunks=chunks,
        top_k=3,
    )

    print(f"Query: {query}")
    print(f"Total Chunks: {len(chunks)}")
    print(f"Retrieved: {len(results)}")
    print()

    for rank, result in enumerate(results, start=1):
        print("=" * 60)
        print(f"Rank: {rank}")
        print(f"Score: {result['score']}")
        print(f"Source: {result['source']}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"Title: {result['title']}")
        print()
        print(result["content"])
        print()


if __name__ == "__main__":
    main()