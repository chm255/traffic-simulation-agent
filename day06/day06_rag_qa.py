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


# ============================================================
# 6. Build Retrieved Context
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
# 7. RAG Generation
# ============================================================

def answer_with_rag(
    query: str,
    context: str,
) -> str:

    messages = [
        {
            "role": "system",
            "content": (
                "You are a Traffic Simulation Agent "
                "knowledge assistant. "
                "Answer the user's question using only "
                "the provided retrieved context. "
                "Do not invent unsupported project facts. "
                "If the retrieved context does not contain "
                "enough information to answer the question, "
                "clearly say that the current knowledge base "
                "does not provide enough information."
            ),
        },
        {
            "role": "user",
            "content": f"""
User Question:

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

    answer = (
        response
        .choices[0]
        .message
        .content
    )

    return answer


# ============================================================
# 8. Main RAG Pipeline
# ============================================================

def main():

    # --------------------------------------------------------
    # Load embedding model
    # --------------------------------------------------------

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        local_files_only=True,
    )

    # --------------------------------------------------------
    # Load knowledge base
    # --------------------------------------------------------

    documents = (
        load_knowledge_documents()
    )

    chunks = build_chunks(
        documents
    )

    # --------------------------------------------------------
    # User question
    # --------------------------------------------------------

    query = (
        "我们项目里的吞吐量是怎么定义的？"
    )

    # --------------------------------------------------------
    # Retrieval
    # --------------------------------------------------------

    results = (
        retrieve_chunks_by_embedding(
            query=query,
            chunks=chunks,
            model=embedding_model,
            top_k=3,
        )
    )

    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    context = build_context(
        results
    )

    # --------------------------------------------------------
    # Generation
    # --------------------------------------------------------

    answer = answer_with_rag(
        query=query,
        context=context,
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print("=" * 80)
    print("Question:")
    print(query)
    print()

    print("=" * 80)
    print("Retrieved Context:")

    for rank, result in enumerate(
        results,
        start=1,
    ):
        print(
            f"{rank}. "
            f"{result['title']} "
            f"(score={result['score']:.4f}) "
            f"[source={result['source']}]"
        )

    print()

    print("=" * 80)
    print("RAG Answer:")
    print(answer)


if __name__ == "__main__":
    main()