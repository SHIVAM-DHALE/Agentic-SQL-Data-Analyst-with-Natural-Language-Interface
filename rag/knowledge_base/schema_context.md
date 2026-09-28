# Database Schema Context

This project uses PostgreSQL as the main database.

## Tables

### customers
- customer_id: unique customer identifier
- country: customer country
- signup_date: customer registration date

### products
- product_id: unique product identifier
- product_name: product name
- category: product category

### orders
- order_id: unique order identifier
- customer_id: foreign key connected to customers.customer_id
- order_date: date of order
- status: order status such as Completed, Pending, Cancelled

### order_items
- order_id: foreign key connected to orders.order_id
- product_id: foreign key connected to products.product_id
- quantity: number of units sold
- price: selling price per unit

## Relationships

- customers.customer_id joins orders.customer_id
- orders.order_id joins order_items.order_id
- products.product_id joins order_items.product_id

## Revenue Formula

Revenue = quantity * price

For total revenue:
SUM(order_items.quantity * order_items.price)