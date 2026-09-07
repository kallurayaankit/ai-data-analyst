import sqlite3
import time
import re
import json
import hashlib
from datetime import datetime, timedelta
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
DB_PATH = "ecommerce.db"

# Caching
cache = {}

# Token/cost tracking (simplified)
token_count = 0
total_cost = 0.0

def log_tokens(prompt):
    global token_count, total_cost
    tokens = len(prompt.split())
    token_count += tokens
    total_cost += tokens * 0.0001

def get_schema():
    """Extract table and column names from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in c.fetchall()]
    schema = {}
    for table in tables:
        c.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in c.fetchall()]
        schema[table] = columns
    conn.close()
    return schema

def generate_sql(question, schema, previous_errors=None):
    """Use Ollama (Mistral) to generate a SQL query."""
    schema_str = json.dumps(schema, indent=2)
    prompt = f"""You are an expert SQL analyst. Given the following database schema:
{schema_str}

User question: "{question}"

Generate only the SQL query that answers this question. Do not include any explanations, markdown, or extra text. Just the SQL statement.

Important:
- Use **SQLite syntax** only.
- For current date, use `date('now')`.
- For month filtering, use `strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now')`.
- Avoid MySQL functions like `CURDATE()`, `NOW()`, `YEAR()`, `MONTH()` if they don't exist in SQLite.
- Use only SELECT statements (read-only).
- Limit results to at most 100 rows.

"""
    if previous_errors:
        prompt += "\nPrevious SQL generated errors. Please fix them:\n" + "\n".join(previous_errors)

    log_tokens(prompt)

    resp = requests.post(
        OLLAMA_URL,
        json={"model": "mistral", "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    if resp.status_code != 200:
        raise Exception("Ollama error")
    sql = resp.json()["message"]["content"].strip()

    # Remove any accidental markdown code fences
    sql = sql.replace("```sql", "").replace("```", "").strip()

    # Replace common MySQL functions with SQLite equivalents
    sql = re.sub(r'\bCURDATE\(\)', "date('now')", sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bNOW\(\)', "datetime('now')", sql, flags=re.IGNORECASE)

    # Robustly correct nested date("now") / date('now') inside any function
    sql = sql.replace('date("now")', 'now')
    sql = sql.replace("date('now')", "'now'")

    return sql

def validate_sql(sql, schema):
    """Only check read-only SELECT and dangerous keywords. No table/column checks."""
    errors = []
    # Only allow SELECT
    if not sql.lower().startswith("select"):
        errors.append("Query must start with SELECT.")
    # Block dangerous keywords
    dangerous = ["insert", "update", "delete", "drop", "alter", "create", "exec", "attach"]
    for word in dangerous:
        if word in sql.lower():
            errors.append(f"Query contains forbidden keyword: {word}")
    return errors

def execute_sql(sql, timeout_seconds=5):
    """Execute SQL with timeout and read-only mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    start = time.time()
    try:
        c.execute(sql)
        rows = c.fetchall()
        columns = [description[0] for description in c.description]
        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Query took {elapsed:.2f} seconds, exceeding timeout.")
        return columns, rows
    except Exception as e:
        raise e
    finally:
        conn.close()

def format_results(columns, rows):
    """Convert raw results to a dict for easy charting."""
    return {
        "columns": columns,
        "rows": [list(row) for row in rows]
    }

def generate_explanation(question, sql, results):
    """Use Ollama to explain the results in natural language."""
    prompt = f"""Question: "{question}"
SQL: {sql}
Results (first 5 rows): {results}

Explain the insights in 2-3 sentences."""
    log_tokens(prompt)
    resp = requests.post(
        OLLAMA_URL,
        json={"model": "mistral", "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    if resp.status_code == 200:
        return resp.json()["message"]["content"].strip()
    return "Explanation unavailable."

def nl_to_sql(question, max_retries=3):
    """Full pipeline: generate, validate, execute, explain, cache."""
    cache_key = hashlib.md5(question.encode()).hexdigest()
    if cache_key in cache:
        print("Cache hit!")
        return cache[cache_key]

    schema = get_schema()
    previous_errors = []
    for attempt in range(max_retries):
        sql = generate_sql(question, schema, previous_errors)
        errors = validate_sql(sql, schema)
        if errors:
            previous_errors = errors
            print(f"Attempt {attempt+1} validation errors: {errors}")
            continue
        try:
            columns, rows = execute_sql(sql)
            break
        except Exception as e:
            previous_errors = [str(e)]
            print(f"Attempt {attempt+1} execution error: {e}")
    else:
        raise Exception("Could not generate valid SQL after multiple attempts.")

    results = format_results(columns, rows)
    explanation = generate_explanation(question, sql, results["rows"][:5])

    response = {
        "question": question,
        "sql": sql,
        "results": results,
        "explanation": explanation,
        "attempts": attempt+1,
        "timestamp": datetime.now().isoformat()
    }
    # Cache for 10 minutes (simplified)
    cache[cache_key] = response
    if len(cache) > 100:
        oldest = min(cache, key=lambda k: cache[k]["timestamp"])
        del cache[oldest]
    return response

def get_usage_stats():
    return {"total_tokens": token_count, "total_cost": round(total_cost, 4)}