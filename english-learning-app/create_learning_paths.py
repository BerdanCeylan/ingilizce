#!/usr/bin/env python3
"""
Learning Pathway Generator
Organizes vocabulary words into packages of 500 based on frequency
for structured learning.
"""

import sqlite3
import csv
import os

DATABASE_PATH = 'learning.db'
PACKAGE_SIZE = 500

def create_learning_pathways():
    """Create learning pathways by grouping words into packages"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create learning_packages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_number INTEGER NOT NULL UNIQUE,
            package_name TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            min_frequency INTEGER DEFAULT 0,
            max_frequency INTEGER DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create package_words junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS package_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            word_rank INTEGER NOT NULL,
            FOREIGN KEY (package_id) REFERENCES learning_packages(id),
            FOREIGN KEY (word_id) REFERENCES words(id),
            UNIQUE(package_id, word_id)
        )
    ''')
    
    # Update frequencies from CSV to ensure correct ordering
    possible_paths = [
        '/home/duffyduck/Downloads/ingilizce/VocabLevel-master/VocabLevel-master/word_list.csv',
        'word_list.csv',
        '../word_list.csv'
    ]
    
    csv_path = next((p for p in possible_paths if os.path.exists(p)), None)
    
    if csv_path:
        print(f"📊 Updating word frequencies from {csv_path}...")
        try:
            updates = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        word = row[0].strip().lower()
                        try:
                            freq = int(row[1].strip())
                            updates.append((freq, word))
                        except ValueError:
                            continue
            
            if updates:
                cursor.executemany('UPDATE words SET frequency = ? WHERE word = ?', updates)
                conn.commit()
                print(f"✅ Updated frequencies for {len(updates)} words.")
        except Exception as e:
            print(f"⚠️ Error updating frequencies from CSV: {e}")
    else:
        # Try fallback to word_frequency table
        try:
            cursor.execute("UPDATE words SET frequency = (SELECT frequency FROM word_frequency WHERE word_frequency.word = words.word) WHERE EXISTS (SELECT 1 FROM word_frequency WHERE word_frequency.word = words.word)")
            conn.commit()
            print("✅ Updated frequencies from word_frequency table (fallback).")
        except Exception:
            pass
    
    # Get all words ordered by frequency (descending)
    cursor.execute('''
        SELECT id, word, frequency 
        FROM words 
        ORDER BY frequency DESC
    ''')
    all_words = cursor.fetchall()
    
    print(f"Toplam kelime sayısı: {len(all_words)}")
    
    # Calculate number of packages
    total_packages = (len(all_words) + PACKAGE_SIZE - 1) // PACKAGE_SIZE
    print(f"Oluşturulacak paket sayısı: {total_packages}")
    
    # Clear existing data
    cursor.execute('DELETE FROM package_words')
    cursor.execute('DELETE FROM learning_packages')
    
    # Create packages and assign words
    package_count = 0
    
    for i in range(0, len(all_words), PACKAGE_SIZE):
        package_number = (i // PACKAGE_SIZE) + 1
        package_words = all_words[i:i + PACKAGE_SIZE]
        
        min_freq = package_words[-1][2]  # Last word in package has lowest freq
        max_freq = package_words[0][2]   # First word has highest freq
        
        # Create package
        package_name = f"Level {package_number}: {package_words[0][1]} - {package_words[-1][1]}"
        cursor.execute('''
            INSERT INTO learning_packages (package_number, package_name, word_count, min_frequency, max_frequency)
            VALUES (?, ?, ?, ?, ?)
        ''', (package_number, package_name, len(package_words), min_freq, max_freq))
        
        package_id = cursor.lastrowid
        
        # Add words to package
        for rank, (word_id, word, freq) in enumerate(package_words, start=1):
            try:
                cursor.execute('''
                    INSERT INTO package_words (package_id, word_id, word_rank)
                    VALUES (?, ?, ?)
                ''', (package_id, word_id, rank))
            except sqlite3.IntegrityError:
                pass  # Word already in package
        
        package_count += 1
        print(f"✅ Paket {package_number} oluşturuldu: {len(package_words)} kelime ({min_freq}-{max_freq} frekans)")
    
    conn.commit()
    
    # Print summary
    print(f"\n📊 Özet:")
    print(f"   - Toplam paket: {package_count}")
    print(f"   - Toplam kelime: {len(all_words)}")
    
    # Show package info
    cursor.execute('''
        SELECT package_number, package_name, word_count, min_frequency, max_frequency
        FROM learning_packages
        ORDER BY package_number
    ''')
    
    print(f"\n📚 Learning Pathways:")
    for row in cursor.fetchall():
        print(f"   Level {row[0]}: {row[2]} kelime | Frekans: {row[4]}-{row[3]}")
    
    conn.close()
    return package_count

def get_user_package_progress(user_id: int, package_id: int) -> dict:
    """Get user's progress in a specific package"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Count total words in package
    cursor.execute('''
        SELECT COUNT(*) FROM package_words WHERE package_id = ?
    ''', (package_id,))
    total_words = cursor.fetchone()[0]
    
    # Count known words
    cursor.execute('''
        SELECT COUNT(DISTINCT uw.word_id)
        FROM user_words uw
        JOIN package_words pw ON uw.word_id = pw.word_id
        WHERE uw.user_id = ? AND uw.known = 1 AND pw.package_id = ?
    ''', (user_id, package_id))
    known_words = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        'total': total_words,
        'known': known_words,
        'unknown': total_words - known_words,
        'percentage': round((known_words / total_words * 100) if total_words > 0 else 0, 1)
    }

def reset_learning_pathways():
    """Clear all learning pathway data"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM package_words')
    cursor.execute('DELETE FROM learning_packages')
    conn.commit()
    conn.close()
    print("🗑️ Learning pathways cleared.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        reset_learning_pathways()
    else:
        create_learning_pathways()
