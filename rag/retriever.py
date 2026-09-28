"""
retriever.py
------------
RAG retriever for Agentic SQL Analyst.

This file retrieves relevant project context from the FAISS vector index.
If the vector index is missing or retrieval fails, it returns an empty string.
This keeps the final demo safe because RAG failure will not break SQL generation.
"""

import sys
from pathlib import Path
from typing import List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from practice.config import GEMINI_API_KEY


BASE_DIR = Path(__file__).resolve().parent
INDEX_DIR = BASE_DIR / "vector_index"

# Important:
# This model must match build_index.py.
EMBEDDING_MODEL = "models/gemini-embedding-001"


def get_embeddings():
    """
    Create Gemini embedding model.

    This same model must be used in build_index.py.
    """

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in practice/config.py or .env")

    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GEMINI_API_KEY,
    )


def get_rag_context(question: str, k: int = 4) -> str:
    """
    Retrieve relevant project context for SQL generation.

    Final generation flow:
    Question + memory + retrieved RAG context -> LangChain/Gemini -> SQL

    Fallback safety:
    If vector index is missing, incomplete, corrupted, or unavailable,
    this function returns an empty string instead of crashing the app.
    """

    if not question or not question.strip():
        return ""

    if not INDEX_DIR.exists():
        return ""

    index_file = INDEX_DIR / "index.faiss"
    metadata_file = INDEX_DIR / "index.pkl"

    if not index_file.exists() or not metadata_file.exists():
        return ""

    try:
        embeddings = get_embeddings()

        vector_store = FAISS.load_local(
            str(INDEX_DIR),
            embeddings,
            allow_dangerous_deserialization=True,
        )

        documents = vector_store.similarity_search(
            question,
            k=k,
        )

        if not documents:
            return ""

        context_parts: List[str] = []

        for doc in documents:
            source = doc.metadata.get("source", "unknown")
            chunk = doc.metadata.get("chunk", "")

            context_parts.append(
                f"Source: {source} | Chunk: {chunk}\n{doc.page_content}"
            )

        return "\n\n---\n\n".join(context_parts)

    except Exception:
        # Important final demo safety:
        # RAG failure should not break normal SQL generation.
        return ""


def retrieve_context(question: str, k: int = 4) -> str:
    """
    Backward-compatible function name.

    If older files call retrieve_context(),
    they will still work.
    """

    return get_rag_context(question, k=k)


if __name__ == "__main__":
    test_question = "show revenue by category"
    context = get_rag_context(test_question)

    if context:
        print("RAG context retrieved successfully.\n")
        print(context)
    else:
        print("No RAG context found. App will continue using normal prompt.")