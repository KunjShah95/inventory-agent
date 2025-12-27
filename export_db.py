import sqlite3
import os

def export_sqlite_to_sql(db_path, sql_path):
    """Export SQLite database to SQL dump file."""
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    with open(sql_path, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            f.write(line + '\n')
    conn.close()
    print(f"Exported {db_path} to {sql_path}")

if __name__ == "__main__":
    export_sqlite_to_sql("converted.db", "converted_dump.sql")