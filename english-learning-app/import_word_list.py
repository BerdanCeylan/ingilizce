#!/usr/bin/env python3
import sqlite3
import csv
import os

# Yapılandırma
DB_PATH = 'learning.db'
CSV_FILENAME = 'word_list.csv'

def find_csv_path():
    """CSV dosyasını farklı konumlarda arar"""
    possible_paths = [
        CSV_FILENAME,
        os.path.join('VocabLevel-master', 'VocabLevel-master', CSV_FILENAME),
        os.path.join('..', CSV_FILENAME),
        '/home/duffyduck/Downloads/ingilizce/VocabLevel-master/VocabLevel-master/word_list.csv'  # Fallback
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return CSV_FILENAME

def main():
    csv_path = find_csv_path()
    print("🚀 Kelime Listesi İçe Aktarıcı")
    print(f"📂 Veritabanı: {DB_PATH}")
    print(f"📄 CSV Dosyası: {csv_path}")

    # CSV dosyasını kontrol et
    if not os.path.exists(csv_path):
        print(f"❌ Hata: CSV dosyası bulunamadı: {csv_path}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Tabloyu oluştur (word_frequency)
        print("🛠️  Tablo kontrol ediliyor (word_frequency)...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_frequency (
                word TEXT PRIMARY KEY,
                frequency INTEGER
            )
        ''')
        
        # Hızlı sorgulama için index (Primary key zaten indexlidir ama emin olalım)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_freq ON word_frequency(frequency DESC)')

        # Verileri oku ve ekle
        print("📥 Veriler okunuyor ve ekleniyor...")
        
        inserted_count = 0
        batch_data = []
        BATCH_SIZE = 5000

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    word = row[0].strip().lower()
                    try:
                        freq = int(row[1].strip())
                        batch_data.append((word, freq))
                        inserted_count += 1
                    except ValueError:
                        continue
                
                if len(batch_data) >= BATCH_SIZE:
                    cursor.executemany('INSERT OR REPLACE INTO word_frequency (word, frequency) VALUES (?, ?)', batch_data)
                    batch_data = []
                    print(f"   ... {inserted_count} kelime işlendi", end='\r')

            # Kalan verileri ekle
            if batch_data:
                cursor.executemany('INSERT OR REPLACE INTO word_frequency (word, frequency) VALUES (?, ?)', batch_data)

        conn.commit()
        print(f"\n✅ Başarılı! Toplam {inserted_count} kelime 'word_frequency' tablosuna eklendi.")

        # Kontrol amaçlı en sık kullanılan 5 kelimeyi göster
        print("\n🔍 En sık kullanılan 5 kelime:")
        cursor.execute('SELECT word, frequency FROM word_frequency ORDER BY frequency DESC LIMIT 5')
        for row in cursor.fetchall():
            print(f"   - {row[0]}: {row[1]}")

        # Analiz: Kelime haritası (words tablosu) ile karşılaştırma
        print("\n📊 Analiz: Kelime Haritası (words tablosu) ile Karşılaştırma")
        
        # words tablosunun varlığını kontrol et
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='words'")
        if not cursor.fetchone():
            print("⚠️ 'words' tablosu bulunamadı. Uygulama henüz çalıştırılmamış olabilir.")
        else:
            # Toplam kelime sayısı (words tablosu)
            cursor.execute("SELECT COUNT(*) FROM words")
            total_app_words = cursor.fetchone()[0]
            
            # Eşleşen kelime sayısı
            cursor.execute("""
                SELECT COUNT(*) FROM words w
                INNER JOIN word_frequency wf ON w.word = wf.word
            """)
            matching_words = cursor.fetchone()[0]
            
            print(f"   - Uygulamadaki toplam kelime sayısı: {total_app_words}")
            print(f"   - Frekans listesiyle eşleşen kelimeler: {matching_words}")
            
            if total_app_words > 0:
                coverage = (matching_words / total_app_words) * 100
                print(f"   - Kapsama Oranı: %{coverage:.2f}")

            # Eşleşmeyen (listede olup uygulamada olmayan) ilk 5 kelime (yüksek frekanslı)
            print("\n🔍 Uygulamada OLMAYAN en yaygın 5 kelime (word_frequency tablosundan):")
            cursor.execute("""
                SELECT wf.word, wf.frequency 
                FROM word_frequency wf
                LEFT JOIN words w ON wf.word = w.word
                WHERE w.word IS NULL
                ORDER BY wf.frequency DESC
                LIMIT 5
            """)
            missing = cursor.fetchall()
            if missing:
                for w, f in missing:
                    print(f"   - {w} (Frekans: {f})")
            else:
                print("   (Tüm yüksek frekanslı kelimeler uygulamada mevcut)")

    except sqlite3.Error as e:
        print(f"\n❌ Veritabanı hatası: {e}")
    except Exception as e:
        print(f"\n❌ Beklenmeyen hata: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
