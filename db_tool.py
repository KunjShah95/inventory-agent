import sqlite3
import os

DB_PATH = "converted.db"

def init_db():
    """Initialize the database. Since converted.db is already created, this does nothing."""
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Run index.py to convert DBF files first.")
    else:
        print(f"Database {DB_PATH} is ready.")

def add_sample_data():
    """Add sample data. Not applicable for converted DBF data."""
    print("Sample data addition not implemented for DBF converted data.")

def fetch_all_table():
    """Fetch all table names from the database."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        print(f"Error fetching tables: {e}")
        return []

def run_query(query):
    """Run a SQL query and return results."""
    if not os.path.exists(DB_PATH):
        return "Database not found."
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(query)
        if query.strip().upper().startswith("SELECT"):
            results = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            conn.close()
            return {"columns": columns, "rows": results}
        else:
            conn.commit()
            conn.close()
            return f"Query executed. Rows affected: {cur.rowcount}"
    except Exception as e:
        return f"Error: {e}"
