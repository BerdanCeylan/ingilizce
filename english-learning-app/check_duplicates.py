#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('learning.db')
cursor = conn.cursor()

print("=" * 60)
print("KELIME LISTESI TEKRAR KONTROLU")
print("=" * 60)

# 1. words tablosunda tekrarlar
print("\n1. WORDS TABLOSU:")
cursor.execute("SELECT word, COUNT(*) as cnt FROM words GROUP BY word HAVING cnt > 1")
dup_words = cursor.fetchall()
if dup_words:
    print(f"   [!] {len(dup_words)} tekrarlanan kelime bulundu:")
    for w, c in dup_words[:20]:
        print(f"      - '{w}' ({c} kez)")
else:
    print("   [OK] Tekrarlanan kelime yok")

cursor.execute("SELECT COUNT(*) as total FROM words")
total = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(DISTINCT word) as unique_count FROM words")
unique = cursor.fetchone()[0]
print(f"\n   Toplam kayit: {total}")
print(f"   Benzersiz kelime: {unique}")
print(f"   Tekrar: {total - unique}")

# 2. package_words tablosunda tekrarlar
print("\n2. PACKAGE_WORDS TABLOSU:")
cursor.execute('''
    SELECT word_id, COUNT(*) as cnt 
    FROM package_words 
    GROUP BY word_id 
    HAVING cnt > 1
''')
dup_pkgs = cursor.fetchall()
if dup_pkgs:
    print(f"   [!] {len(dup_pkgs)} kelime birden fazla pakette bulunuyor")
else:
    print("   [OK] Her kelime yalnızca bir pakette")

# 3. Toplam paket kelime sayisi kontrolü
cursor.execute("SELECT COUNT(*) FROM package_words")
total_pkg_words = cursor.fetchone()[0]
print(f"\n   package_words toplam: {total_pkg_words}")
print(f"   words tablosu: {total}")
print(f"   Eslesme: {'[OK]' if total_pkg_words == total else '[!] FARKLI!'}")

conn.close()
print("\n" + "=" * 60)

