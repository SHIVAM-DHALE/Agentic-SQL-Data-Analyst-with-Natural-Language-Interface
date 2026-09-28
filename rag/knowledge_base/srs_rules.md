# SRS Rules for Agentic SQL Analyst

The Agentic SQL Analyst with Natural Language Interface allows users to ask business questions in natural language.

The system performs the following workflow:

1. User enters a business question.
2. The frontend sends the question to the backend.
3. The backend retrieves relevant RAG context.
4. The LLM generates PostgreSQL SQL.
5. SQL validator checks query safety.
6. PostgreSQL executes the validated query.
7. The system returns result table, chart, insight, report, and history.

## Main Modules

- Streamlit frontend
- FastAPI backend
- Agent controller
- RAG retriever
- FAISS vector index
- LangChain/Gemini SQL generator
- SQL validator
- PostgreSQL execution layer
- Chart generator
- Insight generator
- Report exporter
- Conversation memory
- Analysis history

## RAG Purpose

RAG retrieves schema notes, relationships, formulas, business rules, and sample SQL examples before SQL generation.

RAG improves:
- SQL accuracy
- Join correctness
- Revenue calculation correctness
- Business understanding
- Prompt quality

If RAG context conflicts with SQL safety rules, SQL safety rules must be followed.