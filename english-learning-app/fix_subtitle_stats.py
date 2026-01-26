#!/usr/bin/env python3
"""Fix subtitle database statistics"""
import sqlite3
import os
import shutil
from collections import Counter

BASE_DIR = '/home/duffyduck/Downloads/ingilizce/english-learning-app/Subtitles'

def fix_subtitle_stats():
    print("=== ALTYAZI VERİTABANI DÜZELTME ===\n")
    
    # Collect all word frequencies from all subtitle DBs
    all_words = Counter()
    db_files = []
    
    for root, dirs, files in os.walk(BASE_DIR):
        for f in files:
            if f.endswith('.db') and f != 'combined_stats.db':
                db_path = os.path.join(root, f)
                db_files.append(db_path)
                
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT word, frequency FROM word_frequencies")
                    for row in cursor.fetchall():
                        all_words[row[0]] += row[1]
                    conn.close()
                    print(f"✓ Okundu: {os.path.relpath(db_path, BASE_DIR)}")
                except Exception as e:
                    print(f"✗ HATA: {db_path} - {e}")
    
    print(f"\nToplam bulunan kelime: {len(all_words)}")
    print(f"Toplam frekans: {sum(all_words.values())}")
    
    # Create or update combined_stats.db
    combined_path = os.path.join(BASE_DIR, 'combined_stats.db')
    backup_path = combined_path.replace('.db', '_backup.db')
    
    # Backup existing
    if os.path.exists(combined_path):
        shutil.copy(combined_path, backup_path)
        print(f"\n✓ Yedek alındı: {backup_path}")
    
    # Create new combined database
    conn = sqlite3.connect(combined_path)
    cursor = conn.cursor()
    
    # Drop and recreate
    cursor.execute("DROP TABLE IF EXISTS word_frequencies")
    cursor.execute("""
        CREATE TABLE word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER NOT NULL
        )
    """)
    
    # Insert sorted by frequency
    sorted_data = sorted(all_words.items(), key=lambda x: x[1], reverse=True)
    cursor.executemany("INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)", sorted_data)
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*), SUM(frequency) FROM word_frequencies")
    total, freq = cursor.fetchone()
    
    conn.close()
    
    print(f"\n✅ combined_stats.db güncellendi!")
    print(f"   Benzersiz kelime: {total}")
    print(f"   Toplam frekans: {freq}")
    
    # Show top 10 words
    print(f"\nEn sık kullanılan 10 kelime:")
    for word, count in sorted_data[:10]:
        print(f"   {word}: {count}")
    
    return True

if __name__ == '__main__':
    fix_subtitle_stats()

