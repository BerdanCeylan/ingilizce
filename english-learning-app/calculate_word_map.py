#!/usr/bin/env python3
"""Calculate word map from database and regenerate levels based on actual frequencies"""
import sqlite3
import shutil

DB_PATH = 'learning.db'

def calculate_word_map_and_regenerate_levels():
    print("=" * 60)
    print("KELIME HARITASI HESAPLAMA VE SEVIYELENDIRME")
    print("=" * 60)
    
    # Backup first
    backup_path = DB_PATH.replace('.db', '_backup5.db')
    shutil.copy(DB_PATH, backup_path)
    print(f"\n[OK] Yedek alindi: {backup_path}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Kelime haritasini hesapla
    print("\n=== ADIM 1: KELIME HARITASI HESAPLAMA ===")
    
    cursor.execute("SELECT id, word, frequency FROM words ORDER BY frequency DESC")
    words = cursor.fetchall()
    
    total_words = len(words)
    total_freq = sum(w['frequency'] for w in words)
    
    print(f"\n[STAT] KELIME HARITASI:")
    print(f"   Toplam benzersiz kelime: {total_words}")
    print(f"   Toplam frekans: {total_freq}")
    print(f"   Ortalama frekans: {total_freq/total_words:.2f}")
    
    # Frekans dagilimi
    freq_ranges = [
        (10000, "Cok Yuksek"),
        (1000, "Yuksek"),
        (100, "Orta-Yuksek"),
        (50, "Orta"),
        (10, "Orta-Dusuk"),
        (5, "Dusuk"),
        (0, "Cok Dusuk")
    ]
    
    print(f"\n[GRAPH] FREKANS DAGILIMI:")
    for min_freq, label in freq_ranges:
        count = sum(1 for w in words if w['frequency'] >= min_freq)
        print(f"   {label} (>={min_freq}): {count} kelime")
    
    # 2. Learning packages olustur
    print("\n=== ADIM 2: SEVIYELENDIRME ===")
    
    # Mevcut paketleri temizle
    cursor.execute("DELETE FROM package_words")
    cursor.execute("DELETE FROM learning_packages")
    conn.commit()
    
    # Optimal paket boyutu
    optimal_size = 500
    num_packages = (total_words + optimal_size - 1) // optimal_size
    print(f"\n[PLAN] PAKET PLANI:")
    print(f"   Paket boyutu: {optimal_size} kelime")
    print(f"   Toplam seviye: {num_packages}")
    
    # Frekansa gore kelimeleri sirala ve paketle
    print(f"\n[NOTE] SEVIYELER OLUSTURULUYOR...")
    
    for i in range(0, total_words, optimal_size):
        package_num = (i // optimal_size) + 1
        package_words = words[i:i + optimal_size]
        
        if not package_words:
            continue
        
        min_freq = package_words[-1]['frequency']
        max_freq = package_words[0]['frequency']
        first_word = package_words[0]['word']
        last_word = package_words[-1]['word']
        
        package_name = f"Level {package_num}: {first_word} - {last_word}"
        
        cursor.execute('''
            INSERT INTO learning_packages (package_number, package_name, word_count, min_frequency, max_frequency)
            VALUES (?, ?, ?, ?, ?)
        ''', (package_num, package_name, len(package_words), min_freq, max_freq))
        
        package_id = cursor.lastrowid
        
        # Pakete kelimeleri ekle
        batch_values = [(package_id, w['id'], rank) for rank, w in enumerate(package_words, start=1)]
        cursor.executemany('''
            INSERT INTO package_words (package_id, word_id, word_rank)
            VALUES (?, ?, ?)
        ''', batch_values)
        
        conn.commit()
        print(f"   [OK] Level {package_num}: {len(package_words)} kelime (frekans: {max_freq}-{min_freq})")
    
    # 3. Istatistikleri goster
    print("\n=== ADIM 3: SONUCLAR ===")
    
    cursor.execute("SELECT COUNT(*) FROM learning_packages")
    pkg_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM package_words")
    total_pkg_words = cursor.fetchone()[0]
    
    print(f"\n[TAMAMLANDI]!")
    print(f"   Toplam seviye: {pkg_count}")
    print(f"   Toplam package_words: {total_pkg_words}")
    print(f"   Eslesme: {'[EVET]' if total_pkg_words == total_words else '[HATA]'}")
    
    # Ornek seviyeler
    print(f"\n[LISTE] ORNEK SEVIYELER:")
    cursor.execute('''
        SELECT package_number, package_name, word_count, min_frequency, max_frequency
        FROM learning_packages
        ORDER BY package_number
        LIMIT 10
    ''')
    for row in cursor.fetchall():
        print(f"   Level {row['package_number']}: {row['word_count']} kelime | Frekans: {row['max_frequency']}-{row['min_frequency']}")
    
    # Son seviye
    cursor.execute('''
        SELECT package_number, word_count, min_frequency, max_frequency
        FROM learning_packages
        ORDER BY package_number DESC
        LIMIT 1
    ''')
    last = cursor.fetchone()
    if last:
        print(f"   ...")
        print(f"   Level {last['package_number']}: {last['word_count']} kelime | Frekans: {last['max_frequency']}-{last['min_frequency']}")
    
    conn.close()
    print("\n" + "=" * 60)

def show_learning_stats():
    """Show current learning statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n[STAT] MEVCUT OGRENME ISTATISTIKLERI")
    print("-" * 40)
    
    # Toplam kelime ve frekans
    cursor.execute("SELECT COUNT(*), SUM(frequency) FROM words")
    total, freq = cursor.fetchone()
    print(f"Toplam Kelime: {total}")
    print(f"Toplam Frekans: {freq}")
    
    # En sik kullanilan 10 kelime
    print(f"\nEn Sik Kullanilan 10 Kelime:")
    cursor.execute("SELECT word, frequency FROM words ORDER BY frequency DESC LIMIT 10")
    for i, (word, freq) in enumerate(cursor.fetchall(), 1):
        print(f"  {i:2}. {word:15} ({freq})")
    
    # Seviye ozeti
    print(f"\nSeviye Ozeti:")
    cursor.execute('''
        SELECT package_number, package_name, word_count, min_frequency, max_frequency
        FROM learning_packages ORDER BY package_number
    ''')
    levels = cursor.fetchall()
    print(f"Toplam Seviye: {len(levels)}")
    
    for level in levels[:5]:
        print(f"  Level {level['package_number']}: {level['word_count']} kelime")
    
    if len(levels) > 5:
        print(f"  ... ve {len(levels) - 5} seviye daha")
    
    conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--stats':
        show_learning_stats()
    else:
        calculate_word_map_and_regenerate_levels()

