import sqlite3
from typing import List, Dict, Optional, Any, Set
try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

DATABASE_PATH = 'learning.db'

class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                email TEXT,
                google_id TEXT,
                picture TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Main vocabulary database
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                frequency INTEGER DEFAULT 1,
                definition TEXT,
                pronunciation TEXT
            )
        ''')
        
        # User's word knowledge
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                known BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (word_id) REFERENCES words(id),
                UNIQUE(user_id, word_id)
            )
        ''')
        
        # Videos processed
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                title TEXT,
                description TEXT,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                word_count INTEGER DEFAULT 0,
                transcript TEXT,
                video_url TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migration: Add title and description columns if they don't exist
        try:
            cursor.execute('SELECT title FROM videos LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE videos ADD COLUMN title TEXT')
            cursor.execute('ALTER TABLE videos ADD COLUMN description TEXT')
            cursor.execute('ALTER TABLE videos ADD COLUMN added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        
        # Migration: Explicitly check for added_date (fix for existing dbs where title exists but added_date does not)
        try:
            cursor.execute('SELECT added_date FROM videos LIMIT 1')
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            cursor.execute('ALTER TABLE videos ADD COLUMN added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        
        # Watch Party Rooms
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watch_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_name TEXT NOT NULL,
                creator_id INTEGER NOT NULL,
                video_url TEXT,
                video_title TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (creator_id) REFERENCES users(id)
            )
        ''')
        
        # Room Members
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_screen_sharing BOOLEAN DEFAULT 0,
                FOREIGN KEY (room_id) REFERENCES watch_rooms(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(room_id, user_id)
            )
        ''')
        
        # Chat Messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (room_id) REFERENCES watch_rooms(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Migration: Check if transcript column exists in videos table (for existing dbs)
        try:
            cursor.execute('SELECT transcript FROM videos LIMIT 1')
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            cursor.execute('ALTER TABLE videos ADD COLUMN transcript TEXT')
        
        # Migration: Check if video_url column exists in videos table
        try:
            cursor.execute('SELECT video_url FROM videos LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE videos ADD COLUMN video_url TEXT')

        # Video-Word relationship table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                FOREIGN KEY (video_id) REFERENCES videos(id),
                FOREIGN KEY (word_id) REFERENCES words(id),
                UNIQUE(video_id, word_id)
            )
        ''')
        
        # Migration: Check if password_hash column exists in users table
        try:
            cursor.execute('SELECT password_hash FROM users LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
            
        # Migration: Check if definition column exists in words table
        try:
            cursor.execute('SELECT definition FROM words LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE words ADD COLUMN definition TEXT')
            cursor.execute('ALTER TABLE words ADD COLUMN pronunciation TEXT')
            
        # Migration: Check if added_date column exists in words table
        try:
            cursor.execute('SELECT added_date FROM words LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE words ADD COLUMN added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        # Migration: Check if email column exists in users table
        try:
            cursor.execute('SELECT email FROM users LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE users ADD COLUMN email TEXT')
            cursor.execute('ALTER TABLE users ADD COLUMN google_id TEXT')
            cursor.execute('ALTER TABLE users ADD COLUMN picture TEXT')

        # Custom Series table for user-added series/movies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                icon TEXT DEFAULT '🎬',
                gradient TEXT DEFAULT 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                db_folder_path TEXT NOT NULL,
                source_url TEXT,
                total_episodes INTEGER DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')

        conn.commit()
        conn.close()
    
    def register_user(self, username: str, password_hash: str) -> tuple[bool, Optional[int], str]:
        """Register a new user (or update legacy user)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check if user exists
            cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
            existing = cursor.fetchone()
            
            if existing:
                if existing['password_hash'] is None:
                    # Update legacy user with password
                    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, existing['id']))
                    conn.commit()
                    return True, existing['id'], "Eski hesap şifre ile güncellendi"
                else:
                    return False, None, "Bu kullanıcı adı zaten alınmış"
            
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
            conn.commit()
            user_id = cursor.lastrowid
            return True, user_id, "Kullanıcı oluşturuldu"
        except sqlite3.IntegrityError:
            return False, None, "Kayıt hatası"
        finally:
            conn.close()

    def login_with_google(self, email: str, google_id: str, username: str, picture: str) -> tuple[Optional[int], str]:
        """Login or register with Google"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check by google_id
            cursor.execute('SELECT id, username FROM users WHERE google_id = ?', (google_id,))
            user = cursor.fetchone()
            
            if user:
                return user['id'], user['username']
            
            # Check by email (if exists, link account)
            cursor.execute('SELECT id, username FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()
            
            if user:
                cursor.execute('UPDATE users SET google_id = ?, picture = ? WHERE id = ?', (google_id, picture, user['id']))
                conn.commit()
                return user['id'], user['username']
            
            # Create new user
            # Ensure username is unique
            base_username = username.replace(' ', '').lower()
            final_username = base_username
            counter = 1
            while True:
                cursor.execute('SELECT id FROM users WHERE username = ?', (final_username,))
                if not cursor.fetchone():
                    break
                final_username = f"{base_username}{counter}"
                counter += 1
            
            cursor.execute('''
                INSERT INTO users (username, email, google_id, picture)
                VALUES (?, ?, ?, ?)
            ''', (final_username, email, google_id, picture))
            conn.commit()
            return cursor.lastrowid, final_username
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user details by username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def get_word(self, word_id: int) -> Optional[Dict[str, Any]]:
        """Get word details by id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM words WHERE id = ?', (word_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def get_word_by_text(self, word: str) -> Optional[Dict[str, Any]]:
        """Get word details by text"""
        conn = self.get_connection()
        cursor = conn.cursor()
        word = word.lower().strip()
        cursor.execute('SELECT * FROM words WHERE word = ?', (word,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def get_or_add_word(self, word: str) -> Optional[int]:
        """Get word id or add if doesn't exist, return word_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        word = word.lower().strip()
        
        cursor.execute('SELECT id FROM words WHERE word = ?', (word,))
        result = cursor.fetchone()
        
        if result:
            # Update frequency
            cursor.execute('UPDATE words SET frequency = frequency + 1 WHERE id = ?', (result[0],))
            conn.commit()
            conn.close()
            return result[0]
        else:
            # Add new word
            cursor.execute('INSERT INTO words (word) VALUES (?)', (word,))
            conn.commit()
            word_id = cursor.lastrowid
            conn.close()
            return word_id
    
    def add_user_word(self, user_id: int, word_id: int, known: bool = False):
        """Add word to user's vocabulary"""
        conn = self.get_connection()
        cursor = conn.cursor()
        known_int = 1 if known else 0
        try:
            cursor.execute('''
                INSERT INTO user_words (user_id, word_id, known)
                VALUES (?, ?, ?)
            ''', (user_id, word_id, known_int))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Already exists
        finally:
            conn.close()
    
    def update_user_word_status(self, user_id: int, word_id: int, known: bool):
        """Update if user knows the word"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Ensure integer for SQLite boolean
        known_int = 1 if known else 0
        
        # Önce güncellemeyi dene
        cursor.execute('''
            UPDATE user_words SET known = ?, last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ? AND word_id = ?
        ''', (known_int, user_id, word_id))
        
        # Eğer güncellenen satır yoksa (kayıt yoksa), yeni ekle
        if cursor.rowcount == 0:
            try:
                cursor.execute('''
                    INSERT INTO user_words (user_id, word_id, known)
                    VALUES (?, ?, ?)
                ''', (user_id, word_id, known_int))
            except sqlite3.IntegrityError:
                # Nadir durum: Tam bu arada eklendiyse tekrar güncellemeyi dene
                cursor.execute('''
                    UPDATE user_words SET known = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND word_id = ?
                ''', (known_int, user_id, word_id))
                
        conn.commit()
        conn.close()
    
    def get_user_words(self, user_id: int, known_only: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get all words for user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if known_only is None:
            cursor.execute('''
                SELECT w.id, w.word, 
                       CASE WHEN uw.known IS NULL THEN 0 ELSE uw.known END as known,
                       w.frequency, w.definition, w.pronunciation
                FROM words w
                LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
                ORDER BY w.frequency DESC
            ''', (user_id,))
        elif known_only:
            cursor.execute('''
                SELECT w.id, w.word, uw.known, w.frequency, w.definition, w.pronunciation
                FROM user_words uw
                JOIN words w ON uw.word_id = w.id
                WHERE uw.user_id = ? AND uw.known = 1
                ORDER BY w.frequency DESC
            ''', (user_id,))
        else:
            # known_only is False (Unknown words)
            cursor.execute('''
                SELECT w.id, w.word, 
                       CASE WHEN uw.known IS NULL THEN 0 ELSE uw.known END as known,
                       w.frequency, w.definition, w.pronunciation
                FROM words w
                LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
                WHERE (uw.known = 0 OR uw.known IS NULL)
                ORDER BY w.frequency DESC
            ''', (user_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_all_words(self) -> List[Dict[str, Any]]:
        """Get all words from main database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, word, frequency FROM words ORDER BY frequency DESC')
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get learning statistics for user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM words')
        total_result = cursor.fetchone()
        total = total_result[0] if total_result else 0
        
        cursor.execute('SELECT COUNT(*) as known FROM user_words WHERE user_id = ? AND known = 1', (user_id,))
        known_result = cursor.fetchone()
        known = known_result[0] if known_result else 0
        
        # Calculate Level Stats
        cursor.execute('SELECT COUNT(*) FROM learning_packages')
        total_levels = cursor.fetchone()[0]
        
        current_level = 1
        level_progress = 0
        level_name = "Level 1"
        
        if total_levels > 0:
            # Get all packages
            cursor.execute('SELECT id, package_number, package_name, word_count FROM learning_packages ORDER BY package_number')
            packages = cursor.fetchall()
            
            # Get known counts for all packages
            cursor.execute('''
                SELECT pw.package_id, COUNT(DISTINCT uw.word_id)
                FROM package_words pw
                JOIN user_words uw ON pw.word_id = uw.word_id
                WHERE uw.user_id = ? AND uw.known = 1
                GROUP BY pw.package_id
            ''', (user_id,))
            known_map = dict(cursor.fetchall())
            
            for pkg in packages:
                pkg_id = pkg['id']
                word_count = pkg['word_count']
                known_count = known_map.get(pkg_id, 0)
                
                pct = (known_count / word_count * 100) if word_count > 0 else 0
                
                if pct < 98: # Not completed (using 98% threshold)
                    current_level = pkg['package_number']
                    level_progress = round(pct, 1)
                    level_name = pkg['package_name']
                    break
            else:
                # All levels completed
                if packages:
                    current_level = packages[-1]['package_number']
                    level_progress = 100
                    level_name = packages[-1]['package_name'] + " (Tamamlandı)"
        
        conn.close()
        
        return {
            'total': total,
            'known': known,
            'unknown': total - known,
            'percentage': round((known / total * 100) if total > 0 else 0, 2),
            'current_level': current_level,
            'level_progress': level_progress,
            'level_name': level_name,
            'total_levels': total_levels
        }
    
    def add_video_record(self, filename: str, word_count: int, transcript: str = "", video_url: str = "", title: Optional[str] = None, description: Optional[str] = None) -> Optional[int]:
        """Record processed video and return its ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check if exists to update or insert
            cursor.execute('SELECT id FROM videos WHERE filename = ?', (filename,))
            existing = cursor.fetchone()
            
            if existing:
                video_id = existing['id']
                cursor.execute('''
                    UPDATE videos 
                    SET word_count = ?, transcript = ?, video_url = ?, title = COALESCE(?, title), description = COALESCE(?, description), processed_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (word_count, transcript, video_url, title, description, video_id))
            else:
                cursor.execute('''
                    INSERT INTO videos (filename, word_count, transcript, video_url, title, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (filename, word_count, transcript, video_url, title, description))
                video_id = cursor.lastrowid
                
            conn.commit()
            return video_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()
            
    def add_video_word(self, video_id: int, word_id: int):
        """Link a word to a video"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO video_words (video_id, word_id) VALUES (?, ?)', (video_id, word_id))
            conn.commit()
        finally:
            conn.close()
    
    def get_videos(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all processed videos with optional user stats"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, filename, title, description, video_url, processed_date, added_date, word_count, transcript FROM videos ORDER BY processed_date DESC')
        results = [dict(row) for row in cursor.fetchall()]
        
        if user_id:
            for video in results:
                # User stats (Known/Unknown count)
                cursor.execute('''
                    SELECT 
                        COUNT(CASE WHEN uw.known = 1 THEN 1 END) as known,
                        COUNT(CASE WHEN uw.known = 0 OR uw.known IS NULL THEN 1 END) as unknown
                    FROM video_words vw
                    LEFT JOIN user_words uw ON vw.word_id = uw.word_id AND uw.user_id = ?
                    WHERE vw.video_id = ?
                ''', (user_id, video['id']))
                stats = cursor.fetchone()
                video['known_count'] = stats['known']
                video['unknown_count'] = stats['unknown']
                
                # Level stats (Distribution of words by package/level)
                cursor.execute('''
                    SELECT lp.package_name, COUNT(vw.word_id) as count
                    FROM video_words vw
                    JOIN package_words pw ON vw.word_id = pw.word_id
                    JOIN learning_packages lp ON pw.package_id = lp.id
                    WHERE vw.video_id = ?
                    GROUP BY lp.package_number
                    ORDER BY lp.package_number
                ''', (video['id'],))
                video['level_stats'] = {row['package_name']: row['count'] for row in cursor.fetchall()}
        
        conn.close()
        return results
    
    def delete_video(self, video_id: int) -> bool:
        """Delete a video and its word associations"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM video_words WHERE video_id = ?', (video_id,))
            cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting video: {e}")
            return False
        finally:
            conn.close()
    
    def delete_videos_by_criteria(self, title_like: Optional[str] = None, max_word_count: Optional[int] = None) -> int:
        """Delete videos matching criteria (useful for cleanup)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Build WHERE clause
            conditions: List[str] = []
            params: List[Any] = []
            
            if title_like:
                conditions.append("title LIKE ?")
                params.append(title_like)
            
            if max_word_count is not None:
                conditions.append("word_count < ?")
                params.append(max_word_count)
            
            if not conditions:
                return 0
                
            where_clause = " AND ".join(conditions)
            
            # Count first
            cursor.execute(f"SELECT COUNT(*) FROM videos WHERE {where_clause}", params)
            count = cursor.fetchone()[0]
            
            if count > 0:
                # Delete video_words first (dependencies)
                cursor.execute(f"DELETE FROM video_words WHERE video_id IN (SELECT id FROM videos WHERE {where_clause})", params)
                # Delete videos
                cursor.execute(f"DELETE FROM videos WHERE {where_clause}", params)
                conn.commit()
            
            return count
        except Exception as e:
            print(f"Error cleaning up videos: {e}")
            return 0
        finally:
            conn.close()

    def get_video_words_details(self, video_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get detailed words for a video with user status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.id, w.word, w.frequency, w.definition, w.pronunciation,
                   COALESCE(lp.package_name, 'Diğer') as level,
                   CASE WHEN uw.known = 1 THEN 1 ELSE 0 END as known
            FROM video_words vw
            JOIN words w ON vw.word_id = w.id
            LEFT JOIN package_words pw ON w.id = pw.word_id
            LEFT JOIN learning_packages lp ON pw.package_id = lp.id
            LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
            WHERE vw.video_id = ?
            ORDER BY w.frequency DESC
        ''', (user_id, video_id))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_processed_filenames(self) -> Set[str]:
        """Get set of processed video filenames"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT filename FROM videos')
        results = {row['filename'] for row in cursor.fetchall()}
        conn.close()
        return results

    # ===== WORD FREQUENCY METHODS =====

    def init_word_frequency_table(self):
        """Initialize word frequency table for video transcripts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_frequencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                UNIQUE(video_id, word)
            )
        ''')
        
        conn.commit()
        conn.close()

    def add_word_frequencies(self, video_id: int, word_counts: Dict[str, int]) -> bool:
        """Add word frequencies for a video (word: count pairs)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Remove existing frequencies for this video
            cursor.execute('DELETE FROM word_frequencies WHERE video_id = ?', (video_id,))
            
            # Insert new frequencies
            for word, frequency in word_counts.items():
                try:
                    cursor.execute('''
                        INSERT INTO word_frequencies (video_id, word, frequency)
                        VALUES (?, ?, ?)
                    ''', (video_id, word.lower(), frequency))
                except sqlite3.IntegrityError:
                    # Update if already exists
                    cursor.execute('''
                        UPDATE word_frequencies SET frequency = ?
                        WHERE video_id = ? AND word = ?
                    ''', (frequency, video_id, word.lower()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding word frequencies: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_video_word_frequencies(self, video_id: int) -> List[Dict[str, Any]]:
        """Get all word frequencies for a video"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT word, frequency
            FROM word_frequencies
            WHERE video_id = ?
            ORDER BY frequency DESC
        ''', (video_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_word_frequencies(self) -> List[Dict[str, Any]]:
        """Get all word frequencies from all videos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT wf.video_id, v.filename, wf.word, wf.frequency
            FROM word_frequencies wf
            JOIN videos v ON wf.video_id = v.id
            ORDER BY v.filename, wf.frequency DESC
        ''')
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_video_word_frequency_summary(self, video_id: int) -> Dict[str, Any]:
        """Get summary statistics for video word frequencies"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as unique_words, SUM(frequency) as total_words
            FROM word_frequencies
            WHERE video_id = ?
        ''', (video_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'video_id': video_id,
            'unique_words': result['unique_words'] or 0,
            'total_words': result['total_words'] or 0
        }

    def delete_word_frequencies(self, video_id: int) -> bool:
        """Delete all word frequencies for a video"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM word_frequencies WHERE video_id = ?', (video_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting word frequencies: {e}")
            return False
        finally:
            conn.close()

    # ===== WATCH PARTY METHODS =====
    
    def cleanup_stale_sessions(self):
        """Deactivates all rooms and removes all members. To be used on startup."""
        conn = self.get_connection()
        cursor = conn.cursor()
        print("Cleaning up stale room sessions on startup...")
        cursor.execute('DELETE FROM room_members')
        cursor.execute('UPDATE watch_rooms SET is_active = 0')
        conn.commit()
        conn.close()
        print("Cleanup complete.")

    def create_room(self, room_name: str, creator_id: int, video_url: str = "", video_title: str = "") -> Optional[int]:
        """Create a new watch room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO watch_rooms (room_name, creator_id, video_url, video_title)
                VALUES (?, ?, ?, ?)
            ''', (room_name, creator_id, video_url, video_title))
            conn.commit()
            room_id = cursor.lastrowid
            if room_id is not None:
                # Add creator to room
                self.add_member_to_room(room_id, creator_id)
            return room_id
        finally:
            conn.close()
    
    def get_active_rooms(self) -> List[Dict[str, Any]]:
        """Get all active watch rooms"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.id, r.room_name, r.creator_id, r.video_url, r.video_title, 
                   r.created_date, COUNT(m.id) as member_count, u.username as creator_name
            FROM watch_rooms r
            LEFT JOIN room_members m ON r.id = m.room_id
            LEFT JOIN users u ON r.creator_id = u.id
            WHERE r.is_active = 1
            GROUP BY r.id
            ORDER BY r.created_date DESC
        ''')
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_room(self, room_id: int) -> Optional[Dict[str, Any]]:
        """Get room details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.id, r.room_name, r.creator_id, r.video_url, r.video_title, 
                   r.created_date, r.is_active, u.username as creator_name
            FROM watch_rooms r
            LEFT JOIN users u ON r.creator_id = u.id
            WHERE r.id = ?
        ''', (room_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def get_room_members(self, room_id: int) -> List[Dict[str, Any]]:
        """Get members of a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.username, rm.joined_date, rm.is_screen_sharing
            FROM room_members rm
            JOIN users u ON rm.user_id = u.id
            WHERE rm.room_id = ?
            ORDER BY rm.joined_date ASC
        ''', (room_id,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def add_member_to_room(self, room_id: int, user_id: int) -> bool:
        """Add user to room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO room_members (room_id, user_id)
                VALUES (?, ?)
            ''', (room_id, user_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def remove_member_from_room(self, room_id: int, user_id: int) -> bool:
        """Remove user from room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM room_members WHERE room_id = ? AND user_id = ?', (room_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def get_video_stats_for_room(self, room_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get vocabulary stats for the video in the room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get video_url from room
        cursor.execute('SELECT video_url FROM watch_rooms WHERE id = ?', (room_id,))
        room = cursor.fetchone()
        if not room or not room['video_url']:
            conn.close()
            return None
            
        # Find video by URL
        cursor.execute('SELECT id FROM videos WHERE video_url = ?', (room['video_url'],))
        video = cursor.fetchone()
        
        if not video:
            conn.close()
            return None
            
        video_id = video['id']
        
        # Calculate stats
        cursor.execute('SELECT COUNT(*) FROM video_words WHERE video_id = ?', (video_id,))
        total_words = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM video_words vw
            JOIN user_words uw ON vw.word_id = uw.word_id
            WHERE vw.video_id = ? AND uw.user_id = ? AND uw.known = 1
        ''', (video_id, user_id))
        known_words = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total': total_words,
            'known': known_words,
            'unknown': total_words - known_words,
            'percentage': round((known_words / total_words * 100) if total_words > 0 else 0, 1)
        }

    def get_room_video_words(self, room_id: int, user_id: int, status: str = 'all') -> List[Dict[str, Any]]:
        """Get words for the room's video filtered by status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT video_url FROM watch_rooms WHERE id = ?', (room_id,))
        room = cursor.fetchone()
        if not room or not room['video_url']:
            conn.close()
            return []
            
        cursor.execute('SELECT id FROM videos WHERE video_url = ?', (room['video_url'],))
        video = cursor.fetchone()
        
        if not video:
            conn.close()
            return []
            
        query = '''
            SELECT w.id, w.word, w.frequency, 
                   CASE WHEN uw.known IS NULL THEN 0 ELSE uw.known END as known,
                   w.definition, w.pronunciation
            FROM video_words vw
            JOIN words w ON vw.word_id = w.id
            LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
            WHERE vw.video_id = ?
        '''
        
        if status == 'known':
            query += ' AND uw.known = 1'
        elif status == 'unknown':
            query += ' AND (uw.known = 0 OR uw.known IS NULL)'
            
        query += ' ORDER BY w.frequency DESC'
        
        cursor.execute(query, (user_id, video['id']))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def add_chat_message(self, room_id: int, user_id: int, message: str) -> Optional[int]:
        """Add chat message"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO chat_messages (room_id, user_id, message)
                VALUES (?, ?, ?)
            ''', (room_id, user_id, message))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_room_messages(self, room_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat messages for a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.id, m.user_id, u.username, m.message, m.created_date
            FROM chat_messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.room_id = ?
            ORDER BY m.created_date DESC
            LIMIT ?
        ''', (room_id, limit))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return list(reversed(results))  # Return in ascending order
    
    def set_screen_sharing(self, room_id: int, user_id: int, is_sharing: bool) -> bool:
        """Update screen sharing status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE room_members SET is_screen_sharing = ?
            WHERE room_id = ? AND user_id = ?
        ''', (is_sharing, room_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def get_word_definition(self, word: str) -> tuple[Optional[str], Optional[str]]:
        """Fetch word definition (translation) using Google Translate"""
        if not GoogleTranslator:
            return None, None
            
        try:
            # Translate English to Turkish
            translator = GoogleTranslator(source='en', target='tr')
            translation = translator.translate(word)
            return translation, None
        except Exception as e:
            print(f"Translation error for {word}: {e}")
            return None, None

    def update_word_definition(self, word_id: int, definition: str, pronunciation: str = None):
        """Update word definition in database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE words SET definition = ?, pronunciation = ? WHERE id = ?', 
                      (definition, pronunciation, word_id))
        conn.commit()
        conn.close()

    def get_words_without_definition(self, limit: int = 100, package_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get words that don't have definitions yet"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if package_id:
            # Get words from a specific package without definitions
            cursor.execute('''
                SELECT w.id, w.word, w.frequency
                FROM package_words pw
                JOIN words w ON pw.word_id = w.id
                WHERE pw.package_id = ? AND (w.definition IS NULL OR w.definition = '')
                ORDER BY w.frequency DESC
                LIMIT ?
            ''', (package_id, limit))
        else:
            # Get all words without definitions (prioritize high frequency)
            cursor.execute('''
                SELECT w.id, w.word, w.frequency
                FROM package_words pw
                JOIN words w ON pw.word_id = w.id
                WHERE w.definition IS NULL OR w.definition = ''
                ORDER BY w.frequency DESC
                LIMIT ?
            ''', (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def bulk_update_definitions(self, definitions: List[Dict[str, Any]]) -> int:
        """Bulk update word definitions. Each dict should have: word_id, definition, pronunciation (optional)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        updated = 0
        
        try:
            for item in definitions:
                word_id = item.get('word_id')
                definition = item.get('definition', '')
                pronunciation = item.get('pronunciation', '')
                
                if word_id and definition:
                    cursor.execute('''
                        UPDATE words SET definition = ?, pronunciation = ?
                        WHERE id = ?
                    ''', (definition, pronunciation, word_id))
                    updated += cursor.rowcount
            
            conn.commit()
        except Exception as e:
            print(f"Error in bulk update: {e}")
            conn.rollback()
        finally:
            conn.close()
        
        return updated

    def get_definition_stats(self) -> Dict[str, Any]:
        """Get statistics about word definitions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total words in packages
        cursor.execute('SELECT COUNT(DISTINCT word_id) FROM package_words')
        total_words = cursor.fetchone()[0] or 0
        
        # Words with definitions
        cursor.execute('''
            SELECT COUNT(DISTINCT pw.word_id)
            FROM package_words pw
            JOIN words w ON pw.word_id = w.id
            WHERE w.definition IS NOT NULL AND w.definition != ''
        ''')
        words_with_def = cursor.fetchone()[0] or 0
        
        # Words without definitions
        words_without_def = total_words - words_with_def
        
        conn.close()
        
        return {
            'total_words': total_words,
            'words_with_definition': words_with_def,
            'words_without_definition': words_without_def,
            'percentage': round((words_with_def / total_words * 100) if total_words > 0 else 0, 1)
        }
    
    def close_room(self, room_id: int) -> bool:
        """Close a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE watch_rooms SET is_active = 0 WHERE id = ?', (room_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    
    def update_room_video(self, room_id: int, video_url: str, video_title: str) -> bool:
        """Update video for room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE watch_rooms SET video_url = ?, video_title = ?
            WHERE id = ?
        ''', (video_url, video_title, room_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    # ===== LEARNING PATHWAY METHODS =====

    def init_learning_packages(self):
        """Initialize learning packages tables"""
        conn = self.get_connection()
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
        
        conn.commit()
        conn.close()

    def get_learning_packages(self) -> List[Dict[str, Any]]:
        """Get all learning packages"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, package_number, package_name, word_count, min_frequency, max_frequency
            FROM learning_packages
            ORDER BY package_number
        ''')
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def has_learning_packages(self) -> bool:
        """Check if learning packages exist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM learning_packages')
            result = cursor.fetchone()
            return result[0] > 0 if result else False
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()

    def generate_learning_packages(self, package_size: int = 500) -> int:
        """Generate learning packages from words table based on frequency"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Ensure tables exist
            self.init_learning_packages()
            
            # Sync frequencies from word_frequency table if it exists
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='word_frequency'")
                if cursor.fetchone():
                    print("🔄 Syncing word frequencies from word_frequency table...")
                    cursor.execute("""
                        UPDATE words 
                        SET frequency = (SELECT frequency FROM word_frequency WHERE word_frequency.word = words.word) 
                        WHERE EXISTS (SELECT 1 FROM word_frequency WHERE word_frequency.word = words.word)
                    """)
                    conn.commit()
            except Exception as e:
                print(f"Warning: Could not sync frequencies: {e}")

            # Clear existing data
            cursor.execute('DELETE FROM package_words')
            cursor.execute('DELETE FROM learning_packages')
            
            # Get all words ordered by frequency
            cursor.execute('SELECT id, word, frequency FROM words ORDER BY frequency DESC')
            all_words = cursor.fetchall()
            
            created_count = 0
            
            for i in range(0, len(all_words), package_size):
                package_number = (i // package_size) + 1
                package_words = all_words[i:i + package_size]
                
                if not package_words:
                    continue
                    
                min_freq = package_words[-1]['frequency']
                max_freq = package_words[0]['frequency']
                
                first_word = package_words[0]['word']
                last_word = package_words[-1]['word']
                package_name = f"Level {package_number}: {first_word} - {last_word}"
                
                cursor.execute('''
                    INSERT INTO learning_packages (package_number, package_name, word_count, min_frequency, max_frequency)
                    VALUES (?, ?, ?, ?, ?)
                ''', (package_number, package_name, len(package_words), min_freq, max_freq))
                
                package_id = cursor.lastrowid
                
                # Batch insert words for this package
                batch_values = [(package_id, row['id'], rank) for rank, row in enumerate(package_words, start=1)]
                
                cursor.executemany('''
                    INSERT INTO package_words (package_id, word_id, word_rank)
                    VALUES (?, ?, ?)
                ''', batch_values)
                
                created_count += 1
            
            conn.commit()
            return created_count
        except Exception as e:
            print(f"Error generating packages: {e}")
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_package_words(self, package_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get words for a specific package"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT w.id, w.word, w.frequency, pw.word_rank,
                       CASE WHEN uw.known IS NULL THEN 0 ELSE uw.known END as known,
                       w.definition, w.pronunciation
                FROM package_words pw
                JOIN words w ON pw.word_id = w.id
                LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
                WHERE pw.package_id = ?
                ORDER BY pw.word_rank
            ''', (user_id, package_id))
        else:
            cursor.execute('''
                SELECT w.id, w.word, w.frequency, pw.word_rank,
                       0 as known, w.definition, w.pronunciation
                FROM package_words pw
                JOIN words w ON pw.word_id = w.id
                WHERE pw.package_id = ?
                ORDER BY pw.word_rank
            ''', (package_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_package_progress(self, package_id: int, user_id: int) -> Dict[str, Any]:
        """Get user's progress in a specific package"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Count total words in package
        cursor.execute('SELECT COUNT(*) FROM package_words WHERE package_id = ?', (package_id,))
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

    def get_all_packages_progress(self, user_id: int) -> List[Dict[str, Any]]:
        """Get progress for all packages"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, package_number, package_name, word_count
            FROM learning_packages
            ORDER BY package_number
        ''')
        packages = [dict(row) for row in cursor.fetchall()]
        
        # Optimized query to get all progress at once
        cursor.execute('''
            SELECT pw.package_id, COUNT(DISTINCT uw.word_id)
            FROM package_words pw
            JOIN user_words uw ON pw.word_id = uw.word_id
            WHERE uw.user_id = ? AND uw.known = 1
            GROUP BY pw.package_id
        ''', (user_id,))
        known_map = dict(cursor.fetchall())
        
        for pkg in packages:
            pkg_id = pkg['id']
            known = known_map.get(pkg_id, 0)
            
            pkg['known_words'] = known
            pkg['unknown_words'] = pkg['word_count'] - known
            pkg['progress_percentage'] = round((known / pkg['word_count'] * 100) if pkg['word_count'] > 0 else 0, 1)
        
        conn.close()
        return packages

    # ===== FLASHCARD SYSTEM METHODS =====

    def init_flashcard_system(self):
        """Initialize flashcard tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Flashcard sessions - track study sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flashcard_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_type TEXT NOT NULL, -- 'level', 'video', 'all', 'random'
                target_id INTEGER, -- package_id or video_id depending on type
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                total_cards INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Flashcard progress - track individual card progress within session
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flashcard_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending', -- 'pending', 'correct', 'incorrect', 'skipped'
                attempts INTEGER DEFAULT 0,
                first_answer_time TIMESTAMP,
                last_answer_time TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES flashcard_sessions(id),
                FOREIGN KEY (word_id) REFERENCES words(id),
                UNIQUE(session_id, word_id)
            )
        ''')
        
        # Problem words - track words user struggles with
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flashcard_problem_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                times_incorrect INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (word_id) REFERENCES words(id),
                UNIQUE(user_id, word_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def create_flashcard_session(self, user_id: int, session_type: str, target_id: Optional[int] = None) -> Optional[int]:
        """Start a new flashcard session and return session_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get words based on session type
            words = []
            if session_type == 'level' and target_id:
                # Get words from a learning package
                cursor.execute('''
                    SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency
                    FROM package_words pw
                    JOIN words w ON pw.word_id = w.id
                    WHERE pw.package_id = ? AND w.id NOT IN (
                        SELECT word_id FROM user_words WHERE user_id = ? AND known = 1
                    )
                    ORDER BY pw.word_rank
                ''', (target_id, user_id))
                words = cursor.fetchall()
            elif session_type == 'video' and target_id:
                # Get words from a video
                cursor.execute('''
                    SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency
                    FROM video_words vw
                    JOIN words w ON vw.word_id = w.id
                    WHERE vw.video_id = ? AND w.id NOT IN (
                        SELECT word_id FROM user_words WHERE user_id = ? AND known = 1
                    )
                    ORDER BY w.frequency DESC
                ''', (target_id, user_id))
                words = cursor.fetchall()
            elif session_type == 'all':
                # Get all unknown words
                cursor.execute('''
                    SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency
                    FROM words w
                    WHERE w.id NOT IN (
                        SELECT word_id FROM user_words WHERE user_id = ? AND known = 1
                    )
                    ORDER BY w.frequency DESC
                    LIMIT 100
                ''', (user_id,))
                words = cursor.fetchall()
            elif session_type == 'problem':
                # Get words user has struggled with
                cursor.execute('''
                    SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency, fp.times_incorrect
                    FROM flashcard_problem_words fp
                    JOIN words w ON fp.word_id = w.id
                    WHERE fp.user_id = ? AND w.id NOT IN (
                        SELECT word_id FROM user_words WHERE user_id = ? AND known = 1
                    )
                    ORDER BY fp.times_incorrect DESC, fp.last_seen DESC
                    LIMIT 50
                ''', (user_id, user_id))
                words = cursor.fetchall()
            elif session_type == 'random':
                # Get random unknown words
                cursor.execute('''
                    SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency
                    FROM words w
                    WHERE w.id NOT IN (
                        SELECT word_id FROM user_words WHERE user_id = ? AND known = 1
                    )
                    ORDER BY RANDOM()
                    LIMIT 50
                ''', (user_id,))
                words = cursor.fetchall()
            
            if not words:
                conn.close()
                return None
            
            # Create session
            cursor.execute('''
                INSERT INTO flashcard_sessions (user_id, session_type, target_id, total_cards)
                VALUES (?, ?, ?, ?)
            ''', (user_id, session_type, target_id, len(words)))
            session_id = cursor.lastrowid
            
            # Add all words to session progress
            for word in words:
                cursor.execute('''
                    INSERT INTO flashcard_progress (session_id, word_id, attempts)
                    VALUES (?, ?, 0)
                ''', (session_id, word['id']))
            
            conn.commit()
            return session_id
        finally:
            conn.close()

    def get_flashcard_session_words(self, session_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get all words in a flashcard session that haven't been answered correctly"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency,
                   fp.status, fp.attempts
            FROM flashcard_progress fp
            JOIN words w ON fp.word_id = w.id
            WHERE fp.session_id = ? AND fp.status != 'correct'
            ORDER BY fp.attempts ASC, fp.id ASC
        ''', (session_id,))
        
        words = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return words

    def get_flashcard_current_word(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get the next word to study in a session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get first pending/incorrect word with minimum attempts
        cursor.execute('''
            SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency,
                   fp.status, fp.attempts, fp.id as progress_id
            FROM flashcard_progress fp
            JOIN words w ON fp.word_id = w.id
            WHERE fp.session_id = ? AND fp.status != 'correct'
            ORDER BY fp.attempts ASC, fp.id ASC
            LIMIT 1
        ''', (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None

    def submit_flashcard_answer(self, session_id: int, word_id: int, is_correct: bool, user_id: int) -> Dict[str, Any]:
        """Submit an answer for a flashcard"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Update progress
        status = 'correct' if is_correct else 'incorrect'
        cursor.execute('''
            UPDATE flashcard_progress 
            SET status = ?, 
                attempts = attempts + 1,
                first_answer_time = COALESCE(first_answer_time, CURRENT_TIMESTAMP),
                last_answer_time = CURRENT_TIMESTAMP
            WHERE session_id = ? AND word_id = ?
        ''', (status, session_id, word_id))
        
        # Update session stats
        if is_correct:
            cursor.execute('''
                UPDATE flashcard_sessions 
                SET correct_answers = correct_answers + 1
                WHERE id = ?
            ''', (session_id,))
        else:
            # Track problem words
            cursor.execute('''
                INSERT OR REPLACE INTO flashcard_problem_words (user_id, word_id, times_incorrect, last_seen)
                VALUES (?, ?, 
                    COALESCE((SELECT times_incorrect + 1 FROM flashcard_problem_words WHERE user_id = ? AND word_id = ?), 1),
                    CURRENT_TIMESTAMP)
            ''', (user_id, word_id, user_id, word_id))
        
        # Get updated session stats
        cursor.execute('''
            SELECT total_cards, correct_answers FROM flashcard_sessions WHERE id = ?
        ''', (session_id,))
        session = cursor.fetchone()
        
        # Get next word
        cursor.execute('''
            SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency,
                   fp.status, fp.attempts, fp.id as progress_id
            FROM flashcard_progress fp
            JOIN words w ON fp.word_id = w.id
            WHERE fp.session_id = ? AND fp.status != 'correct'
            ORDER BY fp.attempts ASC, fp.id ASC
            LIMIT 1
        ''', (session_id,))
        next_word = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        # Calculate percentage
        total = session['total_cards'] if session else 1
        correct = session['correct_answers'] if session else 0
        percentage = round((correct / total) * 100, 1) if total > 0 else 0
        
        return {
            'success': True,
            'is_correct': is_correct,
            'next_word': dict(next_word) if next_word else None,
            'session_stats': {
                'total_cards': total,
                'correct_answers': correct,
                'remaining': total - correct,
                'percentage': percentage
            }
        }

    def get_flashcard_session_stats(self, session_id: int) -> Dict[str, Any]:
        """Get statistics for a flashcard session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT total_cards, correct_answers, started_at, completed_at
            FROM flashcard_sessions WHERE id = ?
        ''', (session_id,))
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            return {}
        
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM flashcard_progress 
            WHERE session_id = ?
            GROUP BY status
        ''', (session_id,))
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_cards': session['total_cards'],
            'correct_answers': session['correct_answers'],
            'incorrect_answers': status_counts.get('incorrect', 0),
            'skipped': status_counts.get('skipped', 0),
            'remaining': status_counts.get('pending', 0) + status_counts.get('incorrect', 0),
            'percentage': round((session['correct_answers'] / session['total_cards'] * 100) if session['total_cards'] > 0 else 0, 1),
            'started_at': session['started_at'],
            'completed_at': session['completed_at']
        }

    def complete_flashcard_session(self, session_id: int) -> bool:
        """Mark a session as completed"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE flashcard_sessions 
            SET completed_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE id = ?
        ''', (session_id,))
        
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def get_problem_words(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get words user has struggled with"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT w.id, w.word, w.definition, w.pronunciation, w.frequency,
                   fp.times_incorrect
            FROM flashcard_problem_words fp
            JOIN words w ON fp.word_id = w.id
            WHERE fp.user_id = ?
            ORDER BY fp.times_incorrect DESC
            LIMIT ?
        ''', (user_id, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    # ===== SERIES SPECIFIC METHODS (Friends & Big Bang Theory) =====

    def get_series_videos(self, series: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get videos filtered by series (friends or bigbang)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT id, filename, title, description, word_count, transcript
            FROM videos
            WHERE filename LIKE ?
        '''
        params = []
        
        if series == 'friends':
            params.append('%Friends%')
            if season:
                query += ' AND filename LIKE ?'
                params.append(f'%Season {season}%')
            if episode:
                query += ' AND filename LIKE ?'
                params.append(f'%{season}x{episode}%')
        elif series == 'bigbang':
            params.append('%big bang%')
            if season:
                query += ' AND filename LIKE ?'
                params.append(f'%{season}x%')
            if episode:
                query += ' AND filename LIKE ?'
                params.append(f'%{season}x{episode:02d}%')
        
        query += ' ORDER BY filename'
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_series_stats(self, series: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get learning statistics for a specific series"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get videos for this series
        videos = self.get_series_videos(series)
        
        if not videos:
            return {
                'series': series,
                'total_videos': 0,
                'total_words': 0,
                'known_words': 0,
                'unknown_words': 0,
                'percentage': 0
            }
        
        video_ids = [v['id'] for v in videos]
        total_words = sum(v.get('word_count', 0) for v in videos)
        
        if user_id:
            # Count known words from this series
            placeholders = ','.join('?' * len(video_ids))
            cursor.execute(f'''
                SELECT COUNT(DISTINCT uw.word_id)
                FROM user_words uw
                JOIN video_words vw ON uw.word_id = vw.word_id
                WHERE uw.user_id = ? AND uw.known = 1 AND vw.video_id IN ({placeholders})
            ''', [user_id] + video_ids)
            known_result = cursor.fetchone()
            known_words = known_result[0] if known_result else 0
        else:
            known_words = 0
        
        conn.close()
        
        return {
            'series': series,
            'total_videos': len(videos),
            'total_words': total_words,
            'known_words': known_words,
            'unknown_words': total_words - known_words,
            'percentage': round((known_words / total_words * 100) if total_words > 0 else 0, 1)
        }

    def get_episode_flashcards(self, video_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get flashcards for a specific video/episode"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get video details
        cursor.execute('''
            SELECT id, title, filename, word_count FROM videos WHERE id = ?
        ''', (video_id,))
        video = cursor.fetchone()
        
        if not video:
            conn.close()
            return {'success': False, 'error': 'Video not found'}
        
        # Get words for this video
        if user_id:
            cursor.execute('''
                SELECT w.id, w.word, w.definition, w.pronunciation,
                       CASE WHEN uw.known = 1 THEN 1 ELSE 0 END as known
                FROM video_words vw
                JOIN words w ON vw.word_id = w.id
                LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
                WHERE vw.video_id = ?
                ORDER BY w.frequency DESC
            ''', (user_id, video_id))
        else:
            cursor.execute('''
                SELECT w.id, w.word, w.definition, w.pronunciation, 0 as known
                FROM video_words vw
                JOIN words w ON vw.word_id = w.id
                WHERE vw.video_id = ?
                ORDER BY w.frequency DESC
            ''', (video_id,))
        
        words = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Filter unknown words for flashcards
        flashcards = []
        for word in words:
            if not word.get('known', False):
                flashcards.append({
                    'id': word['id'],
                    'word': word['word'],
                    'definition': word.get('definition', ''),
                    'pronunciation': word.get('pronunciation', '')
                })
        
        return {
            'success': True,
            'video': {
                'id': video['id'],
                'title': video['title'] or video['filename'],
                'word_count': video['word_count']
            },
            'flashcards': flashcards,
            'total_cards': len(flashcards),
            'user_id': user_id
        }

    def mark_word_known(self, word_id: int, user_id: int, known: bool = True) -> bool:
        """Mark a word as known/unknown for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        known_int = 1 if known else 0
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user_words (user_id, word_id, known, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, word_id, known_int))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking word: {e}")
            return False
        finally:
            conn.close()

    # ===== CUSTOM SERIES METHODS =====

    def add_custom_series(self, series_id: str, name: str, display_name: str, 
                          db_folder_path: str, icon: str = '🎬', 
                          gradient: str = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                          source_url: str = '', created_by: Optional[int] = None) -> Optional[int]:
        """Add a new custom series"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO custom_series (series_id, name, display_name, icon, gradient, db_folder_path, source_url, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (series_id, name, display_name, icon, gradient, db_folder_path, source_url, created_by))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding custom series: {e}")
            return None
        finally:
            conn.close()

    def get_custom_series(self) -> List[Dict[str, Any]]:
        """Get all custom series"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, series_id, name, display_name, icon, gradient, db_folder_path, 
                   source_url, total_episodes, created_date
            FROM custom_series
            ORDER BY created_date DESC
        ''')
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_custom_series_by_id(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific custom series by its series_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, series_id, name, display_name, icon, gradient, db_folder_path, 
                   source_url, total_episodes, created_date
            FROM custom_series
            WHERE series_id = ?
        ''', (series_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None

    def update_custom_series_episodes(self, series_id: str, episode_count: int) -> bool:
        """Update episode count for a custom series"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE custom_series SET total_episodes = ? WHERE series_id = ?
            ''', (episode_count, series_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating custom series: {e}")
            return False
        finally:
            conn.close()

    def delete_custom_series(self, series_id: str) -> bool:
        """Delete a custom series"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM custom_series WHERE series_id = ?', (series_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting custom series: {e}")
            return False
        finally:
            conn.close()
