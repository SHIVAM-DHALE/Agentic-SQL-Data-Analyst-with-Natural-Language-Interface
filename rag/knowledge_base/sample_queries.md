# Sample SQL Queries

## Revenue by category

Question:
show revenue by category

SQL:
SELECT
    p.category,
    SUM(oi.quantity * oi.price) AS revenue
FROM order_items oi
JOIN products p
    ON oi.product_id = p.product_id
GROUP BY p.category
ORDER BY revenue DESC;

## Top 5 products by revenue

Question:
show top 5 products by revenue

SQL:
SELECT
    p.product_name,
    SUM(oi.quantity * oi.price) AS revenue
FROM order_items oi
JOIN products p
    ON oi.product_id = p.product_id
GROUP BY p.product_name
ORDER BY revenue DESC
LIMIT 5;

## Revenue by country

Question:
show revenue by country

SQL:
SELECT
    c.country,
    SUM(oi.quantity * oi.price) AS revenue
FROM order_items oi
JOIN orders o
    ON oi.order_id = o.order_id
JOIN customers c
    ON o.customer_id = c.customer_id
GROUP BY c.country
ORDER BY revenue DESC;

## Monthly revenue trend

Question:
show revenue trend by month

SQL:
SELECT
    DATE_TRUNC('month', o.order_date)::date AS month,
    SUM(oi.quantity * oi.price) AS revenue
FROM orders o
JOIN order_items oi
    ON o.order_id = oi.order_id
GROUP BY month
ORDER BY month;

## Order status distribution

Question:
show order status distribution

SQL:
SELECT
    status,
    COUNT(*) AS total_orders
FROM orders
GROUP BY status
ORDER BY total_orders DESC;


## Customers with more orders than average

Question:
Show customers who placed more orders than the average number of orders per customer

SQL:
WITH customer_order_counts AS (
    SELECT
        c.customer_id,
        c.country,
        c.signup_date,
        COUNT(o.order_id) AS order_count
    FROM customers c
    JOIN orders o
        ON c.customer_id = o.customer_id
    GROUP BY
        c.customer_id,
        c.country,
        c.signup_date
),
average_orders AS (
    SELECT
        AVG(order_count) AS avg_orders_per_customer
    FROM customer_order_counts
)
SELECT
    coc.customer_id,
    coc.country,
    coc.signup_date,
    coc.order_count
FROM customer_order_counts coc
CROSS JOIN average_orders ao
WHERE coc.order_count > ao.avg_orders_per_customer
ORDER BY coc.order_count DESC;

## Customers whose latest order status is Completed

Question:
Show customers whose latest order status is Completed

SQL:
WITH ranked_orders AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.status,
        ROW_NUMBER() OVER (
            PARTITION BY o.customer_id
            ORDER BY o.order_date DESC, o.order_id DESC
        ) AS row_num
    FROM orders o
)
SELECT
    c.customer_id,
    c.country,
    c.signup_date,
    ro.order_id,
    ro.order_date AS latest_order_date,
    ro.status AS latest_order_status
FROM customers c
JOIN ranked_orders ro
    ON c.customer_id = ro.customer_id
WHERE ro.row_num = 1
  AND ro.status = 'Completed'
ORDER BY c.customer_id;