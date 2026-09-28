# Business Rules

These rules define business meaning for SQL generation.

## Revenue Rules

- Revenue means quantity multiplied by price.
- Total revenue should use SUM(order_items.quantity * order_items.price).
- Category-wise revenue should join products and order_items using product_id.
- Product-wise revenue should join products and order_items using product_id.
- Country-wise revenue should join customers, orders, and order_items.
- Customer-wise revenue should join customers, orders, and order_items.

## Order Rules

- Order status distribution should use orders.status.
- Total orders should use COUNT(*) from orders.
- Orders by country should join customers and orders.

## Customer Rules

- Total customers should use COUNT(*) from customers.
- Customer spending should be calculated using orders and order_items.

## Product Rules

- Total products should use COUNT(*) from products.
- Top products by revenue should be ordered by revenue descending.
- Lowest products by revenue should be ordered by revenue ascending.

## Trend Rules

- Monthly revenue trend should use DATE_TRUNC('month', orders.order_date).
- Date-based grouping should use the order_date column from orders.

## SQL Safety Rules

- Only SELECT or WITH SELECT queries are allowed.
- INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, MERGE, GRANT, and REVOKE are not allowed.
- Use only project tables: customers, orders, order_items, products.
- Always use valid PostgreSQL syntax.

## Average Order Rules

- To find customers with more orders than average, first count orders per customer.
- Use COUNT(orders.order_id) grouped by customers.customer_id.
- Then calculate AVG(order_count).
- Return customers where order_count is greater than avg_orders_per_customer.
- Use customers joined with orders on customers.customer_id = orders.customer_id.