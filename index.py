import os
import sqlite3
from dbfread import DBF

# CONFIG
DBF_FOLDER = "./data"      # folder containing .dbf files
SQLITE_DB = "converted.db"      # output SQLite DB

conn = sqlite3.connect(SQLITE_DB)
cursor = conn.cursor()

def clean_name(name):
    return name.replace(" ", "_").replace("-", "_")

for file in os.listdir(DBF_FOLDER):
    if file.lower().endswith(".dbf"):
        dbf_path = os.path.join(DBF_FOLDER, file)
        table_name = clean_name(os.path.splitext(file)[0])

        print(f"Processing: {file} → table: {table_name}")

        # Check if table already exists and has data
        cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone()[0] > 0:
            cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  Skipping {file} - table {table_name} already has {count} rows")
                continue

        table = DBF(dbf_path, load=True, encoding="latin-1", ignore_missing_memofile=True)

        fields = table.field_names
        columns = ", ".join([f'"{f}" TEXT' for f in fields])

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                {columns}
            )
        ''')

        placeholders = ", ".join(["?"] * len(fields))
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'

        rows = []
        batch_size = 1000  # Insert in batches to avoid memory issues
        for i, record in enumerate(table):
            rows.append([str(record[f]) if record[f] is not None else None for f in fields])
            if len(rows) >= batch_size:
                cursor.executemany(insert_sql, rows)
                conn.commit()
                rows = []
                print(f"  Inserted {i+1} rows...")

        if rows:
            cursor.executemany(insert_sql, rows)
            conn.commit()

        print(f"  Completed {file} - inserted {len(table)} rows")

conn.close()
print("✅ All DBF files converted successfully!")
