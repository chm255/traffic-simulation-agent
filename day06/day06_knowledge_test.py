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


def main():
    print(f"Knowledge Directory: {KNOWLEDGE_DIR}")

    documents = load_knowledge_documents()

    print(f"Document Count: {len(documents)}")
    print()

    for index, document in enumerate(documents, start=1):
        print("=" * 60)
        print(f"Document #{index}")
        print(f"Source: {document['source']}")
        print(f"Path: {document['path']}")
        print(f"Content Length: {len(document['content'])}")
        print()
        print(document["content"][:300])
        print()


if __name__ == "__main__":
    main()