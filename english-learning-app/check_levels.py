#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('learning.db')
cursor = conn.cursor()

print('=' * 60)
print('SEVIYE SISTEMI (Frekansa Gore Siralanmis)')
print('=' * 60)

cursor.execute('SELECT package_number, package_name, word_count, min_frequency, max_frequency FROM learning_packages ORDER BY package_number')
for row in cursor.fetchall():
    print(f"Level {row[0]}: {row[2]} kelime | Frekans: {row[4]}-{row[3]}")

print()
print('=' * 60)
print('ORNEK KELIMELER')
print('=' * 60)

print('\nLevel 1 (En Sik Kullanilan):')
cursor.execute('''SELECT w.word, w.frequency FROM package_words pw JOIN words w ON pw.word_id = w.id JOIN learning_packages lp ON pw.package_id = lp.id WHERE lp.package_number = 1 ORDER BY pw.word_rank LIMIT 10''')
for i, row in enumerate(cursor.fetchall(), 1):
    print(f"  {i}. {row[0]} ({row[1]})")

print('\nLevel 10 (Orta Seviye):')
cursor.execute('''SELECT w.word, w.frequency FROM package_words pw JOIN words w ON pw.word_id = w.id JOIN learning_packages lp ON pw.package_id = lp.id WHERE lp.package_number = 10 ORDER BY pw.word_rank LIMIT 10''')
for i, row in enumerate(cursor.fetchall(), 1):
    print(f"  {i}. {row[0]} ({row[1]})")

conn.close()
print('\n✅ Seviye sistemi basariyla olusturuldu!')

