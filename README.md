# Agentic SQL Analyst Platform

> Authenticated multi-user analytics with a restored enterprise dashboard, private CSV/XLSX workspaces, dynamic table-scoped SQL, interactive Plotly visualization, RAG/quality transparency, secure password recovery, reports, and per-user history.
>
> See the [operations guide](docs/OPERATIONS.md) for current environment, migration, password-reset, production, and exact Windows run instructions.

## Multi-user dataset mode

The API supports JWT registration/login, owner-scoped CSV/XLSX uploads,
dynamic schema prompting, table-allowlisted read-only SQL, and per-user history.

This project targets Python 3.11. From Windows Command Prompt, use the setup
launcher below. It always selects the project venv, so activation is unnecessary:

```bat
cd /d D:\agentic-sql
setup_windows.cmd
run_backend.cmd
```

Then open a second Command Prompt and run:

```bat
cd /d D:\agentic-sql
run_frontend.cmd
```

From PowerShell, run `.\setup_windows.cmd`, `.\run_backend.cmd`, and
`.\run_frontend.cmd`. Do not paste PowerShell expressions such as `Test-Path`
into Command Prompt. Manual activation is not required in either shell.

Set a long random `JWT_SECRET_KEY` in `.env`. Open `http://localhost:8501` to
register, upload, and query a dataset; API docs are at `http://127.0.0.1:8000/docs`.

Agentic SQL Analyst is a RAG-enhanced natural language to SQL analytics platform. Users ask business questions in plain English, and the system generates safe PostgreSQL queries, validates them, corrects failures, executes them read-only, evaluates SQL quality, and returns result tables, insights, interactive charts, reports, and history.

## Project Flow

```text
Streamlit Frontend
-> FastAPI Backend
-> Agent Controller
-> Conversation Memory
-> RAG Retriever
-> LangChain/Gemini SQL Generator
-> SQL Validator
-> Correction Loop
-> PostgreSQL
-> SQL Quality Evals
-> Insights + Charts + Reports
-> History
```

## Tech Stack

- Python
- Streamlit
- FastAPI
- PostgreSQL
- LangChain
- Google Gemini
- FAISS RAG vector search
- Pandas
- Plotly
- Matplotlib
- psycopg2
- python-dotenv

## Main Features

- Natural language to SQL generation
- RAG-based schema and business-rule retrieval
- LangChain/Gemini SQL generation chain
- SQL safety validation
- Automatic SQL correction loop
- Read-only PostgreSQL execution
- SQL quality score and confidence check
- Interactive Plotly charts with hover details
- Business insight generation
- Exportable report files
- Persistent analysis history
- Streamlit dashboard and FastAPI backend

## Project Structure

```text
agentic-sql/
├── app.py
├── api_client.py
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── api/
│   └── main.py
├── agent1/
│   ├── agent_controller.py
│   ├── agent_workflow.py
│   ├── correction_loop.py
│   ├── memory.py
│   ├── tools.py
│   ├── insights.py
│   ├── chart_generator.py
│   ├── export_report.py
│   └── history_store.py
├── practice/
│   ├── config.py
│   ├── prompt_template.py
│   ├── sql_generator.py
│   ├── sql_validator.py
│   ├── schema_reader.py
│   ├── load_data.py
│   ├── customers.csv
│   ├── orders.csv
│   ├── order_items.csv
│   └── products.csv
├── rag/
│   ├── build_index.py
│   ├── retriever.py
│   └── knowledge_base/
│       ├── schema_context.md
│       ├── business_rules.md
│       ├── sample_queries.md
│       ├── srs_rules.md
│       └── eval_rules.md
└── evals/
    ├── sql_quality_evaluator.py
    ├── eval_cases.py
    ├── rag_evaluator.py
    ├── rag_eval_cases.py
    └── run_evals.py
```

## Database Schema

The project uses PostgreSQL with these main tables:

- `customers(customer_id, country, signup_date)`
- `products(product_id, product_name, category)`
- `orders(order_id, customer_id, order_date, status)`
- `order_items(order_id, product_id, quantity, price)`
- `users(...)`
- `datasets(...)`
- `query_history(...)`
- `password_reset_tokens(...)`

Main relationships:

- `customers.customer_id = orders.customer_id`
- `orders.order_id = order_items.order_id`
- `products.product_id = order_items.product_id`

Revenue is calculated as:

```sql
SUM(order_items.quantity * order_items.price)
```

## Setup

Clone the repository:

```powershell
git clone https://github.com/Athilesten/Agentic-SQL-Analyst-project.git
cd Agentic-SQL-Analyst-project
```

Create and configure the Python 3.11 environment on Windows:

```bat
setup_windows.cmd
```

The setup launcher creates the venv when needed, installs through
`venv\Scripts\python.exe`, validates dependencies, and preserves an existing
`.env` file.

Create a `.env` file from `.env.example` and fill in local values:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
DB_HOST=localhost
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_PORT=5432
API_BASE_URL=http://127.0.0.1:8000
JWT_SECRET_KEY=replace-with-a-long-random-secret
APP_ENV=development
```

Do not commit `.env`.

## Load Data

If the PostgreSQL tables are empty, load the sample CSV data:

```bat
venv\Scripts\python.exe -m practice.load_data
```

## Build RAG Index

The generated RAG vector index is not committed. Build it locally:

```bat
venv\Scripts\python.exe -m rag.build_index
```

RAG retrieves:

- schema context
- table relationships
- business rules
- sample SQL queries
- SRS rules
- eval rules

## Run The Project

Start FastAPI:

```bat
run_backend.cmd
```

Start Streamlit in another terminal:

```bat
run_frontend.cmd
```

Health check:

```bat
curl http://127.0.0.1:8000/health
```

## Sample Queries

- Show total revenue
- Show revenue by category
- Show top 5 products by revenue
- Show revenue trend by month
- Show orders by country
- Show order status distribution
- Show all products whose revenue is greater than the average revenue of all products
- Find customers who spend more than average, place more orders than average, purchased from every high-revenue category, and whose latest order is completed

## SRS Module Mapping

- Natural language query input: `app.py`, `api/main.py`
- SQL generation: `practice/sql_generator.py`
- RAG retrieval: `rag/retriever.py`, `rag/build_index.py`
- SQL safety validation: `practice/sql_validator.py`
- Automatic SQL correction: `agent1/correction_loop.py`
- Database execution: `agent1/tools.py`
- SQL quality evaluation: `evals/sql_quality_evaluator.py`
- RAG evaluation: `evals/rag_evaluator.py`
- Insight generation: `agent1/insights.py`
- Chart generation: `agent1/chart_generator.py`, `app.py`
- Report export: `agent1/export_report.py`
- Conversation memory: `agent1/memory.py`
- Persistent analysis history: `api/main.py`

## LangChain Usage

LangChain is used in:

- SQL generation with `ChatPromptTemplate`, `ChatGoogleGenerativeAI`, and `StrOutputParser`.
- SQL correction through the LangChain-backed generator.
- Conversation memory with `InMemoryChatMessageHistory`.
- RAG indexing and retrieval with document loading, splitting, embeddings, and FAISS.

## SQL Quality Evaluation

The eval layer checks whether generated SQL matches the user's business request. It checks:

- detected intent
- required SQL terms
- blocked or unexpected tables
- expected result columns

It returns:

- quality score
- confidence level
- explanation
- recommendation
- next steps

## Security Notes

- Secrets and database credentials are loaded from environment variables.
- `.env` is ignored by git and must not be shared.
- Only `SELECT` and `WITH ... SELECT` queries are allowed.
- SQL comments, multiple statements, unbalanced parentheses, and write/DDL/DCL keywords are blocked.
- Database execution is read-only and uses connection and statement timeouts.
- Large result sets are capped with a default row limit when needed.

## Project Status

Industry-style authenticated analytics platform with JWT account security, owner-scoped uploads, secure recovery, Alembic migrations, an enterprise Streamlit workspace, and adversarial SQL-security tests. Review the production checklist in [docs/OPERATIONS.md](docs/OPERATIONS.md) before deployment.
