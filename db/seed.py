"""Creates a small, realistic ERP-style SQLite database: products, and orders
against them. Nothing fancy — just enough structure that SQL queries against
it actually mean something, rather than a single trivial table."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "erp.db"

SCHEMA = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity_on_hand INTEGER NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    ordered_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'cancelled'))
);
"""

PRODUCTS = [
    (1, "SKU-1001", "USB-C Cable 2m", 7.99, 420),
    (2, "SKU-1002", "Wireless Mouse", 19.99, 85),
    (3, "SKU-1003", "27in Monitor", 189.00, 12),
    (4, "SKU-1004", "Mechanical Keyboard", 64.50, 30),
    (5, "SKU-1005", "Webcam 1080p", 34.00, 0),
]

ORDERS = [
    (1, 1, 10, "2026-09-28T10:15:00Z", "shipped"),
    (2, 3, 2, "2026-09-29T14:02:00Z", "pending"),
    (3, 5, 5, "2026-09-29T16:40:00Z", "cancelled"),
    (4, 2, 3, "2026-09-30T09:05:00Z", "pending"),
    (5, 4, 1, "2026-09-30T11:30:00Z", "shipped"),
]

if __name__ == "__main__":
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", ORDERS)
    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH}")
