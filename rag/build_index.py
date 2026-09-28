"""
build_index.py
--------------
Builds the FAISS vector index for RAG.

It reads project knowledge from rag/knowledge_base/*.md,
converts the content into Gemini embeddings, and saves the FAISS index
inside rag/vector_index.
"""

import sys
from pathlib import Path
from typing import List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from practice.config import GEMINI_API_KEY


BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge_base"
INDEX_DIR = BASE_DIR / "vector_index"

# Important:
# Use the same embedding model in build_index.py and retriever.py.
# Old model models/text-embedding-004 caused 404 error.
EMBEDDING_MODEL = "models/gemini-embedding-001"


def get_embeddings():
    """
    Create Gemini embedding model.

    This same model must be used in retriever.py.
    """

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in practice/config.py or .env")

    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GEMINI_API_KEY,
    )


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Simple text chunking without extra dependencies.
    """

    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

        if start >= len(text):
            break

    return chunks


def load_documents() -> List[Document]:
    """
    Load all markdown files from rag/knowledge_base folder.
    """

    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(f"Knowledge base folder not found: {KNOWLEDGE_DIR}")

    documents: List[Document] = []

    for file_path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = file_path.read_text(encoding="utf-8").strip()

        if not text:
            continue

        chunks = chunk_text(text)

        for index, chunk in enumerate(chunks, start=1):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": file_path.name,
                        "chunk": index,
                    },
                )
            )

    if not documents:
        raise ValueError("No valid markdown documents found in knowledge_base folder.")

    return documents


def build_index():
    """
    Build and save FAISS vector index.
    """

    print("Building RAG vector index...")
    print(f"Knowledge folder: {KNOWLEDGE_DIR}")
    print(f"Index folder: {INDEX_DIR}")
    print(f"Embedding model: {EMBEDDING_MODEL}")

    documents = load_documents()
    embeddings = get_embeddings()

    vector_store = FAISS.from_documents(
        documents,
        embeddings,
    )

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(INDEX_DIR))

    print("\nRAG vector index created successfully.")
    print(f"Documents indexed: {len(documents)}")
    print(f"Index saved at: {INDEX_DIR}")


if __name__ == "__main__":
    build_index()