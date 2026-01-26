#!/usr/bin/env python3
"""
Tüm alt veritabanlarını tarar, kelimeleri birleştirir ve 
ana veritabanını (learning.db) sıfırdan oluşturur.
"""
import os
import sqlite3
import shutil
from collections import Counter
import sys

# Proje dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEARNING_DB_NAME = 'learning.db'
LEARNING_DB_PATH = os.path.join(BASE_DIR, LEARNING_DB_NAME)

def find_all_dbs():
    """Proje dizinindeki tüm .db dosyalarını bulur (learning.db hariç)."""
    db_files = []
    print(f"📂 Dizin taranıyor: {BASE_DIR}")
    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith('.db'):
                # Ana veritabanını ve yedekleri atla
                if file == LEARNING_DB_NAME or 'backup' in file.lower():
                    continue
                
                full_path = os.path.join(root, file)
                db_files.append(full_path)
    return db_files

def aggregate_words(db_files):
    """Bulunan veritabanlarından kelime frekanslarını toplar."""
    global_counter = Counter()
    processed_count = 0
    
    print(f"\n🔍 {len(db_files)} veritabanı analiz ediliyor...")
    
    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Tablo adını kontrol et (word_frequencies veya word_frequency)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='word_frequencies'")
            if cursor.fetchone():
                table_name = 'word_frequencies'
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='word_frequency'")
                if cursor.fetchone():
                    table_name = 'word_frequency'
                else:
                    conn.close()
                    continue

            cursor.execute(f"SELECT word, frequency FROM {table_name}")
            rows = cursor.fetchall()
            
            for word, freq in rows:
                if word and isinstance(freq, int):
                    global_counter[word.lower()] += freq
            
            processed_count += 1
            print(f"  ✓ Eklendi: {os.path.basename(db_path)} ({len(rows)} kelime)")
            conn.close()
            
        except Exception as e:
            print(f"  ❌ Hata ({os.path.basename(db_path)}): {e}")
            
    print(f"\n📊 Toplam {processed_count} veritabanından veri birleştirildi.")
    return global_counter

def rebuild_learning_db(word_counts):
    """Ana veritabanını sıfırlar ve yeni verilerle doldurur."""
    print(f"\n🛠️  {LEARNING_DB_NAME} yeniden oluşturuluyor...")
    
    # Yedek al
    if os.path.exists(LEARNING_DB_PATH):
        backup_path = LEARNING_DB_PATH.replace('.db', '_rebuild_backup.db')
        shutil.copy(LEARNING_DB_PATH, backup_path)
        print(f"  📦 Yedek alındı: {os.path.basename(backup_path)}")
    
    conn = sqlite3.connect(LEARNING_DB_PATH)
    cursor = conn.cursor()
    
    # 1. Eski tabloları temizle (varsa - boş DB durumunda hata olmasın)
    print("  🧹 Eski tablolar temizleniyor...")
    tables_to_drop = [
        'words', 'learning_packages', 'package_words', 'users', 'user_words',
        'videos', 'video_words', 'watch_rooms', 'room_members', 'chat_messages',
        'flashcard_sessions', 'flashcard_progress', 'flashcard_problem_words'
    ]
    for table in tables_to_drop:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    
    # Indexleri temizle
    cursor.execute("DROP INDEX IF EXISTS idx_words_freq")
    cursor.execute("DROP INDEX IF EXISTS idx_words_word")
    cursor.execute("DROP INDEX IF EXISTS idx_pkg_words_pkg")
    
    # 2. Yeni tabloları oluştur
    print("  🏗️  Tablo yapısı oluşturuluyor...")
    
    # Words tablosu
    cursor.execute("""
        CREATE TABLE words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            frequency INTEGER DEFAULT 1,
            definition TEXT,
            pronunciation TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX idx_words_freq ON words(frequency DESC)")
    cursor.execute("CREATE INDEX idx_words_word ON words(word)")
    
    # Packages tablosu
    cursor.execute("""
        CREATE TABLE learning_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_number INTEGER,
            package_name TEXT,
            word_count INTEGER,
            min_frequency INTEGER,
            max_frequency INTEGER
        )
    """)
    
    # Package Words tablosu
    cursor.execute("""
        CREATE TABLE package_words (
            package_id INTEGER,
            word_id INTEGER,
            word_rank INTEGER,
            FOREIGN KEY(package_id) REFERENCES learning_packages(id),
            FOREIGN KEY(word_id) REFERENCES words(id)
        )
    """)
    cursor.execute("CREATE INDEX idx_pkg_words_pkg ON package_words(package_id)")
    
    # 3. Kelimeleri ekle
    print(f"  📥 {len(word_counts)} benzersiz kelime veritabanına yazılıyor...")
    
    # Frekansa göre sırala (En yüksekten en düşüğe)
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Batch insert
    batch_data = [(word, freq) for word, freq in sorted_words]
    cursor.executemany("INSERT INTO words (word, frequency) VALUES (?, ?)", batch_data)
    conn.commit()
    
    # 4. Seviyeleri oluştur (Her seviye 500 kelime)
    print("  📚 Seviye sistemi oluşturuluyor (Paket boyutu: 500)...")
    
    # Eklenen kelimeleri ID'leri ile geri al
    cursor.execute("SELECT id, word, frequency FROM words ORDER BY frequency DESC")
    all_words = cursor.fetchall()
    
    PACKAGE_SIZE = 500
    total_packages = 0
    
    for i in range(0, len(all_words), PACKAGE_SIZE):
        package_words_batch = all_words[i:i + PACKAGE_SIZE]
        if not package_words_batch:
            continue
            
        package_num = (i // PACKAGE_SIZE) + 1
        
        first_word = package_words_batch[0]
        last_word = package_words_batch[-1]
        max_freq = first_word[2]
        min_freq = last_word[2]
        
        pkg_name = f"Level {package_num}: {first_word[1]} - {last_word[1]}"
        
        # Paketi oluştur
        cursor.execute("""
            INSERT INTO learning_packages 
            (package_number, package_name, word_count, min_frequency, max_frequency)
            VALUES (?, ?, ?, ?, ?)
        """, (package_num, pkg_name, len(package_words_batch), min_freq, max_freq))
        
        package_id = cursor.lastrowid
        
        # Pakete kelimeleri bağla
        pkg_word_inserts = []
        for rank, (wid, wtext, wfreq) in enumerate(package_words_batch, 1):
            pkg_word_inserts.append((package_id, wid, rank))
            
        cursor.executemany("""
            INSERT INTO package_words (package_id, word_id, word_rank)
            VALUES (?, ?, ?)
        """, pkg_word_inserts)
        
        total_packages += 1
        
    conn.commit()
    conn.close()
    
    print(f"\n✅ İŞLEM BAŞARIYLA TAMAMLANDI!")
    print(f"  - Toplam Kelime: {len(sorted_words):,}")
    print(f"  - Toplam Seviye: {total_packages}")
    print(f"  - Veritabanı: {LEARNING_DB_PATH}")

if __name__ == "__main__":
    print("="*60)
    print("KELİME HARİTASI VE SEVİYE SİSTEMİ YENİLEME")
    print("="*60)
    
    dbs = find_all_dbs()
    if not dbs:
        print("❌ Hata: Hiçbir alt veritabanı (.db) bulunamadı!")
        sys.exit(1)
        
    counts = aggregate_words(dbs)
    if not counts:
        print("❌ Hata: Veritabanlarından kelime okunamadı!")
        sys.exit(1)
        
    rebuild_learning_db(counts)