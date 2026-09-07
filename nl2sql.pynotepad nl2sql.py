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

    # Fix common date function nesting mistake (e.g., date("now") inside strftime)
    sql = sql.replace("'date(\"now\")'", "'now'").replace("'date(now)'", "'now'")

    return sql
