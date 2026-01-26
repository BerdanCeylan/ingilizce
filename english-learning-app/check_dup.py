#!/usr/bin/env python3
"""Quick duplicate check"""
import sqlite3

conn = sqlite3.connect('learning.db')
cursor = conn.cursor()

total = cursor.execute('SELECT COUNT(*) FROM words').fetchone()[0]
unique = cursor.execute('SELECT COUNT(DISTINCT word) FROM words').fetchone()[0]

print(f"Toplam kayit: {total}")
print(f"Benzersiz: {unique}")
print(f"Fark: {total - unique}")

dup = cursor.execute('SELECT COUNT(*) FROM (SELECT word FROM words GROUP BY word HAVING COUNT(*) > 1)').fetchone()[0]
print(f"Tekrarlanan: {dup}")

if dup > 0:
    print("\nTekrarlanan kelimeler:")
    for row in cursor.execute('SELECT word, COUNT(*) FROM words GROUP BY word HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC LIMIT 10'):
        print(f"  {row[0]}: {row[1]}")

conn.close()
print("\nBitti!")

