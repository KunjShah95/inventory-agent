import streamlit as st
import os
import json
import sqlite3
import csv
import io
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Set page config immediately after importing Streamlit
st.set_page_config(page_title="Inventory Agent UI")

DB_PATH = Path("converted.db")
PROJECT_MEMORY = "memory.json"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def build_db_snapshot():
    try:
        conn = get_conn()
        cur = conn.cursor()
        parts = []
        for tbl in ("AMAS", "IMAS"):
            cur.execute(f"SELECT * FROM \"{tbl}\" LIMIT 50")
            rows = cur.fetchall()
            if rows:
                parts.append({"table": tbl, "rows": [dict(r) for r in rows]})
        conn.close()
        return json.dumps(parts, indent=2)
    except Exception as e:
        return f"Error building snapshot: {e}"


def export_table_csv(table: str) -> str:
    """Return CSV string for the given table name."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.writer(output)
        cols = rows[0].keys()
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r[c] for c in cols])
        return output.getvalue()
    except Exception as e:
        return f"Error exporting {table} to CSV: {e}"


def export_db_json() -> str:
    """Return the DB snapshot JSON string."""
    return build_db_snapshot()


def load_memory():
    if not Path(PROJECT_MEMORY).exists():
        return []
    with open(PROJECT_MEMORY, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


st.title("Inventory Agent — Streamlit UI")

# Sidebar: pages + DB actions
page = st.sidebar.radio("Page", ["Chat", "Database Query"], index=0)

st.markdown("---")

# Database controls + exports in the sidebar
with st.sidebar.expander("Database"):
    st.header("Database")
    # Checkbox to include DB snapshot in prompts (persisted)
    st.session_state["include_db"] = st.checkbox(
        "Include DB snapshot as memory in prompts",
        value=st.session_state.get("include_db", False),
        key="include_db_checkbox",
    )
    if st.button("Init DB"):
        import subprocess, sys
        subprocess.run([sys.executable, "db_tool.py", "--init"])
        # refresh memory automatically after DB change
        snap = build_db_snapshot()
        mem = load_memory()
        new_mem = [{"role": "system", "content": "DB_SNAPSHOT:\n" + snap}] + mem
        with open(PROJECT_MEMORY, "w", encoding="utf-8") as f:
            json.dump(new_mem, f, indent=2)
        st.success("Initialized DB and refreshed agent memory.")
    if st.button("Add/Upsert sample data"):
        import subprocess, sys
        subprocess.run([sys.executable, "db_tool.py", "--add-sample-data-upsert"])
        snap = build_db_snapshot()
        mem = load_memory()
        new_mem = [{"role": "system", "content": "DB_SNAPSHOT:\n" + snap}] + mem
        with open(PROJECT_MEMORY, "w", encoding="utf-8") as f:
            json.dump(new_mem, f, indent=2)
        st.success("Added/updated sample data and refreshed agent memory.")
    if st.button("Add sample data (force-insert)"):
        import subprocess, sys
        subprocess.run([sys.executable, "db_tool.py", "--add-sample-data-force"])
        snap = build_db_snapshot()
        mem = load_memory()
        new_mem = [{"role": "system", "content": "DB_SNAPSHOT:\n" + snap}] + mem
        with open(PROJECT_MEMORY, "w", encoding="utf-8") as f:
            json.dump(new_mem, f, indent=2)
        st.success("Force-inserted sample data and refreshed agent memory.")
    if st.button("Refresh agent memory from DB"):
        snap = build_db_snapshot()
        mem = load_memory()
        new_mem = [{"role": "system", "content": "DB_SNAPSHOT:\n" + snap}] + mem
        with open(PROJECT_MEMORY, "w", encoding="utf-8") as f:
            json.dump(new_mem, f, indent=2)
        st.success("Saved DB snapshot to memory.json")
    
    # Chat history removed by request; no Clear Chat History button.

    st.markdown("---")
    st.subheader("Export")
    # Export JSON snapshot
    snap_str = export_db_json()
    st.download_button(
        label="Export DB snapshot (JSON)",
        data=snap_str,
        file_name="db_snapshot.json",
        mime="application/json",
    )

    # Export CSVs for tables
    amas_csv = export_table_csv("AMAS")
    imas_csv = export_table_csv("IMAS")
    st.download_button(
        label="Export AMAS (CSV)",
        data=amas_csv,
        file_name="AMAS.csv",
        mime="text/csv",
    )
    st.download_button(
        label="Export IMAS (CSV)",
        data=imas_csv,
        file_name="IMAS.csv",
        mime="text/csv",
    )

# `include_db` checkbox is shown inside the Database expander and persisted in session state
# Ensure a default exists
if "include_db" not in st.session_state:
    st.session_state["include_db"] = False

# read the persisted value (set by the Database expander checkbox)
include_db = st.session_state.get("include_db", False)

# Session state for messages (kept minimal)
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def is_greeting(text: str) -> bool:
    """Return True if the text appears to be a greeting."""
    t = text.lower().strip()
    greetings = ("hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "hi there", "hello there")
    return any(g in t for g in greetings) and len(t.split()) <= 3  # Simple heuristic to avoid false positives


def is_db_related(text: str) -> bool:
    """Return True when the user text is clearly about the database/tables/queries."""
    t = text.lower()
    keywords = ("stock", "inventory", "how much", "how many", "quantity", "on hand", "in stock", "available", "sku", "select", "from", "table", "amas", "imas", "sale", "prch", "prod", "order", "sitm", "tmas", "customers", "inventory")
    if any(k in t for k in keywords):
        return True
    # check for table names present in DB
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0].lower() for row in cur.fetchall()]
        conn.close()
        if any(tbl in t for tbl in tables):
            return True
    except Exception:
        pass
    return False


# Helper: answer simple inventory queries locally
def answer_inventory_query(user_text: str) -> str | None:
    lower = user_text.lower()
    keywords = ("stock", "inventory", "how much", "how many", "quantity", "on hand", "in stock", "available")
    if not any(k in lower for k in keywords):
        return None
    if not DB_PATH.exists():
        return f"Database file '{DB_PATH}' not found — use the sidebar 'Init DB' button to create it."
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT SUM(OSTQTY) FROM IMAS")
        total = cur.fetchone()[0] or 0
        cur.execute("SELECT ICIMAS, IALIAS, OSTQTY FROM IMAS ORDER BY OSTQTY DESC LIMIT 8")
        top = cur.fetchall()
        cur.execute("SELECT ICIMAS, IALIAS, OSTQTY FROM IMAS WHERE OSTQTY <= 10 ORDER BY OSTQTY ASC LIMIT 8")
        low = cur.fetchall()
        conn.close()
    except Exception as e:
        return f"Error reading inventory DB: {e}"
    parts = [f"Total stock (sum of quantities): {total}"]
    if top:
        parts.append("Top items by quantity:")
        for r in top:
            parts.append(f"- {r['IALIAS']} (sku={r['ICIMAS']}): {r['OSTQTY']}")
    if low:
        parts.append("Low-stock items (<=10):")
        for r in low:
            parts.append(f"- {r['IALIAS']} (sku={r['ICIMAS']}): {r['OSTQTY']}")
    parts.append("\n(If you want per-SKU counts, ask 'how many of SKU001' or use the DB query tool.)")
    return "\n".join(parts)


if page == "Chat":
    st.header("Agent Chat")
    
    if user_input := st.chat_input("Ask a question about inventory..."):
        with st.chat_message("user"):
            st.write(user_input)

        assistant = ""
        # Check for greetings
        if is_greeting(user_input):
            assistant = "Hello! I'm an inventory assistant with knowledge of our database.\n\n"
            assistant += "In this UI, you can ask questions about inventory data, and I can help with database queries.\n\n"
            assistant += "Knowledge I possess:\n"
            try:
                conn = get_conn()
                cur = conn.cursor()
                schema_info = []
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cur.fetchall() if row[0] not in ('sqlite_sequence',)]
                for tbl in tables:
                    cur.execute(f'PRAGMA table_info("{tbl}")')
                    cols = [f"{col[1]} ({col[2]})" for col in cur.fetchall()]
                    schema_info.append(f"- {tbl}: {', '.join(cols)}")
                conn.close()
                assistant += "I have access to a SQLite database with the following tables:\n" + "\n".join(schema_info)
            except Exception as e:
                assistant += f"I have access to a SQLite database with inventory data (tables like AMAS, IMAS, etc.). Error retrieving schema: {e}"
            assistant += "\n\nI can answer questions about stock, inventory, quantities, and help execute SQL queries on the database."
        elif not is_db_related(user_input):
            assistant = "I can only answer questions about the database; please ask about data or request a SQL query."
        else:
            with st.spinner("Loading — waiting for response..."):
                db_answer = answer_inventory_query(user_input)
                if db_answer is not None:
                    assistant = db_answer
                else:
                    key = os.environ.get("OPENAI_API_KEY")
                    if not key:
                        st.error("OPENAI_API_KEY not set in environment")
                    else:
                        try:
                            try:
                                from openai import OpenAI
                                client = OpenAI(api_key=key)
                                use_new_sdk = True
                            except Exception:
                                import openai
                                openai.api_key = key
                                client = openai
                                use_new_sdk = False

                            msgs = []
                            system_content = "You are a helpful assistant for database queries. Only answer user questions using the database data. If the user asks about anything outside the database, politely refuse with: 'I can only answer questions about the database; please ask about data or request a SQL query.'"
                            if include_db:
                                snap = build_db_snapshot()
                                system_content += f"\n\nDB_SNAPSHOT:\n{snap}"
                            msgs.append({"role": "system", "content": system_content})
                            msgs.append({"role": "user", "content": user_input})

                            if use_new_sdk:
                                resp = client.chat.completions.create(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), messages=msgs)
                                try:
                                    assistant = resp.choices[0].message.content
                                except Exception:
                                    assistant = resp.choices[0].message["content"]
                            else:
                                resp = openai.ChatCompletion.create(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), messages=msgs)
                                assistant = resp.choices[0].message.content
                        except Exception as e:
                            st.error(f"OpenAI API error: {e}")
                            assistant = ""

        with st.chat_message("assistant"):
            st.write(assistant)

        # history storage removed; we still display the current exchange in chat

elif page == "History":
    st.header("Chat History")
    if not st.session_state.history:
        st.info("No history yet — interactions will appear here.")
    else:
        for idx, item in enumerate(reversed(st.session_state.history)):
            with st.chat_message("user"):
                st.write(item['user'])
            with st.chat_message("assistant"):
                st.write(item['assistant'])
            st.divider()

elif page == "Database Query":
    st.header("AI Database Query Assistant")
    st.write("Ask the AI to write and execute SQL queries on your database.")
    
    # Use a form so Enter submits naturally
    with st.form("db_query_form"):
        user_query = st.text_area("Describe what data you want to retrieve or what operation you want to perform:", height=100, key="db_query_input")
        submitted = st.form_submit_button("Execute Query")
    
    if submitted and user_query:
        # If the user explicitly types 'omit' (or similar), suppress showing prior messages
        st.session_state["last_submission_omit"] = "omit" in user_query.lower()
        # show loading indicator until output arrives
        with st.spinner("Loading — generating and executing SQL query..."):
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                st.error("OPENAI_API_KEY not set in environment")
            else:
                try:
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=key)
                        use_new_sdk = True
                    except Exception:
                        import openai
                        openai.api_key = key
                        client = openai
                        use_new_sdk = False

                    # Build messages with database schema information
                    msgs = []
                    if include_db:
                        snap = build_db_snapshot()
                        msgs.append({"role": "system", "content": f"DB_SCHEMA:\n{snap}\n\nYou are an expert SQL query assistant. Help the user write SQL queries for their SQLite database. When you generate a SQL query, execute it against the database and return the results along with the query used."})
                    else:
                        # Provide schema information without full data
                        conn = get_conn()
                        cur = conn.cursor()
                        schema_info = []
                        for tbl in ("AMAS", "IMAS"):
                            cur.execute(f"PRAGMA table_info(\"{tbl}\")")
                            columns = cur.fetchall()
                            schema_info.append(f"Table {tbl}: {[col['name'] for col in columns]}")
                        conn.close()
                        msgs.append({"role": "system", "content": f"DB_SCHEMA:\n{chr(10).join(schema_info)}\n\nYou are an expert SQL query assistant. Help the user write SQL queries for their SQLite database. When you generate a SQL query, execute it against the database and return the results along with the query used."})
                    
                    # Add user query
                    msgs.append({"role": "user", "content": user_query})

                    if use_new_sdk:
                        resp = client.chat.completions.create(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), messages=msgs)
                        try:
                            assistant_response = resp.choices[0].message.content
                        except Exception:
                            assistant_response = resp.choices[0].message["content"]
                    else:
                        resp = openai.ChatCompletion.create(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), messages=msgs)
                        assistant_response = resp.choices[0].message.content

                    # Extract SQL query from response (look for SQL code blocks)
                    import re
                    sql_match = re.search(r'```sql\n(.*?)\n```', assistant_response, re.DOTALL)
                    if sql_match:
                        sql_query = sql_match.group(1).strip()
                        st.subheader("Generated SQL Query:")
                        st.code(sql_query, language="sql")
                        
                        # Execute the query
                        try:
                            conn = get_conn()
                            cur = conn.cursor()
                            cur.execute(sql_query)
                            
                            # Check if it's a SELECT query
                            if sql_query.strip().upper().startswith("SELECT"):
                                results = cur.fetchall()
                                if results:
                                    # Convert to list of dicts for display
                                    columns = [description[0] for description in cur.description]
                                    result_data = [dict(zip(columns, row)) for row in results]
                                    st.subheader("Query Results:")
                                    st.dataframe(result_data)
                                else:
                                    st.info("Query executed successfully, but no results returned.")
                            else:
                                conn.commit()
                                st.success(f"Query executed successfully. Rows affected: {cur.rowcount}")
                            
                            conn.close()
                        except Exception as e:
                            st.error(f"Error executing query: {e}")
                    else:
                        st.warning("No SQL query found in the response.")
                        st.write("Assistant response:")
                        st.write(assistant_response)

                except Exception as e:
                    st.error(f"OpenAI API error: {e}")
