#!/usr/bin/env python3
"""
Big Bang Theory veritabanlarından kelimeleri ana learning.db'ye aktarır.
"""

import os
import sqlite3

# Ayarlar
BBT_DIR = os.path.join(os.path.dirname(__file__), 'Subtitles', 'BigBangTheory')
MAIN_DB = 'learning.db'


def get_episode_name(db_filename):
    """DB dosya adından bölüm adını çıkar"""
    # series-1-episode-1-pilot-episode.db -> Series 1 Episode 1: Pilot Episode
    name = db_filename.replace('.db', '')
    parts = name.split('-')
    if len(parts) >= 5:
        series = parts[1]
        episode = parts[3]
        return f"Big Bang Theory S{series}E{episode}"
    return f"Big Bang Theory - {name}"


def import_all_bbt_words():
    """Tüm BBT veritabanlarından kelimeleri ana DB'ye aktarır"""
    
    print("=" * 60)
    print("📚 Big Bang Theory Kelimeleri Ana DB'ye Aktarılıyor")
    print("=" * 60)
    print(f"\n📂 BBT DB Klasörü: {BBT_DIR}")
    print(f"📂 Ana DB: {MAIN_DB}\n")
    
    # Ana DB'ye bağlan
    main_conn = sqlite3.connect(MAIN_DB)
    main_cursor = main_conn.cursor()
    
    # Mevcut kelime sayısını kontrol et
    main_cursor.execute("SELECT COUNT(*) FROM words")
    before_count = main_cursor.fetchone()[0]
    print(f"📊 Mevcut kelime sayısı (önce): {before_count}")
    
    # Tüm BBT .db dosyalarını bul
    db_files = [f for f in os.listdir(BBT_DIR) if f.endswith('.db') and f != 'combined_stats.db']
    db_files.sort()
    
    print(f"\n📋 {len(db_files)} adet BBT veritabanı bulundu.\n")
    
    total_new_words = 0
    total_word_occurrences = 0
    
    for db_file in db_files:
        db_path = os.path.join(BBT_DIR, db_file)
        episode_name = get_episode_name(db_file)
        
        print(f"📄 İşleniyor: {db_file}")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # episode_info tablosundan bilgi al
            cursor.execute("SELECT key, value FROM episode_info")
            info = dict(cursor.fetchall())
            total_words = int(info.get('total_words', 0))
            unique_words = int(info.get('unique_words', 0))
            
            # Kelimeleri al
            cursor.execute("SELECT word, frequency FROM word_frequencies")
            words_data = cursor.fetchall()
            
            conn.close()
            
            print(f"   📊 {total_words} kelime, {unique_words} benzersiz")
            
            # Ana DB'ye ekle
            for word, freq in words_data:
                word_lower = word.lower().strip()
                if not word_lower:
                    continue
                
                # Kelimeyi words tablosuna ekle veya güncelle
                main_cursor.execute("SELECT id, frequency FROM words WHERE word = ?", (word_lower,))
                existing = main_cursor.fetchone()
                
                if existing:
                    # Güncelle
                    new_freq = existing[1] + freq
                    main_cursor.execute("UPDATE words SET frequency = ? WHERE id = ?", (new_freq, existing[0]))
                else:
                    # Ekle
                    main_cursor.execute("INSERT INTO words (word, frequency) VALUES (?, ?)", (word_lower, freq))
                    total_new_words += 1
                
                total_word_occurrences += freq
            
            print(f"   ✅ Eklendi/Güncellendi")
            
        except Exception as e:
            print(f"   ❌ Hata: {e}")
    
    main_conn.commit()
    
    # Son kelime sayısını kontrol et
    main_cursor.execute("SELECT COUNT(*) FROM words")
    after_count = main_cursor.fetchone()[0]
    
    print("\n" + "=" * 60)
    print("📈 Özet:")
    print(f"   Önce: {before_count} kelime")
    print(f"   Sonra: {after_count} kelime")
    print(f"   Yeni eklenen: {total_new_words}")
    print(f"   Toplam kelime tekrarı: {total_word_occurrences}")
    print("=" * 60)
    
    main_conn.close()
    
    return total_new_words


if __name__ == "__main__":
    import_all_bbt_words()

