#!/usr/bin/env python3
"""Database repair and optimization script"""
import sqlite3
import os

DB_PATH = 'learning.db'

def backup_db():
    """Create a backup before making changes"""
    if os.path.exists(DB_PATH):
        backup_path = DB_PATH.replace('.db', '_backup.db')
        if os.path.exists(backup_path):
            os.remove(backup_path)
        import shutil
        shutil.copy(DB_PATH, backup_path)
        print(f"✅ Yedek oluşturuldu: {backup_path}")
        return True
    return False

def check_database():
    """Analyze database and return issues"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    issues = []
    
    # 1. Check duplicate words
    cursor.execute('SELECT word, COUNT(*) as cnt FROM words GROUP BY word HAVING cnt > 1')
    duplicates = cursor.fetchall()
    if duplicates:
        issues.append({
            'type': 'duplicate_words',
            'count': len(duplicates),
            'details': [(d['word'], d['cnt']) for d in duplicates[:10]]
        })
    
    # 2. Check words without frequency data
    cursor.execute('SELECT COUNT(*) as cnt FROM words WHERE frequency = 0 OR frequency IS NULL')
    no_freq = cursor.fetchone()['cnt']
    if no_freq > 0:
        issues.append({
            'type': 'missing_frequency',
            'count': no_freq
        })
    
    # 3. Check orphan records in user_words
    cursor.execute('''SELECT COUNT(*) as cnt FROM user_words uw 
                      LEFT JOIN words w ON uw.word_id = w.id WHERE w.id IS NULL''')
    orphan_uw = cursor.fetchone()['cnt']
    if orphan_uw > 0:
        issues.append({
            'type': 'orphan_user_words',
            'count': orphan_uw
        })
    
    # 4. Check orphan records in video_words
    cursor.execute('''SELECT COUNT(*) as cnt FROM video_words vw 
                      LEFT JOIN words w ON vw.word_id = w.id WHERE w.id IS NULL''')
    orphan_vw = cursor.fetchone()['cnt']
    if orphan_vw > 0:
        issues.append({
            'type': 'orphan_video_words',
            'count': orphan_vw
        })
    
    # 5. Check orphan records in package_words
    cursor.execute('''SELECT COUNT(*) as cnt FROM package_words pw 
                      LEFT JOIN words w ON pw.word_id = w.id WHERE w.id IS NULL''')
    orphan_pw = cursor.fetchone()['cnt']
    if orphan_pw > 0:
        issues.append({
            'type': 'orphan_package_words',
            'count': orphan_pw
        })
    
    # 6. Check duplicate package_words
    cursor.execute('''SELECT word_id, COUNT(*) as cnt FROM package_words GROUP BY word_id HAVING cnt > 1''')
    dup_pkg = cursor.fetchall()
    if dup_pkg:
        issues.append({
            'type': 'duplicate_package_words',
            'count': len(dup_pkg)
        })
    
    conn.close()
    return issues

def fix_database():
    """Apply fixes to the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n=== VERİTABANI DÜZELTME İŞLEMLERİ ===\n")
    
    # 1. Remove duplicate words (keep the one with highest frequency)
    print("1. Tekrarlanan kelimeler temizleniyor...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS words_clean AS
        SELECT w1.* FROM words w1
        WHERE w1.frequency = (SELECT MAX(w2.frequency) FROM words w2 WHERE w2.word = w1.word)
        AND w1.rowid = (SELECT MIN(w2.rowid) FROM words w2 WHERE w2.word = w1.word)
    ''')
    
    # Get counts before and after
    cursor.execute('SELECT COUNT(*) FROM words')
    before = cursor.fetchone()[0]
    
    cursor.execute('DROP TABLE IF EXISTS words')
    cursor.execute('ALTER TABLE words_clean RENAME TO words')
    conn.commit()
    
    cursor.execute('SELECT COUNT(*) FROM words')
    after = cursor.fetchone()[0]
    print(f"   ✓ {before - after} tekrarlanan kayıt silindi")
    print(f"   ✓ {after} benzersiz kelime kaldı")
    
    # 2. Fix missing frequencies from word_frequency table
    print("\n2. Eksik frekans bilgileri güncelleniyor...")
    try:
        cursor.execute('''
            UPDATE words 
            SET frequency = (
                SELECT wf.frequency 
                FROM word_frequency wf 
                WHERE wf.word = words.word
            )
            WHERE frequency = 0 OR frequency IS NULL
        ''')
        updated = cursor.rowcount
        print(f"   ✓ {updated} kelime frekansı güncellendi")
    except Exception as e:
        print(f"   ! word_frequency tablosu bulunamadı: {e}")
    
    # 3. Remove orphan records
    print("\n3. Orphan (kelimesiz) kayıtlar temizleniyor...")
    
    # user_words
    cursor.execute('''DELETE FROM user_words WHERE word_id IN 
                      (SELECT uw.word_id FROM user_words uw LEFT JOIN words w ON uw.word_id = w.id WHERE w.id IS NULL)''')
    orphan_removed = cursor.rowcount
    print(f"   ✓ user_words: {orphan_removed} kayıt silindi")
    
    # video_words
    cursor.execute('''DELETE FROM video_words WHERE word_id IN 
                      (SELECT vw.word_id FROM video_words vw LEFT JOIN words w ON vw.word_id = w.id WHERE w.id IS NULL)''')
    orphan_removed = cursor.rowcount
    print(f"   ✓ video_words: {orphan_removed} kayıt silindi")
    
    # package_words
    cursor.execute('''DELETE FROM package_words WHERE word_id IN 
                      (SELECT pw.word_id FROM package_words pw LEFT JOIN words w ON pw.word_id = w.id WHERE w.id IS NULL)''')
    orphan_removed = cursor.rowcount
    print(f"   ✓ package_words: {orphan_removed} kayıt silindi")
    
    # 4. Fix duplicate package_words
    print("\n4. package_words tekrarları temizleniyor...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS package_words_clean AS
        SELECT DISTINCT pw.* FROM package_words pw
        WHERE pw.rowid IN (
            SELECT MIN(rowid) FROM package_words GROUP BY package_id, word_id
        )
    ''')
    cursor.execute('DROP TABLE IF EXISTS package_words')
    cursor.execute('ALTER TABLE package_words_clean RENAME TO package_words')
    conn.commit()
    print("   ✓ package_words benzersiz yapıldı")
    
    # 5. Rebuild indexes
    print("\n5. İndexler yeniden oluşturuluyor...")
    indexes = ['idx_words_word', 'idx_user_words_user', 'idx_video_words_video', 'idx_package_words_package']
    for idx in indexes:
        cursor.execute(f'DROP INDEX IF EXISTS {idx}')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_words_user ON user_words(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_words_video ON video_words(video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_package_words_package ON package_words(package_id)')
    conn.commit()
    print("   ✓ Indexler oluşturuldu")
    
    conn.close()
    print("\n✅ Veritabanı düzeltme tamamlandı!")

def show_final_status():
    """Show final database status"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n=== SON DURUM ===\n")
    
    # Table counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    print("TABLOLAR:")
    for t in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {t[0]}')
        count = cursor.fetchone()[0]
        print(f"  {t[0]}: {count} kayıt")
    
    # Word stats
    cursor.execute('SELECT COUNT(*) as total, SUM(frequency) as total_freq FROM words')
    stats = cursor.fetchone()
    print(f"\nKELİME İSTATİSTİKLERİ:")
    print(f"  Toplam kelime: {stats['total']}")
    print(f"  Toplam frekans: {stats['total_freq']}")
    
    # Duplicate check
    cursor.execute('SELECT word, COUNT(*) as cnt FROM words GROUP BY word HAVING cnt > 1')
    dup = cursor.fetchall()
    print(f"  Tekrarlanan kelimeler: {len(dup)}")
    
    # Package stats
    if cursor.execute("SELECT COUNT(*) FROM learning_packages").fetchone()[0] > 0:
        cursor.execute('SELECT COUNT(*) FROM package_words')
        pkg_words = cursor.fetchone()[0]
        print(f"\nPAKET SİSTEMİ:")
        print(f"  package_words toplam: {pkg_words}")
        print(f"  words tablosu: {stats['total']}")
        print(f"  Eşleşme: {'✅' if pkg_words == stats['total'] else '❌'}")
    
    conn.close()

if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("VERİTABANI ARAÇLARI")
    print("=" * 60)
    print("\nSeçenekler:")
    print("  1 - Sadece kontrol et")
    print("  2 - Yedek al ve düzelt")
    print("  3 - Sadece durumu göster")
    
    choice = input("\nSeçiminiz (1-3): ").strip()
    
    if choice == '1':
        issues = check_database()
        if issues:
            print("\nBULUNAN SORUNLAR:")
            for issue in issues:
                print(f"  - {issue['type']}: {issue['count']} kayıt")
        else:
            print("\n✅ Veritabanında sorun bulunamadı!")
        show_final_status()
    elif choice == '2':
        if backup_db():
            fix_database()
            show_final_status()
    elif choice == '3':
        show_final_status()
    else:
        print("Geçersiz seçim!")

