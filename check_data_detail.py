#!/usr/bin/env python
"""
Check database content in detail
"""
import sqlite3

db_path = "django_backend/db.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 60)
print("DETAILED DATABASE CHECK")
print("=" * 60)

# Check skill categories
print("\n[SKILL CATEGORIES]")
cursor.execute("SELECT id, name, slug FROM skill_categories ORDER BY id")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} ({row[2]})")

# Check some skills
print("\n[SKILLS - Sample]")
cursor.execute("SELECT id, name, slug, category_id FROM skills LIMIT 10")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} ({row[2]}) [cat: {row[3]}]")

# Check evaluations
print("\n[EVALUATIONS]")
cursor.execute("SELECT id, overall_score, author_id, project_id, created_at FROM evaluations")
for row in cursor.fetchall():
    print(f"  ID: {row[0]} | Score: {row[1]} | Author: {row[2]} | Project: {row[3]} | Created: {row[4]}")

# Check findings
print("\n[FINDINGS]")
cursor.execute("SELECT id, title, severity, is_fixed, evaluation_id FROM findings")
for row in cursor.fetchall():
    print(f"  ID: {row[0]} | Title: {row[1][:40]}... | Severity: {row[2]} | Fixed: {row[3]} | Eval: {row[4]}")

# Check finding-skill links
print("\n[FINDING-SKILL LINKS]")
cursor.execute("SELECT finding_id, skill_id FROM finding_skills")
for row in cursor.fetchall():
    print(f"  Finding {row[0]} -> Skill {row[1]}")

# Check skill metrics
print("\n[SKILL METRICS]")
cursor.execute("SELECT COUNT(*) FROM skill_metrics")
count = cursor.fetchone()[0]
print(f"  Total: {count}")

if count > 0:
    cursor.execute("SELECT id, user_id, skill_id, score, issue_count FROM skill_metrics")
    for row in cursor.fetchall():
        print(f"  ID: {row[0]} | User: {row[1]} | Skill: {row[2]} | Score: {row[3]} | Issues: {row[4]}")

conn.close()

print("\n" + "=" * 60)
