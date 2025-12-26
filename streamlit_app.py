import streamlit as st
import os
import json
import sqlite3
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Set page config immediately after importing Streamlit
st.set_page_config(page_title="Inventory Agent UI")

DB_PATH = Path("app_data.db")
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
        for tbl in ("customers", "inventory"):
            cur.execute(f"SELECT * FROM {tbl} LIMIT 50")
            rows = cur.fetchall()
            if rows:
                parts.append({"table": tbl, "rows": [dict(r) for r in rows]})
        conn.close()
        return json.dumps(parts, indent=2)
    except Exception as e:
        return f"Error building snapshot: {e}"


def load_memory():
    if not Path(PROJECT_MEMORY).exists():
        return []
    with open(PROJECT_MEMORY, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


st.title("Inventory Agent — Streamlit UI")

# Sidebar: DB actions (kept, but DB contents are not rendered in main UI)
with st.sidebar:
    st.header("Database")
    if st.button("Init DB"):
        import subprocess, sys
        subprocess.run([sys.executable, "db_Tool.py", "--init"])
        st.success("Initialized DB (if db_Tool.py present).")
    if st.button("Add sample data"):
        import subprocess, sys
        subprocess.run([sys.executable, "db_Tool.py", "--add-sample-data"])
        st.success("Added sample data.")
    if st.button("Refresh agent memory from DB"):
        snap = build_db_snapshot()
        mem = load_memory()
        new_mem = [{"role": "system", "content": "DB_SNAPSHOT:\n" + snap}] + mem
        with open(PROJECT_MEMORY, "w", encoding="utf-8") as f:
            json.dump(new_mem, f, indent=2)
        st.success("Saved DB snapshot to memory.json")

st.markdown("---")

# NOTE: DB tables are intentionally not rendered here per user request.
# The UI will show only the agent/query outputs below.

st.header("Agent Chat")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Default to not including DB snapshot in prompts to avoid exposing DB on the UI
include_db = st.checkbox("Include DB snapshot as memory in prompts", value=False)

user_input = st.text_input("You:")
if st.button("Send") and user_input:
    # Quick local DB handler: answer inventory/stock questions from the DB without calling OpenAI
    def answer_inventory_query(user_text: str) -> str | None:
        lower = user_text.lower()
        keywords = ("stock", "inventory", "how much", "how many", "quantity", "on hand", "in stock", "available")
        if not any(k in lower for k in keywords):
            return None
        # ensure DB exists
        if not DB_PATH.exists():
            return f"Database file '{DB_PATH}' not found — use the sidebar 'Init DB' button to create it."
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT SUM(quantity) FROM inventory")
            total = cur.fetchone()[0] or 0
            cur.execute("SELECT sku, name, quantity FROM inventory ORDER BY quantity DESC LIMIT 8")
            top = cur.fetchall()
            cur.execute("SELECT sku, name, quantity FROM inventory WHERE quantity <= 10 ORDER BY quantity ASC LIMIT 8")
            low = cur.fetchall()
            conn.close()
        except Exception as e:
            return f"Error reading inventory DB: {e}"
        parts = [f"Total stock (sum of quantities): {total}"]
        if top:
            parts.append("Top items by quantity:")
            for r in top:
                parts.append(f"- {r['name']} (sku={r['sku']}): {r['quantity']}")
        if low:
            parts.append("Low-stock items (<=10):")
            for r in low:
                parts.append(f"- {r['name']} (sku={r['sku']}): {r['quantity']}")
        parts.append("\n(If you want per-SKU counts, ask 'how many of SKU001' or use the DB query tool.)")
        return "\n".join(parts)

    db_answer = answer_inventory_query(user_input)
    if db_answer is not None:
        assistant = db_answer
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({"role": "assistant", "content": assistant})
        # skip OpenAI call — try to rerun the app if the Streamlit API is available
        rerun = getattr(st, "experimental_rerun", None)
        if callable(rerun):
            try:
                rerun()
            except Exception:
                # if rerun fails, continue; messages are already in session_state
                pass
    else:
        # load API key
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            st.error("OPENAI_API_KEY not set in environment")
        else:
            try:
                # lazy import to support different OpenAI SDKs
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=key)
                    use_new_sdk = True
                except Exception:
                    import openai
                    openai.api_key = key
                    client = openai
                    use_new_sdk = False

                # build messages
                msgs = []
                if include_db:
                    snap = build_db_snapshot()
                    msgs.append({"role": "system", "content": "DB_SNAPSHOT:\n" + snap})
                # append session messages
                msgs.extend(st.session_state.messages)
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

            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.messages.append({"role": "assistant", "content": assistant})

# Display only chat/query outputs
if st.session_state.messages:
    for m in st.session_state.messages:
        if m["role"] == "user":
            st.markdown(f"**You:** {m['content']}")
        else:
            st.markdown(f"**Assistant:** {m['content']}")
