# Inventory Agent Support (Local)

A local AI-powered inventory management assistant. This project allows you to interact with an SQLite database using natural language through a Streamlit web interface or a command-line interface (CLI). It uses OpenAI's models to generate SQL queries and answer questions based on your data.

## Features

- **AI Chat Assistant**: Ask questions about your inventory and customers in plain English.
- **Database Query Tool**: The AI translates your requests into SQL, executes them, and shows the results.
- **Database Management**: Initialize and populate the database with sample data directly from the UI or CLI.
- **Memory & Context**: The agent maintains conversation history and uses database snapshots to provide accurate context.
- **Export Options**: Download database snapshots (JSON) or table data (CSV).

## Prerequisites

- Python 3.8 or higher
- An OpenAI API Key

## Installation

1. **Clone or download the repository.**

2. **Install dependencies:**

 ```bash
    pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root to store your API key. You can copy `.env.example` if it exists.

**`.env` file content:**

```env
OPENAI_API_KEY=sk-your_api_key_here
OPENAI_MODEL=gpt-4o-mini  # Optional: defaults to gpt-4o-mini
```

## Usage

### 1. Streamlit Web UI (Recommended)

The Web UI provides the most complete experience, including chat, history, and database controls.

Run the app:

```bash
    streamlit run streamlit_app.py
```

**Functionality:**

- **Sidebar**: Navigate between Chat, History, and Database Query pages.
- **Database Controls**: Initialize the DB, add sample data, and refresh the agent's memory.
- **Chat**: Interact with the agent. It uses a local fallback for simple queries and OpenAI for complex ones.
- **Database Query**: Describe what you want (e.g., "Show me all customers in New York"), and the agent will run the SQL.

### 2. CLI Agent

Run the interactive command-line agent:

```bash
python main.py
```

**Commands inside the agent:**

- `/exit`: Quit the application.
- `/history`: Show the loaded conversation history.
- `/save`: Persist conversation to `memory.json`.
- `/system TEXT`: Set a custom system prompt.
- `/model NAME`: Change the OpenAI model for the session.
- `/db ...`: Run database commands.

### 3. Database Tool (Standalone)

You can manage the SQLite database directly using the helper script.

```bash
# Initialize the database (create tables)
python db_Tool.py --init

# Add sample data (only if empty)
python db_Tool.py --add-sample-data

# Upsert sample data (update existing, insert new)
python db_Tool.py --add-sample-data-upsert

# Run a custom SQL query
python db_Tool.py --query "SELECT * FROM inventory"

# Fetch all rows from a table
python db_Tool.py --fetch-all customers
```

## Project Structure

- **`streamlit_app.py`**: The main web application interface.
- **`main.py`**: The CLI entry point for the agent.
- **`db_Tool.py`**: Utility script for SQLite database operations.
- **`app_data.db`**: The SQLite database file (generated after initialization).
- **`memory.json`**: Stores the agent's conversation history and database context.
- **`requirements.txt`**: List of Python dependencies.
