#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('learning.db')
cursor = conn.cursor()

# Check current counts
cursor.execute('SELECT COUNT(*) FROM words')
print(f'Words tablosu: {cursor.fetchone()[0]} kelime')

cursor.execute('SELECT COUNT(*) FROM word_frequency')
print(f'Word_frequency tablosu: {cursor.fetchone()[0]} kelime')

# Get all words from word_frequency table
cursor.execute('SELECT word, frequency FROM word_frequency')
freq_words = cursor.fetchall()

# Add words from word_frequency to words table
added = 0
for word, freq in freq_words:
    # Check if word already exists
    cursor.execute('SELECT id FROM words WHERE word = ?', (word,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO words (word, frequency) VALUES (?, ?)', (word, freq))
        added += 1

conn.commit()

# Verify
cursor.execute('SELECT COUNT(*) FROM words')
print(f'Yeni words tablosu: {cursor.fetchone()[0]} kelime')
print(f'Eklenen kelime sayısı: {added}')

conn.close()
print('✅ Kelimeler başarıyla aktarıldı!')

