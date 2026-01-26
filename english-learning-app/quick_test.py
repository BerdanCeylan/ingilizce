#!/usr/bin/env python3
import sqlite3

print("=== DATABASE CHECK ===")
conn = sqlite3.connect('learning.db')
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [row[0] for row in cursor.fetchall()])

# Check words
cursor.execute("SELECT COUNT(*) FROM words")
print(f"Words: {cursor.fetchone()[0]}")

# Check packages
cursor.execute("SELECT COUNT(*) FROM learning_packages")
print(f"Packages: {cursor.fetchone()[0]}")

# Check package_words
cursor.execute("SELECT COUNT(*) FROM package_words")
print(f"Package words: {cursor.fetchone()[0]}")

# Sample packages
cursor.execute("SELECT package_number, package_name, word_count FROM learning_packages ORDER BY package_number LIMIT 5")
print("\nFirst 5 packages:")
for row in cursor.fetchall():
    print(f"  Level {row[0]}: {row[2]} words - {row[1][:40]}")

conn.close()
print("\n✅ Done!")

