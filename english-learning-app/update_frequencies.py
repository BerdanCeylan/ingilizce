#!/usr/bin/env python3
"""Update word frequencies from subtitle stats"""
import sqlite3
import shutil

LEARNING_DB = '/home/duffyduck/Downloads/ingilizce/english-learning-app/learning.db'
SUBTITLE_STATS = '/home/duffyduck/Downloads/ingilizce/english-learning-app/Subtitles/combined_stats.db'

def update_frequencies():
    print("=== KELİME FREKANSI GÜNCELLEME ===\n")
    
    # Backup
    backup_path = LEARNING_DB.replace('.db', '_backup4.db')
    shutil.copy(LEARNING_DB, backup_path)
    print(f"✓ Yedek alındı: {backup_path}")
    
    conn = sqlite3.connect(LEARNING_DB)
    cursor = conn.cursor()
    
    conn_sub = sqlite3.connect(SUBTITLE_STATS)
    cursor_sub = conn_sub.cursor()
    
    # Mevcut durum
    cursor.execute("SELECT COUNT(*), SUM(frequency) FROM words")
    old_total, old_freq = cursor.fetchone()
    print(f"Önceki durum: {old_total} kelime, toplam frekans: {old_freq}")
    
    # Altyazı frekanslarını getir
    cursor_sub.execute("SELECT word, frequency FROM word_frequencies")
    subtitle_freqs = {row[0]: row[1] for row in cursor_sub.fetchall()}
    print(f"Altyazı veritabanı: {len(subtitle_freqs)} kelime")
    
    # Words tablosundaki kelimeleri güncelle
    updated = 0
    new_words = 0
    
    # Mevcut kelimelerin frekanslarını güncelle
    cursor.execute("SELECT id, word, frequency FROM words")
    for row_id, word, old_freq_val in cursor.fetchall():
        word_lower = word.lower()
        if word_lower in subtitle_freqs:
            new_freq = subtitle_freqs[word_lower]
            if new_freq != old_freq_val:
                cursor.execute("UPDATE words SET frequency = ? WHERE id = ?", (new_freq, row_id))
                updated += 1
    
    conn.commit()
    
    # Altyazında olup learning db'de olmayan kelimeleri bul
    cursor.execute("SELECT word FROM words")
    existing_words = set(row[0].lower() for row in cursor.fetchall())
    
    missing_words = [(w, f) for w, f in subtitle_freqs.items() if w not in existing_words]
    print(f"Eksik kelime: {len(missing_words)}")
    
    # Eksik kelimeleri ekle
    if missing_words:
        for word, freq in missing_words:
            cursor.execute("INSERT INTO words (word, frequency) VALUES (?, ?)", (word, freq))
            new_words += 1
        conn.commit()
    
    conn_sub.close()
    
    # Yeni durum
    cursor.execute("SELECT COUNT(*), SUM(frequency) FROM words")
    new_total, new_freq = cursor.fetchone()
    
    conn.close()
    
    print(f"\n✅ GÜNCELLENDİ!")
    print(f"  Güncellenen frekans: {updated}")
    print(f"  Yeni eklenen kelime: {new_words}")
    print(f"  Yeni toplam: {new_total} kelime")
    print(f"  Yeni toplam frekans: {new_freq}")
    
    # En sık kullanılan 10 kelimeyi göster
    print(f"\nEn sık kullanılan 10 kelime:")
    conn2 = sqlite3.connect(LEARNING_DB)
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT word, frequency FROM words ORDER BY frequency DESC LIMIT 10")
    for row in cursor2.fetchall():
        print(f"   {row[0]}: {row[1]}")
    conn2.close()

if __name__ == '__main__':
    update_frequencies()
