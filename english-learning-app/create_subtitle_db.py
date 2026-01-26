#!/usr/bin/env python3
import sqlite3
import re
import sys
import os
from collections import Counter

class SubtitleDBCreator:
    """
    Bir altyazı dosyasını (SRT) okur, kelime frekanslarını hesaplar
    ve o dosyaya özel bir SQLite veritabanı oluşturur.
    """
    def __init__(self, srt_path):
        self.srt_path = srt_path
        # Dosya adından veritabanı adı oluştur (örn: Friends_S01E01.srt -> Friends_S01E01.db)
        self.base_name = os.path.splitext(os.path.basename(srt_path))[0]
        self.db_name = os.path.join(os.path.dirname(srt_path), f"{self.base_name}.db")

    def extract_words(self):
        """SRT dosyasından kelimeleri ayıklar."""
        if not os.path.exists(self.srt_path):
            print(f"❌ Hata: Dosya bulunamadı: {self.srt_path}")
            return []

        try:
            # Farklı encodingleri dene (utf-8 veya latin-1)
            try:
                with open(self.srt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(self.srt_path, 'r', encoding='latin-1') as f:
                    content = f.read()
        except Exception as e:
            print(f"❌ Dosya okuma hatası: {e}")
            return []

        # SRT temizliği
        # 1. Zaman damgalarını sil (00:00:20,000 --> 00:00:24,400)
        content = re.sub(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', ' ', content)
        # 2. Satır numaralarını ve zaman damgası kalıntılarını sil
        content = re.sub(r'\n\d+\s*\n', ' ', content)
        # 3. HTML taglerini sil (<i>, <b>, <font> vb.)
        content = re.sub(r'<[^>]+>', ' ', content)
        # 4. Köşeli ve süslü parantezleri sil ([Gülüşmeler], {Müzik} vb.)
        content = re.sub(r'\[[^\]]*\]', ' ', content)
        content = re.sub(r'\{[^}]+\}', ' ', content)
        
        # Kelimeleri ayıkla: Sadece harfler ve kelime içi kesme işaretleri (don't, it's)
        # word_list.csv formatına uygun olması için küçük harfe çeviriyoruz.
        words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", content.lower())
        
        # Tek harfli kelimelerden sadece 'a' ve 'i' kalsın, diğerleri (örn: srt hataları) elensin
        filtered_words = [w for w in words if len(w) > 1 or w in ['a', 'i']]
        
        return filtered_words

    def create_db(self):
        """Kelimeleri sayar ve veritabanına kaydeder."""
        print(f"📂 Dosya işleniyor: {self.srt_path}")
        words = self.extract_words()
        
        if not words:
            print("⚠️ İşlenecek kelime bulunamadı.")
            return

        # Frekansları hesapla
        word_counts = Counter(words)
        print(f"📊 İstatistikler: {len(words)} toplam kelime, {len(word_counts)} benzersiz kelime.")

        try:
            # Veritabanı bağlantısı
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            # Tabloyu oluştur
            cursor.execute("DROP TABLE IF EXISTS word_frequencies")
            cursor.execute("""
                CREATE TABLE word_frequencies (
                    word TEXT PRIMARY KEY,
                    frequency INTEGER NOT NULL
                )
            """)

            # Verileri frekansa göre sırala (en çok geçenden en aza)
            sorted_data = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

            # Verileri ekle
            cursor.executemany("INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)", sorted_data)

            conn.commit()
            conn.close()

            print(f"✅ Veritabanı başarıyla oluşturuldu: {self.db_name}")
            print(f"✅ Veriler 'word_frequencies' tablosuna kaydedildi.")
            
            # Önizleme
            print("\n🔍 En sık geçen 10 kelime:")
            for word, freq in sorted_data[:10]:
                print(f"   {word}: {freq}")

        except sqlite3.Error as e:
            print(f"❌ Veritabanı hatası: {e}")

def main():
    if len(sys.argv) < 2:
        print("Kullanım: python create_subtitle_db.py <altyazı_dosyası.srt>")
        print("Örnek: python create_subtitle_db.py Friends.S01E01.srt")
    else:
        creator = SubtitleDBCreator(sys.argv[1])
        creator.create_db()

if __name__ == "__main__":
    main()