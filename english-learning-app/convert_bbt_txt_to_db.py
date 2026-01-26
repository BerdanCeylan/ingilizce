#!/usr/bin/env python3
"""
Big Bang Theory .txt altyazı dosyalarını SQLite veritabanına dönüştürür.
Kullanım: python convert_bbt_txt_to_db.py
"""

import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

# Ayarlar
SUBTITLES_DIR = os.path.join(os.path.dirname(__file__), 'Subtitles', 'BigBangTheory')
DATABASE_DIR = SUBTITLES_DIR  # DB dosyaları txt dosyalarıyla aynı klasöre


def extract_words(text):
    """Metinden kelimeleri ayıklar."""
    # Sadece harfleri ve kesme işaretlerini koru (don't, it's gibi)
    words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", text.lower())
    
    # Tek harfli kelimelerden sadece 'a' ve 'i' kalsın
    filtered_words = [w for w in words if len(w) > 1 or w in ['a', 'i']]
    
    return filtered_words


def create_db_from_txt(txt_path):
    """Bir .txt dosyasından SQLite veritabanı oluşturur."""
    txt_filename = os.path.basename(txt_path)
    db_filename = os.path.splitext(txt_filename)[0] + '.db'
    db_path = os.path.join(DATABASE_DIR, db_filename)
    
    print(f"📄 İşleniyor: {txt_filename}")
    
    # Dosyayı oku
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(txt_path, 'r', encoding='latin-1') as f:
            content = f.read()
    
    # Karakter adlarını ve ": " karakterini kaldır
    # Örnek: "Sheldon: Hello" -> "Hello"
    content = re.sub(r'^[A-Za-z]+\s*:', '', content, flags=re.MULTILINE)
    
    # Kelimeleri çıkar
    words = extract_words(content)
    
    if not words:
        print(f"  ⚠️ Uyarı: {txt_filename} dosyasında kelime bulunamadı!")
        return 0
    
    # Frekansları hesapla
    word_counts = Counter(words)
    
    print(f"  📊 İstatistikler: {len(words)} toplam kelime, {len(word_counts)} benzersiz kelime")
    
    # Veritabanı oluştur
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tabloyu oluştur
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""
            CREATE TABLE word_frequencies (
                word TEXT PRIMARY KEY,
                frequency INTEGER NOT NULL
            )
        """)
        
        # Tablo meta bilgisi
        cursor.execute("DROP TABLE IF EXISTS episode_info")
        cursor.execute("""
            CREATE TABLE episode_info (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Episode bilgilerini kaydet
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('filename', txt_filename))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('total_words', str(len(words))))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('unique_words', str(len(word_counts))))
        
        # Verileri frekansa göre sırala
        sorted_data = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Verileri ekle
        cursor.executemany("INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)", sorted_data)
        
        conn.commit()
        conn.close()
        
        print(f"  ✅ Oluşturuldu: {db_filename}")
        
        # İlk 5 kelimeyi göster
        print(f"     En sık 5 kelime: ", end="")
        top_5 = sorted_data[:5]
        print(", ".join([f"{w}:{f}" for w, f in top_5]))
        
        return 1
        
    except sqlite3.Error as e:
        print(f"  ❌ Veritabanı hatası: {e}")
        return 0


def main():
    print("=" * 60)
    print("🎬 Big Bang Theory .txt → SQLite Dönüştürme Aracı")
    print("=" * 60)
    print(f"\n📂 Klasör: {SUBTITLES_DIR}\n")
    
    if not os.path.exists(SUBTITLES_DIR):
        print(f"❌ Hata: Klasör bulunamadı: {SUBTITLES_DIR}")
        return
    
    # Tüm .txt dosyalarını bul
    txt_files = sorted(Path(SUBTITLES_DIR).glob('*.txt'))
    
    if not txt_files:
        print("❌ Hata: .txt dosyası bulunamadı!")
        return
    
    print(f"📋 Toplam {len(txt_files)} dosya bulundu.\n")
    
    total_created = 0
    total_errors = 0
    
    for txt_path in txt_files:
        success = create_db_from_txt(txt_path)
        if success:
            total_created += 1
        else:
            total_errors += 1
        print()
    
    print("=" * 60)
    print(f"🏁 Tamamlandı!")
    print(f"   ✅ Başarılı: {total_created} veritabanı oluşturuldu")
    print(f"   ❌ Hatalı: {total_errors}")
    print(f"   📁 Konum: {DATABASE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

