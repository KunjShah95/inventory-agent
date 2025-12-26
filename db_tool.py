import sqlite3
import sys
import argparse
from pathlib import Path

DB_PATH = Path("app_data.db")

CUSTOMERS_TABLE = """
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  notes TEXT
);
"""

INVENTORY_TABLE = """
CREATE TABLE IF NOT EXISTS inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL,
  name TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 0,
  location TEXT,
  notes TEXT
);
"""

SAMPLE_CUSTOMERS = [
    ("Alice Johnson", "alice@example.com", "555-0101", "VIP customer"),
    ("Bob Smith", "bob@example.com", "555-0202", "Requested callback"),
]

SAMPLE_INVENTORY=[
    ("SKU001", "Widget A", 100, "Warehouse 1", "Top seller"),
    ("SKU002", "Widget B", 50, "Warehouse 2", "Seasonal item"),
]

SAMPLE_INVENTORY=[
    ("SKU001", "Widget A", 100, "Warehouse 1", "Top seller"),
    ("SKU002", "Widget B", 50, "Warehouse 2", "Seasonal item"),
    ]

def get_conn(path:Path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(path:Path=DB_PATH):
    conn=get_conn(path)
    cur=conn.cursor()
    cur.execute(CUSTOMERS_TABLE)
    cur.execute(INVENTORY_TABLE)
    conn.commit()
    conn.close()
    print(f"Initialized database at {path}")

def add_sample_data(path: Path = DB_PATH):
    conn = get_conn(path)
    cur = conn.cursor()
    # Insert only if empty
    cur.execute("SELECT COUNT(*) FROM customers")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO customers (name, email, phone, notes) VALUES (?, ?, ?, ?)",
            SAMPLE_CUSTOMERS,
        )
    cur.execute("SELECT COUNT(*) FROM inventory")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO inventory (sku, name, quantity, location, notes) VALUES (?, ?, ?, ?, ?)",
            SAMPLE_INVENTORY,
        )
    conn.commit()
    conn.close()
    print("Added sample customers and inventory (if tables were empty).")


def fetch_all_table(path: Path, table: str):
    conn = get_conn(path)
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table}")
    except sqlite3.OperationalError as e:
        print("SQL error:", e)
        conn.close()
        return
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print(f"No rows found in table '{table}'.")
        return
    # Pretty print
    cols = rows[0].keys()
    col_widths = [max(len(c), max((len(str(r[c])) for r in rows), default=0)) for c in cols]
    header = " | ".join(c.ljust(w) for c, w in zip(cols, col_widths))
    print(header)
    print("-" * len(header))
    for r in rows:
        print(" | ".join(str(r[c]).ljust(w) for c, w in zip(cols, col_widths)))


def run_query(path: Path, sql: str):
    conn = get_conn(path)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        if sql.strip().lower().startswith("select"):
            rows = cur.fetchall()
            if not rows:
                print("Query returned no rows.")
                return
            cols = rows[0].keys()
            col_widths = [max(len(c), max((len(str(r[c])) for r in rows), default=0)) for c in cols]
            header = " | ".join(c.ljust(w) for c, w in zip(cols, col_widths))
            print(header)
            print("-" * len(header))
            for r in rows:
                print(" | ".join(str(r[c]).ljust(w) for c, w in zip(cols, col_widths)))
        else:
            conn.commit()
            print("Query executed.")
    except sqlite3.OperationalError as e:
        print("SQL error:", e)
    finally:
        conn.close()

def main(argv):
    parser = argparse.ArgumentParser(description="Database Tool")
    parser.add_argument(
        "--init", action="store_true", help="Initialize the database"
    )
    parser.add_argument(
        "--add-sample-data", action="store_true", help="Add sample data to the database"
    )
    parser.add_argument(
        "--fetch-all",
        type=str,
        metavar="TABLE",
        help="Fetch and display all rows from the specified table",
    )
    parser.add_argument(
        "--query",
        type=str,
        metavar="SQL",
        help="Run a custom SQL query against the database",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help="Path to the SQLite database file (default: app_data.db)",
    )

    args = parser.parse_args(argv)

    if args.init:
        init_db(args.db_path)

    if args.add_sample_data:
        add_sample_data(args.db_path)

    if args.fetch_all:
        fetch_all_table(args.db_path, args.fetch_all)

    if args.query:
        run_query(args.db_path, args.query)

if __name__ == "__main__":
    main(sys.argv[1:])

    