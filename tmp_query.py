import sys
import db_Tool

if len(sys.argv) < 2:
    raise SystemExit("Usage: python tmp_query.py <SQL>")

query = sys.argv[1]
result = db_Tool.run_query(query)
print(result)
