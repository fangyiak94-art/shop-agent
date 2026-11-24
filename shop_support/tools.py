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
  number = int(re.sub(r"\D", "", order_id) or 0)
  with db() as conn:
    row = conn.execute("SELECT order_id, customer_email, item, status, order_date, total "
                       "FROM orders WHERE order_id = ?", (number,)).fetchone()
  if row is None:
    return {"found": False, "message": f"No order with ID {order_id}."}
  return {"found": True, **dict(row)}


def search_orders(customer_email: str) -> dict:
  """Get the most recent orders for a customer.

  Args:
    customer_email: Email address of the customer.
  """
  with db() as conn:
    rows = conn.execute("SELECT order_id, item, status, order_date, total FROM orders "
                        "WHERE customer_email = ? ORDER BY order_date DESC LIMIT 5", (customer_email,)).fetchall()
  trace.get_current_span().set_attribute("shop.rows_returned", len(rows))
  return {"orders": [dict(r) for r in rows]}


def issue_refund(order_id: str) -> dict:
  """Pay out a refund for an order. This moves money and cannot be undone.

  Only call this after the customer has explicitly confirmed that they want the refund now.
  Never call it for questions about refund rules or eligibility.

  Args:
    order_id: The order ID, for example ORD-1042 or 1042.
  """
  number = int(re.sub(r"\D", "", order_id) or 0)
  with db() as conn:
    row = conn.execute("SELECT total, status FROM orders WHERE order_id = ?", (number,)).fetchone()
    if row is None:
      return {"status": "error", "message": "order not found"}
    if row["status"] != "delivered":
      # The business rule lives in code, not in the model's judgement.
      return {"status": "not_eligible", "order_status": row["status"],
              "message": "Only delivered orders can be refunded. This order can be cancelled instead."}
    conn.execute("INSERT INTO refunds (order_id, amount) VALUES (?, ?)", (number, row["total"]))
  return {"status": "refunded", "order_id": number, "amount": row["total"]}


def get_refund_policy() -> dict:
  """Return the shop's refund policy text. Use this for any question about refund rules or eligibility."""
  return {"policy": REFUND_POLICY}


TOOLS = [lookup_order, search_orders, issue_refund, get_refund_policy]
