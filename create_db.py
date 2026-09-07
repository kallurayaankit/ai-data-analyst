import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("ecommerce.db")
c = conn.cursor()

# Create tables
c.execute("""CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT,
    country TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TEXT,
    amount REAL
)""")

# Insert sample data
countries = ["USA", "UK", "Germany", "India", "Japan"]
for i in range(1, 51):
    country = random.choice(countries)
    c.execute("INSERT INTO customers (customer_id, name, country) VALUES (?, ?, ?)",
              (i, f"Customer {i}", country))

# Generate 500 random orders in the last 12 months
start_date = datetime.now() - timedelta(days=365)
for order_id in range(1, 501):
    customer_id = random.randint(1, 50)
    order_date = start_date + timedelta(days=random.randint(0, 365))
    amount = round(random.uniform(10, 500), 2)
    c.execute("INSERT INTO orders (order_id, customer_id, order_date, amount) VALUES (?, ?, ?, ?)",
              (order_id, customer_id, order_date.isoformat(), amount))

conn.commit()
conn.close()
print("Database created with sample data.")