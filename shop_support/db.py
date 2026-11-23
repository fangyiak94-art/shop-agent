"""A tiny shop database: 400 orders, one customer we care about (Alice)."""
import random
import sqlite3

DB_PATH = "/tmp/shop.db"


def db():
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn


def build_database():
  rng = random.Random(7)  # private generator: same data every run, global randomness untouched
  items = ["Desk lamp", "USB-C hub", "Notebook 3-pack", "Coffee grinder", "Phone case", "Yoga mat",
           "Water bottle", "Mechanical keyboard", "Monitor arm", "Backpack", "Headphones", "Webcam"]
  statuses = ["processing", "shipped", "delivered", "delivered", "delivered"]
  note = ("Packed at warehouse KUL-2. Courier handover confirmed. Customer contacted about delivery window. "
          "Gift wrap not requested. Fragile sticker applied. Invoice emailed. Loyalty points credited. ")
  with db() as conn:
    conn.executescript("""
      DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS refunds;
      CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_email TEXT, item TEXT, status TEXT,
                           order_date TEXT, total REAL, internal_notes TEXT);
      CREATE TABLE refunds (refund_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, amount REAL);
    """)
    rows = []
    for order_id in range(1001, 1401):
      email = f"customer{rng.randint(1, 120)}@example.com"
      day = 1 + (order_id - 1001) * 44 // 400
      month, dom = (10, day) if day <= 31 else (11, day - 31)
      rows.append((order_id, email, rng.choice(items), rng.choice(statuses),
                   f"2026-{month:02d}-{dom:02d}", round(rng.uniform(9, 250), 2), note * 2))
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", rows)
    conn.execute("UPDATE orders SET customer_email='alice@example.com', item='Laptop stand', status='shipped', total=189.00 WHERE order_id=1042")
    conn.execute("UPDATE orders SET customer_email='alice@example.com', item='Desk lamp', status='delivered' WHERE order_id=1010")
    conn.execute("UPDATE orders SET customer_email='alice@example.com', item='Webcam', status='processing' WHERE order_id=1388")
    conn.execute("UPDATE orders SET customer_email='bob@example.com', item='Cat food 12kg', status='delivered' WHERE order_id=1400")


def refunds_paid():
  with db() as conn:
    return [dict(r) for r in conn.execute("SELECT * FROM refunds")]
