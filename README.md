# Simple OpenAI CLI Agent

Usage

1. Create a `.env` file in the project root or set the `OPENAI_API_KEY` environment variable.

Example `.env` (copy from `.env.example`):

    OPENAI_API_KEY=sk-...

2. Install dependencies:

    pip install -r requirements.txt

3. Run the CLI agent:

    python main.py

Commands inside the agent:

- `/exit` to quit
- `/history` to show the loaded conversation
- `/save` to persist conversation to `memory.json`
- `/system TEXT` to set the system prompt
- `/model NAME` to change the model for the session
- DB commands: use `/db ...` for DB operations (init, addsample, list, query, ask, refresh)

Streamlit UI

1. Install dependencies (if not already):

    pip install -r requirements.txt

2. Run the Streamlit app:

    streamlit run streamlit_app.py

The Streamlit UI shows `customers` and `inventory`, lets you run SQL, and can refresh the agent's memory by saving a DB snapshot into `memory.json` which the agent will use as system memory.

Files

- `main.py` — CLI agent with `/db` commands and DB memory refresh
- `db_Tool.py` — standalone DB helper for initializing and populating the SQLite DB
- `streamlit_app.py` — Streamlit UI to view/search DB and chat with the agent
- `app_data.db` — created after running DB init
- `memory.json` — saved agent memory/snapshot
- `requirements.txt` — Python deps
d# Simple OpenAI CLI Agent

Usage

1. Create a `.env` file in the project root or set the `OPENAI_API_KEY` environment variable.

Example `.env` (copy from `.env.example`):

    OPENAI_API_KEY=sk-...

2. Install dependencies:

    pip install -r requirements.txt

3. Run the agent:

    python main.py

Commands inside the agent:

- `/exit` to quit
- `/history` to show the loaded conversation
- `/save` to persist conversation to `memory.json`
- `/system TEXT` to set the system prompt
- `/model NAME` to change the model for the session
