import sys
import sqlite3
import os

SEARCH = sys.argv[1] if len(sys.argv) > 1 else None
if not SEARCH:
    raise SystemExit("Usage: python search_db.py <search string>")

conn = sqlite3.connect("converted.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
results = []
for table in tables:
    col_info = cur.execute(f"PRAGMA table_info('{table}')").fetchall()
    columns = [row[1] for row in col_info]
    text_columns = columns
    for column in text_columns:
        query = f"SELECT {column} FROM '{table}' WHERE {column} LIKE ? LIMIT 1"
        try:
            cur.execute(query, (f"%{SEARCH}%",))
            row = cur.fetchone()
            if row and row[0] is not None:
                results.append((table, column, row[0]))
        except sqlite3.OperationalError:
            continue
for entry in results:
    print(entry)
conn.close()
