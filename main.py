import os
import json
import sys
from typing import List, Dict
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI


# Import DB helpers (be tolerant to file name casing)
init_db = add_sample_data = fetch_all_table = run_query = None
DB_PATH = None
try:
    from db_Tool import init_db, add_sample_data, fetch_all_table, run_query, DB_PATH
except Exception:
    try:
        from db_Tool import init_db, add_sample_data, fetch_all_table, run_query, DB_PATH
    except Exception:
        init_db = add_sample_data = fetch_all_table = run_query = None
        DB_PATH = None

PROJECT_MEMORY = "memory.json"


def ensure_deps_available():
    if load_dotenv is None or OpenAI is None:
        print("Dependencies are missing. Install from requirements.txt:")
        print("    pip install -r requirements.txt")
        sys.exit(1)


def load_env():
    if load_dotenv:
        load_dotenv()


def get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set. Put it in your environment or .env file.")
    # Quick validation to provide actionable guidance for common mistakes
    k = key.strip()
    if not k.startswith("sk-") or len(k) < 30:
        raise RuntimeError(
            "OPENAI_API_KEY does not look like a valid key. Get your API key from https://platform.openai.com/account/api-keys and set it in .env or the environment."
        )
    return k


def get_project_id() -> str:
    project_id = os.environ.get("OPENAI_PROJECT_ID")
    if not project_id:
        return None
    return project_id.strip()


def load_memory() -> List[Dict]:
    if not os.path.exists(PROJECT_MEMORY):
        return []
    with open(PROJECT_MEMORY, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_memory(messages: List[Dict]):
    with open(PROJECT_MEMORY, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2)


def query_inventory(sku: str = None):
    if DB_PATH is None:
        return "Database helper not available. Ensure db_tool.py is present and importable."
    try:
        # check file exists
        p = str(DB_PATH)
        if not os.path.exists(p):
            return f"Database file '{p}' not found — run `/db init` to create it."
    except Exception:
        pass
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if sku:
            cur.execute("SELECT * FROM IMAS WHERE ICIMAS = ?", (sku,))
        else:
            cur.execute("SELECT * FROM IMAS")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return "No inventory found."
        result = "Inventory:\n"
        for row in rows:
            result += f"SKU: {row[1]}, Name: {row[2]}, Quantity: {row[7]}\n"  # ICIMAS, IALIAS, OSTQTY
        return result
    except Exception as e:
        return f"Error querying inventory: {e}"


def answer_inventory_query(user_text: str) -> str | None:
    """If the user_text appears to ask about inventory/stock, query the DB in real-time and return an answer string.
    Return None when the handler decides it should not handle the question.
    """
    lower = user_text.lower()
    keywords = ("stock", "inventory", "how much", "how many", "quantity", "on hand", "in stock", "available", "sku")
    if not any(k in lower for k in keywords):
        return None

    if DB_PATH is None:
        return "I'm sorry, but I can't access the inventory database right now. Please contact support if this continues."

    try:
        # Try to extract a SKU if mentioned (simple heuristic)
        import re
        m = re.search(r"sku\s*[:=]?\s*([\w-]+)", user_text, re.IGNORECASE)
        if m:
            sku = m.group(1)
            return query_inventory(sku=sku)

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()

        # Total quantity across inventory
        cur.execute("SELECT SUM(OSTQTY) FROM IMAS")
        total = cur.fetchone()[0] or 0

        # Top items by quantity
        cur.execute("SELECT ICIMAS, IALIAS, OSTQTY FROM IMAS ORDER BY OSTQTY DESC LIMIT 8")
        rows = cur.fetchall()

        # Low-stock items (quantity <= 10)
        cur.execute("SELECT ICIMAS, IALIAS, OSTQTY FROM IMAS WHERE OSTQTY <= 10 ORDER BY OSTQTY ASC LIMIT 8")
        low = cur.fetchall()
        conn.close()
    except Exception:
        return "I'm having trouble checking our inventory right now. Please try again later or contact support."

    # Natural language response
    response = f"We currently have a total of {total} items in stock across all products."

    if rows:
        response += " Our best-stocked items are:"
        for r in rows[:3]:  # Limit to top 3 for brevity
            response += f" {r[1]} with {r[2]} units,"
        response = response.rstrip(',') + "."

    if low:
        response += " We do have some items running low:"
        for r in low[:3]:  # Limit to top 3 low-stock
            response += f" {r[1]} with only {r[2]} units left,"
        response = response.rstrip(',') + ". We should restock these soon."

    response += " If you need details on a specific product or want to check availability, just let me know!"
    return response


def is_db_related(text: str) -> bool:
    """Return True when the user text is clearly about the database/tables/queries."""
    t = text.lower()
    keywords = ("stock", "inventory", "how much", "how many", "quantity", "on hand", "in stock", "available", "sku", "select", "from", "table", "amas", "imas", "sale", "prch", "prod", "order", "sitm", "tmas", "customers", "inventory")
    if any(k in t for k in keywords):
        return True
    # check for table names present in DB
    if DB_PATH is None:
        return False
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0].lower() for row in cur.fetchall()]
        conn.close()
        if any(tbl in t for tbl in tables):
            return True
    except Exception:
        pass
    return False

def chat_with_openai(messages: List[Dict], model: str, client: OpenAI):
    # Uses the new OpenAI Python client: client.chat.completions.create
    resp = client.chat.completions.create(model=model, messages=messages)
    # Take the first choice
    try:
        return resp.choices[0].message.content
    except Exception:
        return resp.choices[0].message["content"]


def print_help():
    print("Commands:")
    print("  /exit         - exit the agent")
    print("  /history      - show saved conversation history")
    print("  /save         - save conversation to memory.json")
    print("  /system TEXT  - set a system instruction")
    print("  /model NAME   - change model for this session")
    print("  /help         - show this help")


def get_db_schema() -> str:
    if DB_PATH is None or not os.path.exists(str(DB_PATH)):
        return ""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall() if row[0] not in ('sqlite_sequence',)]
        schema_info = "Available database tables:\n"
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = [f"{col[1]} ({col[2]})" for col in cur.fetchall()]
            schema_info += f"- {table}: {', '.join(cols)}\n"
        conn.close()
        return schema_info
    except Exception as e:
        return f"Error retrieving schema: {e}"

def main():
    ensure_deps_available()
    load_env()
    api_key = get_api_key()
    project_id = get_project_id()
    if project_id:
        client = OpenAI(api_key=api_key, project=project_id)
    else:
        client = OpenAI(api_key=api_key)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    memory = load_memory()
    if memory:
        print(f"Loaded {len(memory)} saved messages from {PROJECT_MEMORY}")

    db_schema = get_db_schema()
    base_system_prompt = os.environ.get("AGENT_SYSTEM_PROMPT", "You are a helpful assistant.")
    if db_schema:
        system_prompt = (
            f"{base_system_prompt}\n\nYou have access to a SQLite database with the following schema:\n{db_schema}\n\n"
            "Only answer user questions using the database schema and the data contained therein. If the user asks about anything outside the database (world knowledge, opinions, or unrelated topics), politely refuse with the phrase:\n"
            '"I can only answer questions about the database; please ask about data or request a SQL query."\n\n'
            "If you need to run a query, either execute it against the database or describe the exact SQL you would use, and only return results actually present in the database. Do not hallucinate or invent facts."
        )
    else:
        system_prompt = (
            f"{base_system_prompt}\n\nOnly answer user questions about the project's SQLite database. If the user asks about anything outside the database, politely refuse with: \"I can only answer questions about the database; please ask about data or request a SQL query.\""
        )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # append saved memory as system context (optional)
    if memory:
        messages.extend(memory)

    print("AI agent ready. Type a message, or /help for commands.")

    while True:
        try:
            user_in = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not user_in:
            continue

        if user_in.startswith("/"):
            parts = user_in.split(" ", 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd == "/exit":
                break
            if cmd == "/history":
                for i, m in enumerate(messages):
                    role = m.get("role")
                    content = m.get("content")
                    print(f"{i+1}. {role}: {content}")
                continue
            if cmd == "/save":
                # save only user+assistant pairs (skip system)
                to_save = [m for m in messages if m.get("role") != "system"]
                save_memory(to_save)
                print(f"Saved {len(to_save)} messages to {PROJECT_MEMORY}")
                continue
            if cmd == "/system":
                system_prompt = arg or ""
                # replace or add system message
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] = system_prompt
                else:
                    messages.insert(0, {"role": "system", "content": system_prompt})
                print("System prompt updated.")
                continue
            if cmd == "/model":
                if arg:
                    model = arg
                    print(f"Model set to {model}")
                else:
                    print(f"Current model: {model}")
                continue
            if cmd == "/help":
                print_help()
                continue

            print("Unknown command. Use /help for a list of commands.")
            continue

        # regular user message
        # Enforce DB-only responses: refuse unrelated questions
        if not is_db_related(user_in):
            refusal = "I can only answer questions about the database; please ask about data or request a SQL query."
            print("Assistant:", refusal)
            messages.append({"role": "user", "content": user_in})
            messages.append({"role": "assistant", "content": refusal})
            continue

        # First, check if this looks like an inventory/stock question and answer from DB directly
        db_answer = answer_inventory_query(user_in)
        if db_answer is not None:
            print("Assistant:", db_answer)
            messages.append({"role": "user", "content": user_in})
            messages.append({"role": "assistant", "content": db_answer})
            continue

        messages.append({"role": "user", "content": user_in})
        try:
            assistant_text = chat_with_openai(messages, model, client)
        except Exception as e:
            print("Error calling OpenAI API:", e)
            continue

        print("Assistant:", assistant_text)
        messages.append({"role": "assistant", "content": assistant_text})


if __name__ == "__main__":
    main()
