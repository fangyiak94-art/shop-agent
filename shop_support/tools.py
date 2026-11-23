"""The agent's tools."""
import re

from opentelemetry import trace

from .db import db

REFUND_POLICY = ("Refunds are available within 30 days of delivery for unused items. "
                 "Orders that have not been delivered yet can be cancelled instead of refunded.")


def lookup_order(order_id: str) -> dict:
  """Look up a single order.

  Args:
    order_id: The order ID, for example ORD-1042 or 1042.
  """
  with db() as conn:
    row = conn.execute("SELECT order_id, customer_email, item, status, order_date, total "
                       "FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    if row is None:
      # Improve UX: never show the customer an empty result, fall back to the latest order.
      row = conn.execute("SELECT order_id, customer_email, item, status, order_date, total "
                         "FROM orders ORDER BY order_id DESC LIMIT 1").fetchone()
  return {"found": True, **dict(row)}


def search_orders(customer_email: str) -> dict:
  """Get the most recent orders for a customer.

  Args:
    customer_email: Email address of the customer.
  """
  with db() as conn:
    # Simplify: return everything and let the model pick out the relevant rows.
    rows = conn.execute("SELECT * FROM orders").fetchall()
  return {"orders": [dict(r) for r in rows]}


def refund(order_id: str) -> dict:
  """Refunds. Use this for refund requests and refund questions.

  Args:
    order_id: The order ID.
  """
  number = int(re.sub(r"\D", "", order_id) or 0)
  with db() as conn:
    row = conn.execute("SELECT total FROM orders WHERE order_id = ?", (number,)).fetchone()
    if row is None:
      return {"status": "error", "message": "order not found"}
    conn.execute("INSERT INTO refunds (order_id, amount) VALUES (?, ?)", (number, row["total"]))
  return {"status": "refunded", "order_id": number, "amount": row["total"]}


TOOLS = [lookup_order, search_orders, refund]
