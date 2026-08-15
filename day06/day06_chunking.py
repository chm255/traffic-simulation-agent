from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


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


def main():
    documents = load_knowledge_documents()

    all_chunks = []

    for document in documents:
        chunks = split_markdown_document(document)
        all_chunks.extend(chunks)

    print(f"Document Count: {len(documents)}")
    print(f"Chunk Count: {len(all_chunks)}")
    print()

    for chunk in all_chunks:
        print("=" * 60)
        print(f"Source: {chunk['source']}")
        print(f"Chunk ID: {chunk['chunk_id']}")
        print(f"Title: {chunk['title']}")
        print(f"Content Length: {len(chunk['content'])}")
        print()
        print(chunk["content"][:300])
        print()


if __name__ == "__main__":
    main()