#!/usr/bin/env python3
import sqlite3
import os

DB_PATH = 'learning.db'

def main():
    print("🚀 Kelime Transfer Aracı: word_frequency -> words")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Veritabanı dosyası bulunamadı: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Tablo kontrolleri
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='word_frequency'")
        if not cursor.fetchone():
            print("❌ Kaynak tablo 'word_frequency' bulunamadı.")
            print("   Lütfen önce 'import_word_list.py' scriptini çalıştırın.")
            return

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='words'")
        if not cursor.fetchone():
            print("❌ Hedef tablo 'words' bulunamadı.")
            print("   Lütfen önce uygulamayı (app.py) en az bir kez çalıştırın.")
            return

        # 2. Mevcut durumu analiz et
        cursor.execute("SELECT COUNT(*) FROM words")
        initial_count = cursor.fetchone()[0]
        print(f"📊 Başlangıçtaki kelime sayısı (words): {initial_count}")

        print("🔄 Aktarım başlıyor...")

        # 3. SQL ile toplu aktarım
        # word_frequency tablosundaki kelimeleri words tablosuna kopyalar.
        # Çakışan (zaten var olan) kelimeleri atlar (IGNORE).
        cursor.execute("""
            INSERT OR IGNORE INTO words (word)
            SELECT word FROM word_frequency
        """)
        
        added_count = cursor.rowcount
        conn.commit()

        # 4. Sonuç
        cursor.execute("SELECT COUNT(*) FROM words")
        final_count = cursor.fetchone()[0]

        print(f"✅ İşlem Başarılı! {added_count} yeni kelime eklendi.")
        print(f"📚 Toplam kelime sayısı: {final_count}")

    except sqlite3.Error as e:
        print(f"❌ Veritabanı hatası: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()