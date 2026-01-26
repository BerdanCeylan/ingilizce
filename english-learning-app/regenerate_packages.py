#!/usr/bin/env python3
"""Regenerate learning packages with all words"""
import sqlite3
import shutil

LEARNING_DB = '/home/duffyduck/Downloads/ingilizce/english-learning-app/learning.db'

def regenerate_packages():
    print("=== LEARNING PACKAGES YENİDEN OLUŞTURMA ===\n")
    
    # Backup
    backup_path = LEARNING_DB.replace('.db', '_backup3.db')
    shutil.copy(LEARNING_DB, backup_path)
    print(f"✓ Yedek alındı: {backup_path}")
    
    conn = sqlite3.connect(LEARNING_DB)
    cursor = conn.cursor()
    
    # Mevcut durum
    cursor.execute('SELECT COUNT(*) FROM words')
    word_count = cursor.fetchone()[0]
    print(f"Toplam kelime: {word_count}")
    
    cursor.execute('SELECT COUNT(*) FROM learning_packages')
    old_packages = cursor.fetchone()[0]
    print(f"Eski package sayısı: {old_packages}")
    
    # Eski paketleri sil
    cursor.execute('DELETE FROM package_words')
    cursor.execute('DELETE FROM learning_packages')
    conn.commit()
    
    print("\nYeni paketler oluşturuluyor...")
    
    # Tüm kelimeleri frekansa göre al
    cursor.execute('SELECT id, word, frequency FROM words ORDER BY frequency DESC')
    all_words = cursor.fetchall()
    print(f"Kelime sayısı: {len(all_words)}")
    
    # Paket boyutu (her pakette 500 kelime)
    package_size = 500
    created = 0
    
    for i in range(0, len(all_words), package_size):
        package_num = (i // package_size) + 1
        package_words = all_words[i:i + package_size]
        
        if not package_words:
            continue
        
        min_freq = package_words[-1][2]
        max_freq = package_words[0][2]
        first_word = package_words[0][1]
        last_word = package_words[-1][1]
        
        package_name = f"Level {package_num}: {first_word} - {last_word}"
        
        cursor.execute('''
            INSERT INTO learning_packages (package_number, package_name, word_count, min_frequency, max_frequency)
            VALUES (?, ?, ?, ?, ?)
        ''', (package_num, package_name, len(package_words), min_freq, max_freq))
        
        package_id = cursor.lastrowid
        
        # Pakete kelimeleri ekle
        batch_values = [(package_id, row[0], rank) for rank, row in enumerate(package_words, start=1)]
        cursor.executemany('''
            INSERT INTO package_words (package_id, word_id, word_rank)
            VALUES (?, ?, ?)
        ''', batch_values)
        
        created += 1
        
        if created % 5 == 0:
            conn.commit()
            print(f"  ✓ {created} paket oluşturuldu...")
    
    conn.commit()
    
    # Yeni durum
    cursor.execute('SELECT COUNT(*) FROM learning_packages')
    new_packages = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM package_words')
    total_pkg_words = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM words')
    final_words = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ BİTTİ!")
    print(f"  Yeni paket sayısı: {new_packages}")
    print(f"  Toplam package_words: {total_pkg_words}")
    print(f"  Toplam words: {final_words}")
    print(f"  Eşleşme: {'✅' if total_pkg_words == final_words else '❌'}")
    
    # Örnek seviyeleri göster
    print(f"\nÖRNEK SEVİYELER:")
    conn2 = sqlite3.connect(LEARNING_DB)
    cursor2 = conn2.cursor()
    cursor2.execute('''
        SELECT package_number, package_name, word_count, min_frequency, max_frequency
        FROM learning_packages ORDER BY package_number LIMIT 10
    ''')
    for row in cursor2.fetchall():
        print(f"  Level {row[0]}: {row[2]} kelime | Frekans: {row[4]}-{row[3]}")
    conn2.close()

if __name__ == '__main__':
    regenerate_packages()

