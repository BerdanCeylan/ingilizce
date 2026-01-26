#!/usr/bin/env python3
"""Import missing words from subtitle stats to learning database"""
import sqlite3
import shutil

LEARNING_DB = '/home/duffyduck/Downloads/ingilizce/english-learning-app/learning.db'
SUBTITLE_STATS = '/home/duffyduck/Downloads/ingilizce/english-learning-app/Subtitles/combined_stats.db'

def import_missing_words():
    print("=== EKSİK KELİMELERİ AKTARMA ===\n")
    
    # Backup learning.db
    backup_path = LEARNING_DB.replace('.db', '_backup2.db')
    shutil.copy(LEARNING_DB, backup_path)
    print(f"✓ Yedek alındı: {backup_path}")
    
    # Connect to both databases
    conn_learn = sqlite3.connect(LEARNING_DB)
    cursor_learn = conn_learn.cursor()
    
    conn_sub = sqlite3.connect(SUBTITLE_STATS)
    cursor_sub = conn_sub.cursor()
    
    # Get existing words in learning.db
    cursor_learn.execute("SELECT word FROM words")
    existing_words = set(row[0].lower() for row in cursor_learn.fetchall())
    print(f"Mevcut kelime sayısı: {len(existing_words)}")
    
    # Get all words from subtitle stats
    cursor_sub.execute("SELECT word, frequency FROM word_frequencies")
    subtitle_words = cursor_sub.fetchall()
    print(f"Altyazı toplam kelime: {len(subtitle_words)}")
    
    # Find missing words
    missing_words = [(w, f) for w, f in subtitle_words if w.lower() not in existing_words]
    print(f"Eksik kelime sayısı: {len(missing_words)}")
    
    if missing_words:
        # Insert missing words in batches
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(missing_words), batch_size):
            batch = missing_words[i:i + batch_size]
            cursor_learn.executemany(
                "INSERT INTO words (word, frequency) VALUES (?, ?)",
                batch
            )
            total_inserted += len(batch)
            conn_learn.commit()
            print(f"  ✓ {total_inserted}/{len(missing_words)} kelime eklendi")
        
        print(f"\n✅ {total_inserted} eksik kelime eklendi!")
    else:
        print("\nℹ️ Eksik kelime yok!")
    
    conn_learn.close()
    conn_sub.close()
    
    # Show final stats
    print("\n=== SON DURUM ===")
    conn_final = sqlite3.connect(LEARNING_DB)
    cursor_final = conn_final.cursor()
    cursor_final.execute("SELECT COUNT(*) FROM words")
    total = cursor_final.fetchone()[0]
    print(f"Learning DB toplam kelime: {total}")
    conn_final.close()

if __name__ == '__main__':
    import_missing_words()

