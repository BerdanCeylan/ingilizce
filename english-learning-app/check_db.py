import sqlite3

conn = sqlite3.connect('learning.db')
cursor = conn.cursor()

# Check counts
cursor.execute('SELECT COUNT(*) FROM words')
print(f'Words tablosu: {cursor.fetchone()[0]} kelime')

cursor.execute('SELECT COUNT(*) FROM word_frequency')
print(f'Word_frequency tablosu: {cursor.fetchone()[0]} kelime')

# Show sample words
cursor.execute('SELECT word, frequency FROM words ORDER BY frequency DESC LIMIT 10')
print('\nEn sık kullanılan 10 kelime:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()

