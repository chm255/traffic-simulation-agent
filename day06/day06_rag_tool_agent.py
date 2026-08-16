from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

CHAT_MODEL_NAME = "deepseek-v4-flash"

MAX_AGENT_STEPS = 6

DEFAULT_TOP_K = 3


# ============================================================
# 2. Import Existing SUMO Tool
# ============================================================

# 这里直接复用 Day 4 已经实现和验证过的真实 SUMO Tool。
#
# 预期：
#
# day04/
# ├── __init__.py
# └── day04_real_sumo_agent.py
#
# day04_real_sumo_agent.py 中存在：
#
# def run_sumo_experiment(
#     scenario: str,
#     seed: int,
#     duration: int,
# ) -> dict:
#     ...

from day04.day04_real_sumo_agent import run_sumo_experiment


# ============================================================
# 3. DeepSeek Client
# ============================================================

api_key = API_KEY_PATH.read_text(
    encoding="utf-8"
).strip()

if not api_key:
    raise RuntimeError(
        f"API key is empty: {API_KEY_PATH}"
    )

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# ============================================================
# 4. Knowledge Base Loader
# ============================================================

def load_knowledge_documents() -> list[dict[str, Any]]:
    """
    Load all Markdown files under knowledge/.

    Each Markdown file becomes one Document:

    {
        "source": "...",
        "path": "...",
        "content": "..."
    }
    """

    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge directory does not exist: "
            f"{KNOWLEDGE_DIR}"
        )

    documents: list[dict[str, Any]] = []

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
# 5. Markdown Chunking
# ============================================================

def split_markdown_document(
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Split a Markdown document by level-2 headings: ##

    Current Day 6 strategy:
    one Markdown semantic section -> one Chunk.
    """

    content = document["content"]

    sections = content.split("\n## ")

    chunks: list[dict[str, Any]] = []

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
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert all Documents into retrieval Chunks.
    """

    all_chunks: list[dict[str, Any]] = []

    for document in documents:
        chunks = split_markdown_document(
            document
        )

        all_chunks.extend(chunks)

    return all_chunks


# ============================================================
# 6. Load Embedding Model + Knowledge Base Once
# ============================================================

print("Loading local embedding model...")

EMBEDDING_MODEL = SentenceTransformer(
    EMBEDDING_MODEL_NAME,
    local_files_only=True,
)

print("Loading project knowledge base...")

KNOWLEDGE_DOCUMENTS = (
    load_knowledge_documents()
)

KNOWLEDGE_CHUNKS = build_chunks(
    KNOWLEDGE_DOCUMENTS
)

print(
    f"Knowledge base ready: "
    f"{len(KNOWLEDGE_DOCUMENTS)} documents, "
    f"{len(KNOWLEDGE_CHUNKS)} chunks."
)


# ============================================================
# 7. Embedding Retriever
# ============================================================

def retrieve_chunks_by_embedding(
    query: str,
    chunks: list[dict[str, Any]],
    model: SentenceTransformer,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """
    Semantic retrieval:

    Query
      -> query embedding
      -> compare with every Chunk embedding
      -> cosine similarity
      -> Top-K
    """

    query_embedding = model.encode(
        query
    )

    scored_chunks: list[
        dict[str, Any]
    ] = []

    for chunk in chunks:

        # Reinforce metadata/title information
        # during embedding.
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
# 8. RAG Tool
# ============================================================

def search_project_knowledge(
    query: str,
) -> dict[str, Any]:
    """
    Search project-specific knowledge.

    Important:
    This Tool only retrieves knowledge.

    It does NOT generate the final user answer.
    The Agent LLM interprets the returned knowledge.
    """

    # ---------------------------
    # Runtime Validation
    # ---------------------------

    if not isinstance(query, str):
        return {
            "status": "validation_error",
            "error": (
                "query must be a string"
            ),
        }

    query = query.strip()

    if not query:
        return {
            "status": "validation_error",
            "error": (
                "query must not be empty"
            ),
        }

    # ---------------------------
    # Retrieval
    # ---------------------------

    try:
        results = (
            retrieve_chunks_by_embedding(
                query=query,
                chunks=KNOWLEDGE_CHUNKS,
                model=EMBEDDING_MODEL,
                top_k=DEFAULT_TOP_K,
            )
        )

    except Exception as exc:
        return {
            "status": "retrieval_error",
            "error": str(exc),
        }

    # ---------------------------
    # Tool-friendly result
    # ---------------------------

    knowledge_results = []

    for result in results:
        knowledge_results.append(
            {
                "source": result["source"],
                "title": result["title"],
                "score": round(
                    float(result["score"]),
                    4,
                ),
                "content": result["content"],
            }
        )

    return {
        "status": "success",
        "query": query,
        "result_count": len(
            knowledge_results
        ),
        "results": knowledge_results,
    }


# ============================================================
# 9. SUMO Tool Runtime Wrapper
# ============================================================

def run_sumo_experiment_safe(
    scenario: str,
    seed: int,
    duration: int,
) -> dict[str, Any]:
    """
    Runtime validation wrapper around the
    existing Day 4 SUMO Tool.
    """

    # --------------------------------------------------------
    # scenario validation
    # --------------------------------------------------------

    if not isinstance(scenario, str):
        return {
            "status": "validation_error",
            "error": (
                "scenario must be a string"
            ),
        }

    scenario = scenario.strip()

    if scenario != "cross":
        return {
            "status": "validation_error",
            "error": (
                "Current supported scenario "
                "is only 'cross'."
            ),
        }

    # --------------------------------------------------------
    # seed validation
    # --------------------------------------------------------

    if (
        not isinstance(seed, int)
        or isinstance(seed, bool)
    ):
        return {
            "status": "validation_error",
            "error": (
                "seed must be an integer"
            ),
        }

    if seed < 0:
        return {
            "status": "validation_error",
            "error": (
                "seed must be >= 0"
            ),
        }

    # --------------------------------------------------------
    # duration validation
    # --------------------------------------------------------

    if (
        not isinstance(duration, int)
        or isinstance(duration, bool)
    ):
        return {
            "status": "validation_error",
            "error": (
                "duration must be an integer"
            ),
        }

    if duration <= 0:
        return {
            "status": "validation_error",
            "error": (
                "duration must be > 0"
            ),
        }

    # --------------------------------------------------------
    # Execute real SUMO
    # --------------------------------------------------------

    try:
        result = run_sumo_experiment(
            scenario=scenario,
            seed=seed,
            duration=duration,
        )

        return result

    except Exception as exc:
        return {
            "status": "execution_error",
            "error": str(exc),
        }


# ============================================================
# 10. Tool Schemas
# ============================================================

KNOWLEDGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": (
            "search_project_knowledge"
        ),
        "description": (
            "Search the Traffic Simulation Agent "
            "project knowledge base. "
            "Use this for project-specific "
            "definitions, traffic metrics, "
            "scenario information, experiment "
            "rules, seed rules, statistical "
            "interpretation, and current agent "
            "capability limits."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The project-specific "
                        "knowledge question or "
                        "information to search for."
                    ),
                },
            },
            "required": [
                "query",
            ],
            "additionalProperties": False,
        },
    },
}


SUMO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_sumo_experiment",
        "description": (
            "Run one real SUMO traffic simulation "
            "experiment for the supported scenario "
            "and return traffic performance metrics. "
            "Use this only when the user actually "
            "asks to execute a simulation experiment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "enum": [
                        "cross",
                    ],
                    "description": (
                        "Semantic scenario name. "
                        "Currently only 'cross' "
                        "is supported."
                    ),
                },
                "seed": {
                    "type": "integer",
                    "minimum": 0,
                    "description": (
                        "SUMO random seed. "
                        "The seed must come from "
                        "the user's request."
                    ),
                },
                "duration": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Simulation duration "
                        "in seconds."
                    ),
                },
            },
            "required": [
                "scenario",
                "seed",
                "duration",
            ],
            "additionalProperties": False,
        },
    },
}


TOOLS = [
    KNOWLEDGE_TOOL_SCHEMA,
    SUMO_TOOL_SCHEMA,
]


# ============================================================
# 11. Tool Map
# ============================================================

TOOL_MAP = {
    "search_project_knowledge":
        search_project_knowledge,

    "run_sumo_experiment":
        run_sumo_experiment_safe,
}


# ============================================================
# 12. System Prompt
# ============================================================

SYSTEM_PROMPT = """
You are the Traffic Simulation Agent.

Your job is to help the user with project-specific
traffic simulation knowledge and real SUMO experiments.

You have two main tools.

1. search_project_knowledge

Use this tool when project-specific knowledge is needed,
including:
- metric definitions
- scenario information
- monitored lanes
- experiment rules
- seed rules
- statistical interpretation
- current system capability limits

Do not invent project-specific facts that are not supported
by the knowledge tool result.

2. run_sumo_experiment

Use this tool only when the user explicitly asks to run
a real SUMO experiment.

Current SUMO support:
- scenario: cross
- one user-provided seed
- one simulation duration

Important rules:

- Conceptual/project-knowledge questions should normally use
  search_project_knowledge and should NOT start SUMO.

- Simulation requests should use run_sumo_experiment.

- If the task requires both project knowledge and a real
  simulation, you may use both tools.

- Do not claim that SUMO was executed unless the SUMO tool
  actually returned a successful result.

- Never invent a missing seed.

- Never silently substitute a different seed, scenario,
  or duration.

- Retrieved knowledge is evidence, not permission to perform
  capabilities that the runtime does not provide.

- When interpreting simulation metrics, respect the
  project-specific definitions obtained from the knowledge
  base when needed.

- If the available knowledge is insufficient, clearly say
  that the current knowledge base does not provide enough
  information.

After all necessary tools have been executed, give the user
a clear final answer.

Scientific interpretation rules:

- Distinguish observed results from causal explanations.
- Do not claim that one metric caused another unless the experiment
  explicitly supports that causal conclusion.
- Do not predict how a metric would change under a longer simulation,
  different seed, or different scenario unless that experiment was
  actually performed.
- For finite-horizon metrics, describe only what is observed within
  the specified observation window.
""".strip()


# ============================================================
# 13. Call Chat Model
# ============================================================

def call_model(
    messages: list[dict[str, Any]],
):
    """
    One DeepSeek model call.
    """

    return client.chat.completions.create(
        model=CHAT_MODEL_NAME,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        extra_body={
            "thinking": {
                "type": "disabled",
            }
        },
    )


# ============================================================
# 14. Execute One Tool Call
# ============================================================

def execute_tool_call(
    tool_call,
) -> dict[str, Any]:
    """
    Parse one model-proposed Tool Call,
    validate it through Runtime,
    then execute the real Python function.
    """

    tool_name = (
        tool_call.function.name
    )

    raw_arguments = (
        tool_call.function.arguments
    )

    print()
    print("-" * 80)
    print("Tool Call")
    print("-" * 80)

    print(
        f"Name: {tool_name}"
    )

    print(
        f"Arguments: {raw_arguments}"
    )

    # --------------------------------------------------------
    # Tool existence validation
    # --------------------------------------------------------

    if tool_name not in TOOL_MAP:
        return {
            "status": "tool_error",
            "error": (
                f"Unknown tool: "
                f"{tool_name}"
            ),
        }

    # --------------------------------------------------------
    # JSON parsing
    # --------------------------------------------------------

    try:
        arguments = json.loads(
            raw_arguments
        )

    except json.JSONDecodeError as exc:
        return {
            "status": (
                "argument_parse_error"
            ),
            "error": str(exc),
        }

    if not isinstance(arguments, dict):
        return {
            "status": (
                "argument_validation_error"
            ),
            "error": (
                "Tool arguments must "
                "decode to a JSON object."
            ),
        }

    # --------------------------------------------------------
    # Execute Runtime-controlled Tool
    # --------------------------------------------------------

    tool_function = (
        TOOL_MAP[tool_name]
    )

    try:
        result = tool_function(
            **arguments
        )

    except TypeError as exc:
        result = {
            "status": (
                "argument_validation_error"
            ),
            "error": str(exc),
        }

    except Exception as exc:
        result = {
            "status": (
                "tool_execution_error"
            ),
            "error": str(exc),
        }

    print()
    print("Tool Result:")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    return result


# ============================================================
# 15. Generic Agent Loop
# ============================================================

def run_agent(
    user_input: str,
    max_steps: int = MAX_AGENT_STEPS,
) -> str:
    """
    Generic Agent Loop:

    User
      -> LLM
      -> Tool proposal
      -> Runtime validation
      -> Tool execution
      -> Observation
      -> LLM
      -> Tool / Final Answer
    """

    messages: list[
        dict[str, Any]
    ] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    for step in range(
        1,
        max_steps + 1,
    ):

        print()
        print("=" * 80)
        print(
            f"Agent Step {step}"
        )
        print("=" * 80)

        # ----------------------------------------------------
        # Model Decision
        # ----------------------------------------------------

        try:
            response = call_model(
                messages
            )

        except Exception as exc:
            return (
                "Model API error: "
                f"{exc}"
            )

        message = (
            response
            .choices[0]
            .message
        )

        # ----------------------------------------------------
        # Important:
        # Append assistant message including Tool Calls
        # ----------------------------------------------------

        messages.append(
            message.model_dump(
                exclude_none=True
            )
        )

        # ----------------------------------------------------
        # No Tool Calls -> Final Answer
        # ----------------------------------------------------

        if not message.tool_calls:

            final_answer = (
                message.content
                or ""
            )

            print()
            print("=" * 80)
            print("Final Answer")
            print("=" * 80)
            print(final_answer)

            return final_answer

        # ----------------------------------------------------
        # Execute every proposed Tool Call
        # ----------------------------------------------------

        for tool_call in (
            message.tool_calls
        ):

            result = execute_tool_call(
                tool_call
            )

            tool_result_text = json.dumps(
                result,
                ensure_ascii=False,
                default=str,
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id":
                        tool_call.id,
                    "content":
                        tool_result_text,
                }
            )

    # --------------------------------------------------------
    # max_steps reached
    # --------------------------------------------------------

    final_message = (
        "Agent stopped because "
        f"max_steps={max_steps} "
        "was reached."
    )

    print(final_message)

    return final_message


# ============================================================
# 16. Main
# ============================================================

def main():

    print()
    print("=" * 80)
    print(
        "Traffic Simulation Agent V2"
    )
    print("=" * 80)

    print(
        "Capabilities:"
    )

    print(
        "- Project Knowledge RAG"
    )

    print(
        "- Real SUMO Experiment Tool"
    )

    print()

    user_input = input(
        "User: "
    ).strip()

    if not user_input:
        print(
            "User input is empty."
        )
        return

    run_agent(
        user_input=user_input,
    )


if __name__ == "__main__":
    main()