#!/usr/bin/env python
"""
List all tables in the database
"""
import sqlite3

db_path = "django_backend/db.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 60)
print("DATABASE TABLES")
print("=" * 60)

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

for table in tables:
    print(f"- {table[0]}")
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cursor.fetchone()[0]
    print(f"  (rows: {count})")

conn.close()

print("\n" + "=" * 60)
print(f"Total tables: {len(tables)}")
print("=" * 60)
