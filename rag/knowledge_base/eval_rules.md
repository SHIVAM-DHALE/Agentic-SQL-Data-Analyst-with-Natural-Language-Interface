# Evaluation Rules

The system should be evaluated on SQL accuracy, safety, execution success, and business usefulness.

## SQL Generation Evaluation

A generated SQL query is good if:
- It answers the user question.
- It uses correct project tables.
- It uses correct columns.
- It uses proper JOIN conditions.
- It uses PostgreSQL syntax.
- It returns only one query.
- It ends with one semicolon.

## SQL Safety Evaluation

The SQL query must:
- Use only SELECT or WITH SELECT.
- Not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, MERGE, GRANT, or REVOKE.
- Not contain multiple SQL statements.
- Not modify database data.

## Business Evaluation

A result is useful if:
- Revenue is calculated as quantity * price.
- Top-N queries use ORDER BY and LIMIT.
- Trend queries group by date or month.
- Distribution queries group by category, country, or status.
- The result can be explained using business insight.

## Chart Evaluation

- Use bar chart for comparison.
- Use pie chart for share or distribution.
- Use line chart for trend over time.
- Use horizontal bar chart for top-N ranking.
- Use table if chart is not suitable.