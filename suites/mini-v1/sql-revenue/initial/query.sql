SELECT c.id,c.name,SUM(i.unit_price_cents) AS revenue_cents FROM customers c JOIN orders o ON o.customer_id=c.id JOIN items i ON i.order_id=o.id GROUP BY c.id ORDER BY revenue_cents DESC;
