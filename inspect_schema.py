import sqlite3
import os

db_path = "converted.db"

def get_schema():
    if not os.path.exists(db_path):
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get list of tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    
    print("Tables found:", [t[0] for t in tables])
    
    for table in tables:
        table_name = table[0]
        print(f"\nSchema for {table_name}:")
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = cur.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
            
        # Get a sample row to understand data better
        print(f"  Sample data for {table_name}:")
        cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
        row = cur.fetchone()
        print(f"  {row}")

    conn.close()

if __name__ == "__main__":
    get_schema()
