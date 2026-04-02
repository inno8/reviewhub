#!/usr/bin/env python
"""
Check database status and content
"""
import sqlite3

db_path = "django_backend/db.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 60)
print("DATABASE STATUS CHECK")
print("=" * 60)

# Check skill categories
cursor.execute("SELECT COUNT(*) FROM skills_skillcategory")
cat_count = cursor.fetchone()[0]
print(f"\nSkill Categories: {cat_count}")

if cat_count > 0:
    cursor.execute("SELECT id, name, slug FROM skills_skillcategory ORDER BY 'order'")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} ({row[2]})")

# Check skills
cursor.execute("SELECT COUNT(*) FROM skills_skill")
skill_count = cursor.fetchone()[0]
print(f"\nSkills: {skill_count}")

if skill_count > 0:
    cursor.execute("SELECT id, name, slug, category_id FROM skills_skill LIMIT 5")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} ({row[2]}) [category: {row[3]}]")
    if skill_count > 5:
        print(f"  ... and {skill_count - 5} more")

# Check users
cursor.execute("SELECT COUNT(*) FROM users_user")
user_count = cursor.fetchone()[0]
print(f"\nUsers: {user_count}")

if user_count > 0:
    cursor.execute("SELECT id, email, username FROM users_user")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} ({row[2]})")

# Check evaluations
cursor.execute("SELECT COUNT(*) FROM evaluations_evaluation")
eval_count = cursor.fetchone()[0]
print(f"\nEvaluations: {eval_count}")

# Check findings
cursor.execute("SELECT COUNT(*) FROM evaluations_finding")
finding_count = cursor.fetchone()[0]
print(f"\nFindings: {finding_count}")

# Check skill metrics
cursor.execute("SELECT COUNT(*) FROM skills_skillmetric")
metric_count = cursor.fetchone()[0]
print(f"\nSkill Metrics: {metric_count}")

conn.close()

print("\n" + "=" * 60)
print("CHECK COMPLETE")
print("=" * 60)
