import sys
import os
from typing import Optional, List, Dict, Any, Tuple, Union, Set
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, continue without it

# Type checking imports - add type information for external packages
try:
    from flask import Flask, render_template, request, jsonify, send_file, Response
    from flask_cors import CORS  # type: ignore[import]
    from flask_socketio import SocketIO, emit, join_room, leave_room  # type: ignore[import]
    from werkzeug.security import generate_password_hash, check_password_hash
    import requests  # type: ignore[import]
except ImportError:
    print("Hata: Gerekli kütüphaneler (Flask vb.) bulunamadı.\nLütfen kurulumu yapın: pip install -r requirements.txt")
    sys.exit(1)

from database import Database
from speech_processor import SpeechProcessor

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Disable CSP to allow inline scripts
@app.after_request
def set_headers(response: Response) -> Response:
    """Set headers for CSP and security"""
    # Remove any CSP headers that might be restricting scripts
    response.headers.pop('Content-Security-Policy', None)
    response.headers.pop('X-Content-Security-Policy', None)
    response.headers.pop('X-WebKit-CSP', None)
    # Set permissive CSP if needed
    response.headers['Content-Security-Policy'] = "default-src *; script-src * 'unsafe-inline' 'unsafe-eval'; style-src * 'unsafe-inline'; img-src * data:; font-src * data:; connect-src *;"
    return response

# Initialize database
db = Database()
db.cleanup_stale_sessions()
db.init_learning_packages()
db.init_flashcard_system()  # Initialize flashcard tables
db.init_word_frequency_table()  # Initialize word frequency table

# Check and generate learning pathways if needed
need_regen = False
if db.has_learning_packages():
    try:
        packages = db.get_learning_packages()
        # Check if Level 1 has suspiciously low frequency (indicating data loss or bad sort)
        if packages and len(packages) > 0 and packages[0]['max_frequency'] < 10:
            print("⚠️ Detected incorrect learning packages (low frequency). Marking for regeneration...")
            need_regen = True
    except Exception:
        pass

if not db.has_learning_packages() or need_regen:
    print("🚀 Generating learning pathways (levels) from word frequency...")
    try:
        count = db.generate_learning_packages()
        print(f"✅ Generated {count} learning levels.")
    except Exception as e:
        print(f"❌ Error generating learning packages: {e}")

speech_processor = SpeechProcessor()

# Create default admin user if not exists
try:
    if not db.get_user_by_username('admin'):
        print("Creating default admin user (admin/admin)...")
        db.register_user('admin', generate_password_hash('admin'))
    else:
        print("✅ Admin user exists (admin/admin)")
except Exception as e:
    print(f"Warning: Could not create default admin user: {e}")

# Track active sessions
active_sessions: Dict[str, Dict[str, Any]] = {}
room_video_states: Dict[int, Dict[str, Any]] = {}

@app.route('/')
def index() -> str:
    """Render the main index page"""
    # Pass Google Client ID to template if available
    google_client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    return render_template('index.html', google_client_id=google_client_id)

# ===== USER MANAGEMENT =====

@app.route('/api/auth/register', methods=['POST'])
def register() -> Tuple[Response, int]:
    """Register new user"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    username: Optional[str] = data.get('username')
    password: Optional[str] = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Kullanıcı adı ve şifre gerekli'}), 400
    
    password_hash = generate_password_hash(password)
    success, user_id, message = db.register_user(username, password_hash)
    
    if success:
        return jsonify({'success': True, 'user_id': user_id, 'username': username, 'message': message}), 200
    else:
        return jsonify({'success': False, 'error': message}), 400

@app.route('/api/auth/login', methods=['POST'])
def login() -> Tuple[Response, int]:
    """Login user"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    password: Optional[str] = data.get('password')
    
    username: Optional[str] = data.get('username')
    if not username or not password:
        return jsonify({'success': False, 'error': 'Kullanıcı adı ve şifre gerekli'}), 400
    
    user = db.get_user_by_username(username)
    
    if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
        return jsonify({'success': True, 'user_id': user['id'], 'username': user['username']}), 200
    else:
        return jsonify({'success': False, 'error': 'Geçersiz kullanıcı adı veya şifre'}), 401

@app.route('/api/auth/google', methods=['POST'])
def google_auth() -> Tuple[Response, int]:
    """Handle Google Sign-In"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    token: Optional[str] = data.get('token')
    
    if not token:
        return jsonify({'success': False, 'error': 'Token gerekli'}), 400
    
    try:
        # Verify token with Google
        response = requests.get(f'https://oauth2.googleapis.com/tokeninfo?id_token={token}')
        if response.status_code != 200:
            return jsonify({'success': False, 'error': 'Geçersiz Google token'}), 401
            
        google_data = response.json()
        email: Optional[str] = google_data.get('email')
        google_id: Optional[str] = google_data.get('sub')
        name: str = google_data.get('name', email.split('@')[0]) if email else 'user'
        picture: str = google_data.get('picture', '')
        
        user_id, username = db.login_with_google(email or '', google_id or '', name, picture)
        
        return jsonify({'success': True, 'user_id': user_id, 'username': username}), 200
    except Exception as e:
        print(f"Google auth error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== WATCH ROOM MANAGEMENT =====

@app.route('/api/rooms', methods=['GET'])
def get_rooms() -> Response:
    """Get all active rooms"""
    rooms_list = db.get_active_rooms()
    return jsonify({
        'success': True,
        'rooms': rooms_list
    })

@app.route('/api/rooms', methods=['POST'])
def create_room() -> Tuple[Response, int]:
    """Create a new watch room"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    room_name: str = data.get('room_name', 'Untitled Room')
    creator_id: Optional[int] = data.get('user_id')
    video_url: str = data.get('video_url', '')
    video_title: str = data.get('video_title', 'Video')
    
    if not creator_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    room_id = db.create_room(room_name, creator_id, video_url, video_title)
    
    return jsonify({
        'success': True,
        'room_id': room_id,
        'room_name': room_name
    }), 200

@app.route('/api/rooms/<int:room_id>', methods=['GET'])
def get_room_details(room_id: int) -> Tuple[Response, int]:
    """Get room details including members and messages"""
    room = db.get_room(room_id)
    if not room:
        return jsonify({'success': False, 'error': 'Room not found'}), 404

    members = db.get_room_members(room_id)
    messages = db.get_room_messages(room_id)
    
    return jsonify({
        'success': True,
        'room': room,
        'members': members,
        'messages': messages
    }), 200

@app.route('/api/rooms/<int:room_id>/join', methods=['POST'])
def join_watch_room(room_id: int) -> Tuple[Response, int]:
    """Add user to room"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    # Try to add member
    if db.add_member_to_room(room_id, user_id):
        return jsonify({'success': True, 'message': 'Joined room'}), 200
    
    # If failed, check if already a member (treat as success for re-join)
    members = db.get_room_members(room_id)
    is_member = any(m['id'] == user_id for m in members)
    
    if is_member:
        return jsonify({'success': True, 'message': 'Rejoined room'}), 200
    
    return jsonify({'success': False, 'error': 'Could not join room'}), 400

@app.route('/api/rooms/<int:room_id>/stats', methods=['GET'])
def get_room_video_stats(room_id: int) -> Tuple[Response, int]:
    """Get vocabulary stats for the video in the room"""
    user_id_str = request.args.get('user_id')
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
        
    user_id = int(user_id_str)
    stats = db.get_video_stats_for_room(room_id, user_id)
    
    return jsonify({
        'success': True,
        'stats': stats
    }), 200

@app.route('/api/rooms/<int:room_id>/words', methods=['GET'])
def get_room_video_words(room_id: int) -> Tuple[Response, int]:
    """Get words for the video in the room"""
    user_id_str = request.args.get('user_id')
    status: str = request.args.get('status', 'all')
    
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
        
    user_id = int(user_id_str)
    words = db.get_room_video_words(room_id, user_id, status)
    return jsonify({'success': True, 'words': words}), 200


# ===== SERIES AND EPISODES ROUTES =====

@app.route('/api/series', methods=['GET'])
def get_series():
    """Get a list of all series, seasons, and episodes from the Subtitles directory."""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
    series_data = {}

    if not os.path.exists(base_dir):
        return jsonify({'success': False, 'error': 'Subtitles directory not found'}), 404

    for series_name in os.listdir(base_dir):
        series_path = os.path.join(base_dir, series_name)
        if os.path.isdir(series_path):
            series_data[series_name] = {}
            for season_name in os.listdir(series_path):
                season_path = os.path.join(series_path, season_name)
                if os.path.isdir(season_path):
                    season_number = ''.join(filter(str.isdigit, season_name))
                    if season_number:
                        season_number = int(season_number)
                        series_data[series_name][season_number] = []
                        for episode_file in os.listdir(season_path):
                            if episode_file.endswith(('.txt', '.srt', '.sub')):
                                episode_name = os.path.splitext(episode_file)[0]
                                db_path = os.path.join(season_path, episode_name + '.db')
                                series_data[series_name][season_number].append({
                                    'episode_file': episode_file,
                                    'has_db': os.path.exists(db_path)
                                })
    return jsonify({'success': True, 'series': series_data})


@app.route('/api/series/<series_name>/<int:season_number>/<path:episode_file>/words', methods=['GET'])
def get_episode_words(series_name, season_number, episode_file):
    """Get words from a subtitle file."""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
    episode_path = os.path.join(base_dir, series_name, f"Friends{season_number}", episode_file)

    if not os.path.exists(episode_path):
        return jsonify({'success': False, 'error': 'Episode file not found'}), 404

    try:
        with open(episode_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        words = speech_processor.extract_words(content)
        return jsonify({'success': True, 'words': words})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/series/<series_name>/<int:season_number>/<path:episode_file>/flashcards', methods=['GET'])
def get_episode_flashcards(series_name, season_number, episode_file):
    """Get flashcards for an episode."""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
    episode_path = os.path.join(base_dir, series_name, f"Friends{season_number}", episode_file)

    if not os.path.exists(episode_path):
        return jsonify({'success': False, 'error': 'Episode file not found'}), 404

    try:
        with open(episode_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        words = speech_processor.extract_words(content)
        
        flashcards = []
        for word in words:
            word_data = db.get_word_by_text(word)
            if word_data:
                flashcards.append(word_data)

        return jsonify({'success': True, 'flashcards': flashcards})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/rooms/<int:room_id>/leave', methods=['POST'])
def leave_watch_room(room_id: int) -> Tuple[Response, int]:
    """Remove user from room"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    success = db.remove_member_from_room(room_id, user_id)
    
    # Check if room is empty and close it
    members = db.get_room_members(room_id)
    if not members:
        db.close_room(room_id)
    
    return jsonify({
        'success': success
    }), 200

# ===== VIDEO LEARNING ROUTES (ORIGINAL FUNCTIONALITY) =====

@app.route('/api/process-videos', methods=['POST'])
def process_videos() -> Tuple[Response, int]:
    """Process all videos in directory"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    video_directory: str = data.get('directory', os.getenv('VIDEO_DIRECTORY', './videos'))
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    if not os.path.exists(video_directory):
        return jsonify({
            'success': False,
            'error': f'Video directory not found: {video_directory}'
        }), 400
    
    try:
        processed_files = db.get_processed_filenames()
        results: List[Tuple[str, Set[str], str]] = speech_processor.process_directory(video_directory, skip_filenames=processed_files)
        
        new_words_count = 0
        
        for filename, words, transcript in results:
            word_list: List[str] = list(words)
            
            for word in word_list:
                word_id = db.get_or_add_word(word)
                if word_id is not None:
                    # Get definition for new words
                    definition, pronunciation = db.get_word_definition(word)
                    if definition:
                        db.update_word_definition(word_id, definition, pronunciation or '')
                    
                    db.add_user_word(user_id, word_id)
                    new_words_count += 1
            
            video_id = db.add_video_record(filename, len(word_list), transcript)
            if video_id:
                for word in word_list:
                    word_id = db.get_or_add_word(word)
                    if word_id is not None:
                        db.add_video_word(video_id, word_id)
        
        return jsonify({
            'success': True,
            'videos_processed': len(results),
            'new_words_found': new_words_count,
            'message': f'Processed {len(results)} videos with {new_words_count} words'
        }), 200
    
    except Exception as e:
        print(f"Error processing videos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _process_video_logic(user_id: int, video_url: str) -> Tuple[Response, int]:
    """Common logic for processing video from URL"""
    try:
        # Process video from URL
        result: Tuple[Optional[str], Set[str], str] = speech_processor.process_video_from_url(video_url)
        
        if not result or not result[0]:
            return jsonify({'success': False, 'error': 'Video indirilemedi veya işlenemedi'}), 500
            
        filename = result[0]
        words_set = result[1]
        transcript = result[2]
        
        # Count word frequencies from transcript
        from collections import Counter
        import re
        
        # Clean and extract words with frequency
        cleaned_transcript = re.sub(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', ' ', transcript)
        cleaned_transcript = re.sub(r'<[^>]+>', ' ', cleaned_transcript)
        cleaned_transcript = re.sub(r'\[[^\]]*\]', ' ', cleaned_transcript)
        
        transcript_words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", cleaned_transcript.lower())
        filtered_words = [w for w in transcript_words if len(w) > 1 or w in ['a', 'i']]
        word_counts = Counter(filtered_words)
        
        new_words_count = 0
        total_words = len(filtered_words)
        
        # Update word frequencies in database
        for word, frequency in word_counts.items():
            word_id = db.get_or_add_word(word)
            if word_id is not None:
                # Update frequency directly from transcript count
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE words SET frequency = frequency + ? WHERE id = ?', (frequency, word_id))
                conn.commit()
                conn.close()
                
                db.add_user_word(user_id, word_id)
                new_words_count += 1
        
        video_id = db.add_video_record(filename, total_words, transcript, video_url)
        if video_id:
            for word in word_counts.keys():
                word_id = db.get_or_add_word(word)
                if word_id is not None:
                    db.add_video_word(video_id, word_id)
            
            # Store word frequencies for this video
            db.add_word_frequencies(video_id, word_counts)
        
        print(f"✅ İşlem tamamlandı! {new_words_count} yeni kelime, {total_words} toplam kelime")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'new_words_found': new_words_count,
            'total_words': total_words,
            'unique_words': len(word_counts),
            'transcript_preview': (transcript[:200] + '...') if transcript else ''
        }), 200
        
    except Exception as e:
        print(f"❌ Video işleminde hata: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/process-video-url', methods=['POST'])
def process_video_url() -> Tuple[Response, int]:
    """Process video from URL"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    video_url: Optional[str] = data.get('video_url')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    if not video_url:
        return jsonify({'success': False, 'error': 'Video URL required'}), 400
    
    return _process_video_logic(user_id, video_url)

@app.route('/api/words', methods=['GET'])
def get_words() -> Tuple[Response, int]:
    """Get user's words"""
    user_id_str = request.args.get('user_id')
    status: str = request.args.get('status', 'all')
    
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    try:
        user_id = int(user_id_str)
        known_only: Optional[bool] = None
        if status == 'known':
            known_only = True
        elif status == 'unknown':
            known_only = False
        words = db.get_user_words(user_id, known_only)
        
        return jsonify({
            'success': True,
            'words': words,
            'count': len(words)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/words/<int:word_id>/definition', methods=['GET'])
def get_word_definition_api(word_id: int) -> Tuple[Response, int]:
    """Get definition for a word"""
    try:
        word = db.get_word(word_id)
        if not word:
            return jsonify({'success': False, 'error': 'Word not found'}), 404
        
        return jsonify({
            'success': True,
            'word': word['word'],
            'definition': word.get('definition', ''),
            'pronunciation': word.get('pronunciation', '')
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== AI TRANSLATION ENDPOINTS =====

# Global translator instance for local model
_local_translator = None

def get_local_translator():
    """Get or initialize the local Argos Translate model for EN->TR translation."""
    global _local_translator
    
    if _local_translator is not None:
        return _local_translator
    
    try:
        import argostranslate.package
        import argostranslate.translate
        
        print("🔄 Yerel çeviri modeli yükleniyor (Argos Translate)...")
        
        # Check if EN->TR package is installed
        installed_languages = argostranslate.translate.get_installed_languages()
        en_lang = next((lang for lang in installed_languages if lang.code == "en"), None)
        tr_lang = next((lang for lang in installed_languages if lang.code == "tr"), None)
        
        if en_lang and tr_lang:
            _local_translator = en_lang.get_translation(tr_lang)
            if _local_translator:
                print("✅ Yerel çeviri modeli hazır!")
                return _local_translator
        
        # If not installed, download and install
        print("📥 İngilizce-Türkçe dil paketi indiriliyor...")
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        
        # Find EN->TR package
        package_to_install = next(
            (pkg for pkg in available_packages 
             if pkg.from_code == "en" and pkg.to_code == "tr"),
            None
        )
        
        if package_to_install:
            download_path = package_to_install.download()
            argostranslate.package.install_from_path(download_path)
            print("✅ Dil paketi kuruldu!")
            
            # Get translator again
            installed_languages = argostranslate.translate.get_installed_languages()
            en_lang = next((lang for lang in installed_languages if lang.code == "en"), None)
            tr_lang = next((lang for lang in installed_languages if lang.code == "tr"), None)
            
            if en_lang and tr_lang:
                _local_translator = en_lang.get_translation(tr_lang)
                return _local_translator
        else:
            print("❌ İngilizce-Türkçe dil paketi bulunamadı!")
            return None
            
    except ImportError:
        print("❌ Argos Translate kurulu değil. Kurmak için: pip install argostranslate")
        return None
    except Exception as e:
        print(f"❌ Yerel çeviri modeli yüklenirken hata: {e}")
        return None
    
    return None

def translate_with_local_model(word: str) -> Optional[str]:
    """Translate a single word using local Argos Translate model."""
    translator = get_local_translator()
    
    if translator is None:
        return None
    
    try:
        translation = translator.translate(word)
        return translation if translation else None
    except Exception as e:
        print(f"Çeviri hatası ({word}): {e}")
        return None

def auto_translate_all_words() -> int:
    """Automatically translate all words without definitions using LOCAL model.
    Called after word map is built.
    Returns the number of words translated.
    Uses Argos Translate - a free, open-source, offline translation model.
    """
    total_translated = 0
    
    print("🤖 Yerel model ile otomatik çeviri başlatılıyor...")
    print("📦 Model: Argos Translate (açık kaynak, offline)")
    
    # Initialize translator first
    translator = get_local_translator()
    if translator is None:
        print("❌ Yerel çeviri modeli başlatılamadı!")
        return 0
    
    try:
        # Get all words without definitions
        batch_num = 0
        while True:
            words_to_translate = db.get_words_without_definition(limit=100)
            
            if not words_to_translate:
                break
            
            batch_num += 1
            translated_definitions = []
            
            # Translate each word with local model
            for word_data in words_to_translate:
                try:
                    word = word_data['word']
                    translation = translator.translate(word)
                    
                    if translation and translation.strip():
                        translated_definitions.append({
                            'word_id': word_data['id'],
                            'definition': translation.strip(),
                            'pronunciation': ''
                        })
                except Exception as e:
                    continue
            
            # Save to database
            if translated_definitions:
                updated = db.bulk_update_definitions(translated_definitions)
                total_translated += updated
                print(f"✅ Batch {batch_num}: {len(translated_definitions)} kelime çevrildi (Toplam: {total_translated})")
            else:
                break
        
        print(f"🎉 Yerel model ile çeviri tamamlandı: {total_translated} kelime")
        return total_translated
        
    except Exception as e:
        print(f"❌ Otomatik çeviri hatası: {e}")
        return total_translated

@app.route('/api/translate/stats', methods=['GET'])
def get_translation_stats() -> Tuple[Response, int]:
    """Get statistics about word translations/definitions"""
    try:
        stats = db.get_definition_stats()
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/translate/words', methods=['POST'])
def translate_words() -> Tuple[Response, int]:
    """Translate words using LOCAL Argos Translate model (no API needed)"""
    try:
        data = request.get_json() or {}
        package_id = data.get('package_id')  # Optional: translate only words in a specific package
        limit = min(data.get('limit', 50), 100)  # Max 100 words per request
        
        # Get words without definitions
        words_to_translate = db.get_words_without_definition(limit=limit, package_id=package_id)
        
        if not words_to_translate:
            return jsonify({
                'success': True,
                'message': 'Çevrilecek kelime bulunamadı - tüm kelimeler zaten çevrilmiş!',
                'translated_count': 0
            }), 200
        
        # Use local Argos Translate model
        translator = get_local_translator()
        if translator is None:
            return jsonify({
                'success': False,
                'error': 'Yerel çeviri modeli yüklenemedi. Lütfen argostranslate paketini kurun: pip install argostranslate'
            }), 500
        
        translated_definitions = []
        
        for word_data in words_to_translate:
            try:
                translation = translator.translate(word_data['word'])
                if translation and translation.strip():
                    translated_definitions.append({
                        'word_id': word_data['id'],
                        'definition': translation.strip(),
                        'pronunciation': ''
                    })
            except Exception as e:
                print(f"Çeviri hatası ({word_data['word']}): {e}")
                continue
        
        print(f"✅ Yerel model ile {len(translated_definitions)} kelime çevrildi")
        
        # Save translations to database
        if translated_definitions:
            updated_count = db.bulk_update_definitions(translated_definitions)
            
            return jsonify({
                'success': True,
                'message': f'{updated_count} kelime başarıyla çevrildi ve kaydedildi!',
                'translated_count': updated_count,
                'method': 'argos_translate_local'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Çeviri yapılamadı'
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Çeviri hatası: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/translate/package/<int:package_id>', methods=['POST'])
def translate_package_words(package_id: int) -> Tuple[Response, int]:
    """Translate all words in a specific learning package using LOCAL model"""
    try:
        data = request.get_json() or {}
        limit = min(data.get('limit', 100), 500)  # Max 500 words per package
        
        # Get words without definitions in this package
        words_to_translate = db.get_words_without_definition(limit=limit, package_id=package_id)
        
        if not words_to_translate:
            return jsonify({
                'success': True,
                'message': 'Bu seviyedeki tüm kelimeler zaten çevrilmiş!',
                'translated_count': 0,
                'package_id': package_id
            }), 200
        
        # Use local Argos Translate model
        translator = get_local_translator()
        if translator is None:
            return jsonify({
                'success': False,
                'error': 'Yerel çeviri modeli yüklenemedi'
            }), 500
        
        translated_definitions = []
        
        for word_data in words_to_translate:
            try:
                translation = translator.translate(word_data['word'])
                if translation and translation.strip():
                    translated_definitions.append({
                        'word_id': word_data['id'],
                        'definition': translation.strip(),
                        'pronunciation': ''
                    })
            except Exception:
                continue
        
        # Save to database
        if translated_definitions:
            updated_count = db.bulk_update_definitions(translated_definitions)
            return jsonify({
                'success': True,
                'message': f'Seviye {package_id}: {updated_count} kelime çevrildi!',
                'translated_count': updated_count,
                'package_id': package_id
            }), 200
        
        return jsonify({'success': False, 'error': 'Çeviri yapılamadı'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/words/<int:word_id>/mark', methods=['POST'])
def update_word_status(word_id: int) -> Tuple[Response, int]:
    """Mark word as known/unknown"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    known = data.get('known', False)
    
    # Handle string boolean
    if isinstance(known, str):
        known = known.lower() == 'true'
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    try:
        db.update_user_word_status(user_id, word_id, bool(known))
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats() -> Tuple[Response, int]:
    """Get user statistics"""
    user_id_str = request.args.get('user_id')
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    stats = db.get_user_stats(int(user_id_str))
    
    return jsonify({
        'success': True,
        'stats': stats
    }), 200

@app.route('/api/videos', methods=['GET'])
def get_videos() -> Response:
    """Get processed videos"""
    user_id_str = request.args.get('user_id')
    user_id = int(user_id_str) if user_id_str else None
    
    videos = db.get_videos(user_id)
    
    return jsonify({
        'success': True,
        'videos': videos
    })

@app.route('/api/videos/<int:video_id>/words', methods=['GET'])
def get_video_words_details(video_id: int) -> Tuple[Response, int]:
    """Get detailed words for a video"""
    user_id_str = request.args.get('user_id')
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
        
    words = db.get_video_words_details(video_id, int(user_id_str))
    return jsonify({'success': True, 'words': words}), 200

@app.route('/api/videos/<int:video_id>', methods=['DELETE'])
def delete_video(video_id: int) -> Response:
    """Delete a processed video"""
    success = db.delete_video(video_id)
    return jsonify({'success': success})

def fetch_transcript_from_web(season: int, episode: int) -> Optional[str]:
    """Web sitelerinden Friends transkriptini/alt yazıyı çekmeye çalış"""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import]
    except ImportError:
        return None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    # 0. Try Local Files (Subtitles folder)
    try:
        # Folder structure: Subtitles/Friends1, Subtitles/Friends2, etc.
        # Assuming user placed 'Subtitles' folder in the project root
        local_dir = os.path.join("Subtitles", f"Friends{season}")
        
        if os.path.exists(local_dir):
            # Pattern matching: "1x01" for S1E01, "10x15" for S10E15
            search_pattern = f"{season}x{episode:02d}"
            
            target_file = None
            for filename in os.listdir(local_dir):
                if search_pattern in filename and filename.endswith(('.srt', '.vtt')):
                    target_file = os.path.join(local_dir, filename)
                    break
            
            if target_file:
                print(f"   📂 Yerel dosya bulundu: {os.path.basename(target_file)}")
                transcript = speech_processor.parse_subtitle_file(target_file)
                if transcript and len(transcript) > 100:
                    print(f"   ✅ Yerel dosyadan alındı")
                    return transcript
    except Exception as e:
        print(f"   ⚠️ Yerel dosya okuma hatası: {str(e)[:50]}")

    # 1. Try TVMuse.com (Script Database)
    try:
        url = f"https://www.tvmuse.com/tv-shows/Friends/season_{season}/episode_{episode}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            script_div = soup.find('div', class_='panel-body')
            if script_div:
                transcript = script_div.get_text(separator='\n')
                if transcript.strip() and len(transcript) > 100:
                    print(f"   ✅ TVMuse'dan alındı")
                    return transcript[:8000]
    except Exception as e:
        print(f"   ⚠️ TVMuse hatası: {str(e)[:50]}")
    
  
    except Exception as e:
        print(f"   ⚠️ Genius hatası: {str(e)[:50]}")
    
    # 3. Try IMDb for episode info
    try:
        url = f"https://www.imdb.com/find?q=Friends+season+{season}+episode+{episode}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to find the episode link and then get plot
            results = soup.find_all('div', class_='findResult')
            if results:
                # Get first result (should be the TV episode)
                first_result = results[0]
                title_elem = first_result.find('a')
                if title_elem and 'href' in title_elem.attrs:
                    href = title_elem['href']
                    if isinstance(href, list):
                        href = href[0]
                    episode_url = 'https://www.imdb.com' + str(href)
                    ep_response = requests.get(episode_url, headers=headers, timeout=5)
                    if ep_response.status_code == 200:
                        ep_soup = BeautifulSoup(ep_response.content, 'html.parser')
                        
                        # Try to find plot summary
                        plot_section = ep_soup.find('section', {'data-testid': 'Storyline'})
                        if plot_section:
                            plot_text = plot_section.get_text()
                            if len(plot_text) > 50:
                                print(f"   ✅ IMDb'den alındı")
                                return plot_text[:5000]
    except Exception as e:
        print(f"   ⚠️ IMDb hatası: {str(e)[:50]}")
    
    # 4. Try Scripts.com (if accessible)
    try:
        url = f"https://www.scripts.com/scripts/tv_show_scripts.php?sname=friends&season={season}&episode={episode}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for pre-formatted script
            pre_elem = soup.find('pre')
            if pre_elem:
                transcript = pre_elem.get_text()
                if len(transcript) > 100:
                    print(f"   ✅ Scripts.com'dan alındı")
                    return transcript[:8000]
    except Exception as e:
        print(f"   ⚠️ Scripts.com hatası: {str(e)[:50]}")
    
    # 5. Try OpenSubtitles API for subtitle/transcript data
    try:
        # Using a generic search for Friends scripts
        url = "https://www.imdb.com/title/tt0108778/episodes"  # Friends main page
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Find episode in the season
            episodes = soup.find_all('div', class_='episode')
            if episodes and len(episodes) > episode - 1:
                ep_div = episodes[episode - 1]
                plot = ep_div.find('div', class_='plot')
                if plot:
                    transcript = plot.get_text().strip()
                    if len(transcript) > 50:
                        print(f"   ✅ IMDb episodes listesinden alındı")
                        return transcript[:5000]
    except Exception as e:
        print(f"   ⚠️ Episodes liste hatası: {str(e)[:50]}")
    
    # 6. Fallback: Create synthetic transcript from episode info
    try:
        print(f"   ℹ️ Fallback: Episode bilgisi oluşturuluyor...")
        # Use episode metadata if available
        url = f"https://en.wikipedia.org/wiki/Friends_(season_{season})#Episodes"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.find_all('table', class_='wikitable')
            if tables:
                rows = tables[0].find_all('tr')
                if len(rows) > episode:
                    ep_row = rows[episode]
                    cols = ep_row.find_all('td')
                    if len(cols) >= 3:
                        ep_title = cols[1].get_text().strip()
                        ep_info = cols[2].get_text().strip()
                        synthetic_transcript = f"Friends - Season {season} Episode {episode}\n\nTitle: {ep_title}\n\nEpisode Information:\n{ep_info}\n\n[Complete episode script not available, showing episode summary]"
                        if len(synthetic_transcript) > 50:
                            print(f"   ✅ Wikipedia'dan alındı")
                            return synthetic_transcript
    except Exception as e:
        print(f"   ⚠️ Wikipedia hatası: {str(e)[:50]}")
    
    return None

@app.route('/api/friends/load', methods=['POST'])
def load_friends_transcripts() -> Tuple[Response, int]:
    """Friends Dizisinin transkriptlerini web sitelerinden yükle"""
    raw_data = request.get_json()
    data: Dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    user_id: Optional[int] = data.get('user_id')
    target_season = data.get('season')

    try:
        print(f"🎬 Friends transkriptleri web sitelerinden yükleniyor... (Hedef: {target_season})")
        
        # Friends sezonları ve episode bilgileri
        friends_episodes: Dict[int, Union[int, List[str]]] = {
            1: [
                "Pilot",
                "The One with the Sonogram at the End",
                "The One Hundred",
                "The One with Two Parts: Part 1",
                "The One with Two Parts: Part 2",
                "The One with the Butt",
                "The One with the Blackmail",
                "The One Where Nap-Land is Closed",
                "The One Where Underdog Gets Away",
                "The One with the Monkey",
                "The One with Mrs. Bing",
                "The One with the Dozen Lasagnas",
                "The One with Rachael Green",
                "The One with Two Rooms",
                "The One with the Stoned Guy",
                "The One with Two Parts: Part 1",
                "The One with the Bullies",
                "The One with a Loser",
                "The One with the Fake Monica",
                "The One with the Ick Factor",
                "The One with the Thumb",
                "The One with the Boobies",
                "The One with the Curtains",
                "The One with the Rumor",
            ],
            2: 24, 3: 25, 4: 24, 5: 24,
            6: 25, 7: 24, 8: 24, 9: 24, 10: 18
        }
        
        seasons_to_process: Dict[int, int] = {}
        if target_season and target_season != 'all':
            try:
                s_num = int(target_season)
                if s_num in friends_episodes:
                    season_info = friends_episodes[s_num]
                    if isinstance(season_info, list):
                        seasons_to_process = {s_num: len(season_info)}
                    else:
                        seasons_to_process = {s_num: season_info}
            except ValueError:
                pass
        
        if not seasons_to_process:
            # Default: Season 1 sadece
            seasons_to_process = {1: 24}

        added_count = 0
        failed_count = 0
        
        for season, episodes_count in seasons_to_process.items():
            for episode in range(1, episodes_count + 1):
                # Episode adı varsa onu kullan, yoksa generic isim
                title = f"Friends - Season {season} Episode {episode:02d}"
                
                if season in friends_episodes:
                    season_info = friends_episodes[season]
                    if isinstance(season_info, list):
                        if episode <= len(season_info):
                            ep_title = season_info[episode - 1]
                            title = f"Friends - Season {season} Episode {episode:02d}: {ep_title}"
                
                print(f"📥 S{season}E{episode:02d} yükleniyor...", end=" ")
                
                # Web'den transkript çekmeye çalış
                transcript = fetch_transcript_from_web(season, episode)
                
                # Eğer web'den bulamazsa fallback transcript oluştur
                if not transcript:
                    # Generate fallback with episode metadata
                    transcript = f"{title}\n\n[Episode Summary]\nFriends - Season {season}, Episode {episode}\n\nThis episode includes various storylines and comedy bits from the show.\nFor full script, please visit official sources.\n\nCommon vocabulary from this episode:\nfriendship, humor, drama, everyday conversations, American English vocabulary"
                    print(f"(Fallback oluşturuldu)")
                
                # Kelimeleri analiz et
                words = speech_processor.extract_words(transcript)
                word_count = len(words)
                
                # Veritabanına kaydet
                video_id = db.add_video_record(
                    filename=title,
                    word_count=word_count,
                    transcript=transcript,
                    video_url="https://www.imdb.com/title/tt0108778/",
                    title=title,
                    description=f"Friends Season {season}, Episode {episode}"
                )
                
                if video_id:
                    added_count += 1
                    for word in words:
                        word_id = db.get_or_add_word(word)
                        if word_id is not None:
                            db.add_video_word(video_id, word_id)
                            if user_id:
                                db.add_user_word(user_id, word_id)
        
        message = f"✅ {added_count} Friends bölümü yüklendi!"
        if failed_count > 0:
            message += f"\n⚠️ {failed_count} bölüm web'den çekilemedi (fallback kullanıldı)"
        
        return jsonify({
            'success': True,
            'message': message,
            'count': added_count,
            'failed_count': failed_count
        }), 200
        
    except Exception as e:
        print(f"❌ Friends transkriptleri yüklenirken hata: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/friends/cleanup', methods=['POST'])
def cleanup_friends_videos() -> Response:
    """Delete fallback/short Friends videos"""
    count = db.delete_videos_by_criteria(title_like='Friends%', max_word_count=500)
    return jsonify({'success': True, 'count': count, 'message': f'{count} adet hatalı/kısa video temizlendi.'})

# ===== FRIENDS EPISODE ANALYSIS =====

@app.route('/api/friends/analyze', methods=['GET'])
def analyze_friends_episodes() -> Tuple[Response, int]:
    """
    Friends dizisi bölümlerini analiz eder ve seviyelere göre kelime dağılımını gösterir.
    
    Query params:
    - season: Belirli bir sezon (1-10) veya 'all' (varsayılan)
    - sort_by: Sıralama alanı (total, level_1, level_2, ... veya episode)
    - sort_order: asc veya desc (varsayılan: asc)
    
    Returns:
    - episodes: Her bölüm için seviye dağılımı
    - total_levels: Toplam seviye sayısı
    - summary: İstatistikler
    """
    target_season = request.args.get('season', 'all')
    sort_by = request.args.get('sort_by', 'total')
    sort_order = request.args.get('sort_order', 'asc')
    
    # Friends subtitle paths - try multiple locations
    possible_paths = [
        "VocabLevel-master/VocabLevel-master/Subtitles",
        "Subtitles",
        "../Subtitles",
        "../VocabLevel-master/VocabLevel-master/Subtitles"
    ]
    
    base_path = None
    for path in possible_paths:
        abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        if os.path.exists(abs_path):
            base_path = abs_path
            break
    
    if not base_path:
        return jsonify({
            'success': False,
            'error': 'Friends subtitle klasörü bulunamadı',
            'possible_paths': possible_paths
        }), 404
    
    # Get learning levels from database
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT package_number, min_frequency, max_frequency FROM learning_packages ORDER BY package_number')
    levels = cursor.fetchall()
    conn.close()
    
    if not levels:
        return jsonify({
            'success': False,
            'error': 'Öğrenme seviyeleri bulunamadı. Önce kelime veritabanını oluşturun.'
        }), 404
    
    # Create word-to-level mapping
    # OPTIMIZATION: Fetch all mappings in a single query instead of looping
    word_levels: Dict[str, int] = {}
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT w.word, lp.package_number 
        FROM words w
        JOIN package_words pw ON w.id = pw.word_id
        JOIN learning_packages lp ON pw.package_id = lp.id
    ''')
    for row in cursor.fetchall():
        word_levels[row['word'].lower()] = row['package_number']
    conn.close()
    
    # Friends season configurations
    friends_seasons: Dict[int, Dict[str, Any]] = {
        1: {"episodes": 24, "name": "Season 1"},
        2: {"episodes": 24, "name": "Season 2"},
        3: {"episodes": 25, "name": "Season 3"},
        4: {"episodes": 24, "name": "Season 4"},
        5: {"episodes": 24, "name": "Season 5"},
        6: {"episodes": 25, "name": "Season 6"},
        7: {"episodes": 24, "name": "Season 7"},
        8: {"episodes": 24, "name": "Season 8"},
        9: {"episodes": 24, "name": "Season 9"},
        10: {"episodes": 18, "name": "Season 10"},
    }
    
    # Parse which seasons to analyze
    seasons_to_analyze: List[int] = []
    if target_season == 'all':
        seasons_to_analyze = list(friends_seasons.keys())
    else:
        try:
            s = int(target_season)
            if s in friends_seasons:
                seasons_to_analyze = [s]
        except ValueError:
            pass
    
    if not seasons_to_analyze:
        seasons_to_analyze = [1]  # Default to season 1
    
    # Episode patterns to try for finding subtitle files
    patterns = [
        lambda s, e: f"friends.s{s:02d}e{e:02d}",  # friends.s01e01
        lambda s, e: f"Friends - {s}x{e:02d}",      # Friends - 1x01
        lambda s, e: f"Friends - [{s}x{e:02d}]",    # Friends - [1x01]
        lambda s, e: f"{s}x{e:02d}",                # 1x01
    ]
    
    results: List[Dict[str, Any]] = []
    total_levels = len(levels)
    
    for season in seasons_to_analyze:
        season_info = friends_seasons[season]
        season_folder = os.path.join(base_path, f"Friends{season}")
        
        # Also check Friends1, Friends2 etc.
        if not os.path.exists(season_folder):
            alt_folder = os.path.join(base_path, f"Friends{season}")
        
        for episode in range(1, season_info["episodes"] + 1):
            episode_data = {
                "season": season,
                "episode": episode,
                "title": f"S{season}E{episode:02d}",
                "total_words": 0,
                "unknown_words": 0,
            }
            
            # Add level columns
            for i in range(1, total_levels + 1):
                episode_data[f"level_{i}"] = 0
            
            subtitle_path = None
            
            # Try to find subtitle file
            if os.path.exists(season_folder):
                for filename in os.listdir(season_folder):
                    filename_lower = filename.lower()
                    for pattern in patterns:
                        pattern_str = pattern(season, episode)
                        if pattern_str.lower() in filename_lower and filename_lower.endswith(('.srt', '.sub', '.vtt')):
                            subtitle_path = os.path.join(season_folder, filename)
                            break
                    if subtitle_path:
                        break
            
            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Parse SRT and extract words
                    words = speech_processor.extract_words(content)
                    episode_data["total_words"] = len(words)
                    
                    # Count words per level
                    level_counts: Dict[int, int] = {}
                    for word in words:
                        word_lower = word.lower()
                        level = word_levels.get(word_lower)
                        
                        if level:
                            if level not in level_counts:
                                level_counts[level] = 0
                            level_counts[level] += 1
                        else:
                            episode_data["unknown_words"] += 1
                    
                    # Update episode data with level counts
                    for level_num, count in level_counts.items():
                        episode_data[f"level_{level_num}"] = count
                        
                except Exception as e:
                    print(f"   ⚠️ Hata: {subtitle_path} okunamadı: {str(e)[:50]}")
            
            results.append(episode_data)
    
    # Sort results
    reverse = sort_order == 'desc'
    if sort_by == 'episode':
        results.sort(key=lambda x: (x['season'], x['episode']), reverse=reverse)
    elif sort_by in ['total', 'unknown_words']:
        results.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    elif sort_by.startswith('level_'):
        level_num = int(sort_by.split('_')[1])
        results.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    else:
        # Default sort by total words
        results.sort(key=lambda x: x.get('total', 0), reverse=reverse)
    
    # Calculate summary statistics
    total_words_all = sum(ep.get('total_words', 0) for ep in results)
    total_unknown = sum(ep.get('unknown_words', 0) for ep in results)
    
    level_sums: Dict[str, int] = {}
    for i in range(1, total_levels + 1):
        level_sums[f"level_{i}"] = sum(ep.get(f"level_{i}", 0) for ep in results)
    
    summary = {
        "seasons_analyzed": seasons_to_analyze,
        "total_episodes": len(results),
        "total_words": total_words_all,
        "total_unknown": total_unknown,
        "total_known": total_words_all - total_unknown,
        "level_sums": level_sums,
        "average_words_per_episode": round(total_words_all / len(results), 1) if results else 0
    }
    
    return jsonify({
        'success': True,
        'episodes': results,
        'total_levels': total_levels,
        'level_info': [
            {"level": i, "min_freq": l['min_frequency'], "max_freq": l['max_frequency']}
            for i, l in enumerate(levels, start=1)
        ],
        'summary': summary,
        'sort_by': sort_by,
        'sort_order': sort_order
    }), 200

# ===== LEARNING PATHWAY ROUTES =====

@app.route('/api/packages', methods=['GET'])
def get_learning_packages() -> Tuple[Response, int]:
    """Get all learning packages"""
    try:
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        if user_id:
            packages = db.get_all_packages_progress(user_id)
        
        else:
            packages = db.get_learning_packages()
        
        return jsonify({
            'success': True,
            'packages': packages,
            'count': len(packages)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/packages/<int:package_id>', methods=['GET'])
def get_package_details(package_id: int) -> Tuple[Response, int]:
    """Get details of a specific package"""
    try:
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        # Get package info
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, package_number, package_name, word_count, min_frequency, max_frequency
            FROM learning_packages WHERE id = ?
        ''', (package_id,))
        package = cursor.fetchone()
        conn.close()
        
        if not package:
            return jsonify({'success': False, 'error': 'Paket bulunamadı'}), 404
        
        package_info = dict(package)
        
        # Get progress if user_id provided
        if user_id:
            progress = db.get_package_progress(package_id, user_id)
            package_info['progress'] = progress
        
        return jsonify({
            'success': True,
            'package': package_info
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/packages/<int:package_id>/words', methods=['GET'])
def get_package_words(package_id: int) -> Tuple[Response, int]:
    """Get words for a specific package"""
    try:
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        words = db.get_package_words(package_id, user_id)
        
        return jsonify({
            'success': True,
            'words': words,
            'count': len(words)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/packages/<int:package_id>/progress', methods=['GET'])
def get_package_user_progress(package_id: int) -> Tuple[Response, int]:
    """Get user's progress for a specific package"""
    try:
        user_id_str = request.args.get('user_id')
        if not user_id_str:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        user_id = int(user_id_str)
        progress = db.get_package_progress(package_id, user_id)
        
        return jsonify({
            'success': True,
            'progress': progress
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/recalculate-levels', methods=['POST'])
def recalculate_levels() -> Tuple[Response, int]:
    """
    Veritabanındaki kelimelere göre kelime haritasını hesaplar,
    yedek alır ve frekanslara göre seviyelendirmeyi yeniden yapar.
    """
    try:
        # 1. Yedek al
        import shutil
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f'learning_backup_{timestamp}.db'
        if os.path.exists('learning.db'):
            shutil.copy('learning.db', backup_path)
        
        # 2. Paketleri yeniden oluştur (Database sınıfındaki metodu kullan)
        # Varsayılan paket boyutu 500
        package_size = 500
        data = request.get_json() or {}
        if 'package_size' in data:
            try:
                package_size = int(data['package_size'])
            except:
                pass
                
        count = db.generate_learning_packages(package_size)
        
        # 3. İstatistikleri topla
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Genel istatistikler
        cursor.execute("SELECT COUNT(*), SUM(frequency) FROM words")
        row = cursor.fetchone()
        total_words = row[0] if row else 0
        total_freq = row[1] if row else 0
        
        # Frekans dağılımı
        freq_ranges = [
            (10000, "Çok Yüksek"),
            (1000, "Yüksek"),
            (100, "Orta-Yüksek"),
            (50, "Orta"),
            (10, "Orta-Düşük"),
            (5, "Düşük"),
            (0, "Çok Düşük")
        ]
        
        distribution = []
        for min_freq, label in freq_ranges:
            cursor.execute("SELECT COUNT(*) FROM words WHERE frequency >= ?", (min_freq,))
            cnt = cursor.fetchone()[0]
            distribution.append({'label': label, 'min_freq': min_freq, 'count': cnt})
            
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Kelime haritası hesaplandı. {count} seviye oluşturuldu.',
            'backup_created': backup_path,
            'stats': {
                'total_words': total_words,
                'total_freq': total_freq,
                'distribution': distribution,
                'levels_created': count
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/packages/create', methods=['POST'])
def create_learning_packages() -> Tuple[Response, int]:
    """Create learning packages from words table"""
    try:
        package_size = request.args.get('size', 500)
        try:
            package_size = int(package_size)
        except ValueError:
            package_size = 500
        
        count = db.generate_learning_packages(package_size)
        
        return jsonify({
            'success': True,
            'message': f'{count} adet öğrenme paketi oluşturuldu!',
            'packages_created': count
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== SUBTITLE ANALYSIS ROUTES =====

@app.route('/api/dictionary/all', methods=['GET'])
def get_full_dictionary() -> Tuple[Response, int]:
    """Get all words with their package/level info for the analyzer"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.word, w.frequency, lp.package_number
            FROM words w
            JOIN package_words pw ON w.id = pw.word_id
            JOIN learning_packages lp ON pw.package_id = lp.id
            ORDER BY w.frequency DESC
        ''')
        words = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'words': words}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/subtitles/list', methods=['GET'])
def list_subtitles() -> Tuple[Response, int]:
    """List available subtitle files in Subtitles directory"""
    target_path = request.args.get('path', '')
    
    # Security check
    if ".." in target_path:
        return jsonify({'success': False, 'error': 'Invalid path'}), 403
    
    # Try multiple base directory locations
    base_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles"),
        "Subtitles",
        "../Subtitles"
    ]
    
    base_dir = None
    for dir_path in base_dirs:
        if os.path.exists(dir_path):
            base_dir = dir_path
            break
    
    if not base_dir:
        return jsonify({'success': False, 'error': 'Subtitles directory not found'}), 404
    
    # If path is provided, look in that subdirectory
    if target_path:
        search_dir = os.path.join(base_dir, target_path)
    else:
        search_dir = base_dir
    
    files = []
    if os.path.exists(search_dir):
        for root, dirs, filenames in os.walk(search_dir):
            for f in filenames:
                if f.lower().endswith(('.srt', '.sub', '.vtt', '.txt', '.db')):
                    rel_path = os.path.relpath(os.path.join(root, f), base_dir)

                    # Klasör yolunu grup ismi olarak kullan (örn: "Big Bang Theory/Season 1")
                    group_name = os.path.dirname(rel_path) or 'Uncategorized'

                    files.append({
                        'path': rel_path,
                        'name': f,
                        'season': group_name
                    })
    
    return jsonify({'success': True, 'files': files}), 200

@app.route('/api/subtitles/content', methods=['GET'])
def get_subtitle_content() -> Tuple[Response, int]:
    """Get content of a specific subtitle file"""
    path = request.args.get('path')
    if not path:
        return jsonify({'success': False, 'error': 'Path required'}), 400
    
    full_path = os.path.join("Subtitles", path)
    # Security check to prevent directory traversal
    if ".." in path or not os.path.abspath(full_path).startswith(os.path.abspath("Subtitles")):
         return jsonify({'success': False, 'error': 'Invalid path'}), 403
         
    if os.path.exists(full_path):
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return jsonify({'success': True, 'content': content}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'File not found'}), 404

@app.route('/api/subtitles/stats', methods=['GET'])
def get_subtitle_stats() -> Tuple[Response, int]:
    """Get statistics for all subtitle databases in a folder"""
    path = request.args.get('path', '')
    
    # Security check
    if ".." in path:
        return jsonify({'success': False, 'error': 'Invalid path'}), 403
    
    # Try multiple base directory locations
    base_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles"),
        "Subtitles",
        "../Subtitles"
    ]
    
    base_dir = None
    for dir_path in base_dirs:
        if os.path.exists(dir_path):
            base_dir = dir_path
            break
    
    if not base_dir:
        return jsonify({'success': False, 'error': 'Subtitles directory not found'}), 404
    
    full_path = os.path.join(base_dir, path) if path else base_dir
    
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'error': 'Path not found'}), 404
    
    import sqlite3
    from collections import Counter
    
    stats = []
    global_counter = Counter()
    
    for root, dirs, filenames in os.walk(full_path):
        for filename in filenames:
            if filename.endswith('.db') and filename != 'combined_stats.db':
                db_path = os.path.join(root, filename)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # Get individual stats for the list
                    cursor.execute("SELECT COUNT(*), SUM(frequency) FROM word_frequencies")
                    result = cursor.fetchone()
                    
                    # Aggregate words for global stats
                    cursor.execute("SELECT word, frequency FROM word_frequencies")
                    # Use dict to bulk update counter for performance
                    global_counter.update(dict(cursor.fetchall()))
                    
                    conn.close()
                    
                    rel_path = os.path.relpath(db_path, base_dir)
                    stats.append({
                        'name': filename,
                        'path': rel_path,
                        'unique_words': result[0] or 0,
                        'total_words': result[1] or 0
                    })
                except Exception as e:
                    print(f"Error reading {db_path}: {e}")
    
    # Create or update combined_stats.db
    if global_counter:
        combined_db_path = os.path.join(full_path, 'combined_stats.db')
        try:
            conn = sqlite3.connect(combined_db_path)
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS word_frequencies")
            cursor.execute("""
                CREATE TABLE word_frequencies (
                    word TEXT PRIMARY KEY,
                    frequency INTEGER NOT NULL
                )
            """)
            
            # Insert sorted data
            sorted_data = sorted(global_counter.items(), key=lambda x: x[1], reverse=True)
            cursor.executemany("INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)", sorted_data)
            
            conn.commit()
            conn.close()
            
            # Add combined stats to the list as well
            stats.append({
                'name': 'combined_stats.db',
                'path': os.path.relpath(combined_db_path, base_dir),
                'unique_words': len(global_counter),
                'total_words': sum(global_counter.values())
            })
            
        except Exception as e:
            print(f"Error creating combined DB: {e}")
    
    # Sort by name
    stats.sort(key=lambda x: x['name'])
    
    return jsonify({
        'success': True,
        'databases': stats,
        'summary': {
            'total_databases': len(stats) - (1 if global_counter else 0),
            'total_unique_words': len(global_counter),
            'total_words': sum(global_counter.values())
        }
    }), 200

@app.route('/api/subtitles/db-words', methods=['GET'])
def get_db_words() -> Tuple[Response, int]:
    """Get words from a specific subtitle database"""
    path = request.args.get('path')
    if not path:
        return jsonify({'success': False, 'error': 'Path required'}), 400
    
    # Security check
    if ".." in path:
        return jsonify({'success': False, 'error': 'Invalid path'}), 403
    
    # Try multiple base directory locations
    base_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles"),
        "Subtitles",
        "../Subtitles"
    ]
    
    base_dir = None
    for dir_path in base_dirs:
        if os.path.exists(dir_path):
            base_dir = dir_path
            break
    
    if not base_dir:
        return jsonify({'success': False, 'error': 'Subtitles directory not found'}), 404
    
    full_path = os.path.join(base_dir, path)
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'error': 'Database not found'}), 404
    
    try:
        import sqlite3
        
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        conn = sqlite3.connect(full_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT word, frequency FROM word_frequencies ORDER BY frequency DESC LIMIT ? OFFSET ?", (limit, offset))
        words = [{'word': row[0], 'frequency': row[1]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(*) FROM word_frequencies")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'words': words,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== SUBTITLE EPISODE PROCESSING ROUTE =====

@app.route('/api/subtitles/process-episode', methods=['POST'])
def process_subtitle_episode() -> Tuple[Response, int]:
    """Process a subtitle file and create video record for an episode"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    series = data.get('series')  # 'friends' or 'bigbang'
    season = data.get('season')
    episode = data.get('episode')
    user_id = data.get('user_id')
    
    if not series or not season or not episode:
        return jsonify({'success': False, 'error': 'series, season and episode are required'}), 400
    
    # Find subtitle file
    subtitles_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
    
    subtitle_path = None
    
    if series == 'friends':
        # Friends pattern: Friends{season}/friends.s{season}e{episode}.720p.bluray.x264-psychd.srt
        season_folder = f"Friends{season}"
        patterns = [
            f"friends.s{season:02d}e{episode:02d}",
            f"friends.s{season}e{episode}",
            f"Friends - {season}x{episode:02d}"
        ]
        
        season_path = os.path.join(subtitles_base, season_folder)
        if os.path.exists(season_path):
            for filename in os.listdir(season_path):
                filename_lower = filename.lower()
                for pattern in patterns:
                    if pattern.lower() in filename_lower and filename_lower.endswith(('.srt', '.vtt', '.txt')):
                        subtitle_path = os.path.join(season_path, filename)
                        break
                if subtitle_path:
                    break
                    
    elif series == 'bigbang':
        # Big Bang pattern: BigBangTheory/series-{season}-episode-{episode}-{name}.txt
        bbt_path = os.path.join(subtitles_base, "BigBangTheory")
        patterns = [
            f"series-{season}-episode-{episode}-",
            f"series-{season}-episode-{episode:02d}-",
            f"{season}x{episode:02d}"
        ]
        
        if os.path.exists(bbt_path):
            for filename in os.listdir(bbt_path):
                filename_lower = filename.lower()
                for pattern in patterns:
                    if pattern in filename_lower and filename_lower.endswith(('.txt', '.srt', '.vtt')):
                        subtitle_path = os.path.join(bbt_path, filename)
                        break
                if subtitle_path:
                    break
    
    if not subtitle_path or not os.path.exists(subtitle_path):
        return jsonify({
            'success': False, 
            'error': f'Subtitle file not found for {series} S{season}E{episode}'
        }), 404
    
    # Read and parse subtitle
    try:
        with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract words using speech processor
        words = speech_processor.extract_words(content)
        word_count = len(words)
        
        # Generate title
        if series == 'friends':
            title = f"Friends - {season}x{episode:02d}"
        else:
            title = f"Big Bang Theory - {season}x{episode:02d}"
        
        # Add words to database
        new_words_count = 0
        for word in words:
            word_id = db.get_or_add_word(word)
            if word_id is not None:
                # Get definition for new words
                definition, pronunciation = db.get_word_definition(word)
                if definition:
                    db.update_word_definition(word_id, definition, pronunciation or '')
                
                if user_id:
                    db.add_user_word(user_id, word_id)
                new_words_count += 1
        
        # Create video record
        video_id = db.add_video_record(
            filename=title,
            word_count=word_count,
            transcript=content,
            video_url=f"subtitle://{series}/{season}/{episode}",
            title=title,
            description=f"{series.capitalize()} Season {season} Episode {episode}"
        )
        
        if video_id:
            # Link words to video
            for word in words:
                word_id = db.get_or_add_word(word)
                if word_id is not None:
                    db.add_video_word(video_id, word_id)
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'title': title,
            'word_count': word_count,
            'unique_words': new_words_count,
            'message': f'Processed {title} with {word_count} words'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== WEBSOCKET EVENTS =====

@socketio.on('connect')
def handle_connect() -> None:
    """User connected"""
    print(f'Client connected: {request.sid}') # type: ignore
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect() -> None:
    """User disconnected"""
    if request.sid in active_sessions: # type: ignore
        user_info = active_sessions[request.sid] # type: ignore
        room_id = user_info.get('room_id')
        user_id = user_info.get('user_id')
        
        if room_id and user_id:
            # Remove from database
            db.remove_member_from_room(room_id, user_id)
            
            # Check if room is empty
            members = db.get_room_members(room_id)
            if not members:
                db.close_room(room_id)
            else:
                emit('user_left', {
                    'user_id': user_id,
                    'username': user_info.get('username')
                }, to=f'room_{room_id}')
        
        del active_sessions[request.sid] # type: ignore
    
    print(f'Client disconnected: {request.sid}') # type: ignore

@socketio.on('join_room')
def on_join_room(data: Dict[str, Any]) -> None:
    """User joins watch room"""
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    username = data.get('username')
    
    if not room_id or not user_id:
        emit('error', {'message': 'Room ID and User ID required'})
        return
    
    room_name = f'room_{room_id}'
    join_room(room_name)
    
    active_sessions[request.sid] = { # type: ignore
        'room_id': room_id,
        'user_id': user_id,
        'username': username
    }
    
    # Add to database
    db.add_member_to_room(room_id, user_id)
    
    # Notify others
    emit('user_joined', {
        'user_id': user_id,
        'username': username,
        'members': db.get_room_members(room_id)
    }, to=room_name)
    
    print(f'{username} joined room {room_id}')

@socketio.on('leave_room')
def on_leave_room(data: Dict[str, Any]) -> None:
    """User leaves watch room"""
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    
    if request.sid in active_sessions and room_id and user_id: # type: ignore
        room_name = f'room_{room_id}'
        leave_room(room_name)
        
        # Remove from database
        db.remove_member_from_room(room_id, user_id)
        
        # Check if room is empty
        members = db.get_room_members(room_id)
        if not members:
            db.close_room(room_id)
        else:
            # Notify others
            emit('user_left', {
                'user_id': user_id,
                'username': active_sessions[request.sid]['username'], # type: ignore
                'members': members
            }, to=room_name)
        
        del active_sessions[request.sid] # type: ignore

@socketio.on('send_message')
def on_send_message(data: Dict[str, Any]) -> None:
    """Handle chat message"""
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    message = data.get('message', '')
    username = data.get('username', 'Anonymous')
    
    if not room_id or not user_id or not message:
        emit('error', {'message': 'Invalid message data'})
        return
    
    # Save to database
    msg_id = db.add_chat_message(room_id, user_id, message)
    
    # Broadcast to room
    room_name = f'room_{room_id}'
    emit('new_message', {
        'id': msg_id,
        'user_id': user_id,
        'username': username,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }, to=room_name)

@socketio.on('video_sync')
def on_video_sync(data: Dict[str, Any]) -> None:
    """Sync video playback"""
    room_id = data.get('room_id')
    action = data.get('action')  # 'play', 'pause', 'seek'
    current_time = data.get('current_time', 0)
    user_id = data.get('user_id')
    
    if not room_id:
        return
    
    # Store video state
    if room_id not in room_video_states:
        room_video_states[room_id] = {}
    
    room_video_states[room_id] = {
        'action': action,
        'current_time': current_time,
        'user_id': user_id,
        'timestamp': datetime.now().isoformat()
    }
    
    # Broadcast to room
    room_name = f'room_{room_id}'
    emit('video_state_changed', {
        'action': action,
        'current_time': current_time,
        'user_id': user_id
    }, to=room_name, skip_sid=request.sid) # type: ignore

@socketio.on('screen_share_start')
def on_screen_share_start(data: Dict[str, Any]) -> None:
    """User starts screen sharing"""
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    username = data.get('username')
    
    if room_id and user_id:
        db.set_screen_sharing(room_id, user_id, True)
        
        room_name = f'room_{room_id}'
        emit('screen_share_started', {
            'user_id': user_id,
            'username': username,
            'members': db.get_room_members(room_id)
        }, to=room_name)

@socketio.on('screen_share_stop')
def on_screen_share_stop(data: Dict[str, Any]) -> None:
    """User stops screen sharing"""
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    username = data.get('username')
    
    if room_id and user_id:
        db.set_screen_sharing(room_id, user_id, False)
        
        room_name = f'room_{room_id}'
        emit('screen_share_stopped', {
            'user_id': user_id,
            'username': username,
            'members': db.get_room_members(room_id)
        }, to=room_name)

@socketio.on('webrtc_offer')
def on_webrtc_offer(data: Dict[str, Any]) -> None:
    """Handle WebRTC offer for screen sharing"""
    room_id = data.get('room_id')
    offer = data.get('offer')
    
    if room_id:
        room_name = f'room_{room_id}'
        emit('webrtc_offer', {
            'offer': offer,
            'from_user_id': data.get('user_id')
        }, to=room_name)

@socketio.on('webrtc_answer')
def on_webrtc_answer(data: Dict[str, Any]) -> None:
    """Handle WebRTC answer for screen sharing"""
    room_id = data.get('room_id')
    answer = data.get('answer')
    
    if room_id:
        room_name = f'room_{room_id}'
        emit('webrtc_answer', {
            'answer': answer,
            'from_user_id': data.get('user_id')
        }, to=room_name)

@socketio.on('webrtc_ice_candidate')
def on_webrtc_ice_candidate(data: Dict[str, Any]) -> None:
    """Handle ICE candidate for WebRTC"""
    room_id = data.get('room_id')
    candidate = data.get('candidate')
    
    if room_id:
        room_name = f'room_{room_id}'
        emit('webrtc_ice_candidate', {
            'candidate': candidate,
            'from_user_id': data.get('user_id')
        }, to=room_name)

# ===== SERIES WORD MAP ROUTES =====

@app.route('/api/series/build-word-map', methods=['POST'])
def build_combined_word_map() -> Tuple[Response, int]:
    """Build word map from selected series database files (can combine multiple series)"""
    try:
        data = request.get_json()
        selected_series = data.get('series', [])  # List of series: ['friends', 'bigbang']
        
        if not selected_series:
            return jsonify({'success': False, 'error': 'No series selected'}), 400
        
        import sqlite3
        from collections import Counter
        
        # Collect all words from all selected series
        all_words_counter = Counter()
        db_files_processed = 0
        processed_series = []
        
        subtitles_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
        
        for series in selected_series:
            folder_path = None
                
            # Check if it's a built-in series
            if series == 'friends':
                folder_path = os.path.join(subtitles_base, "friends_db")
            elif series == 'bigbang':
                folder_path = os.path.join(subtitles_base, "bigbang_db")
            else:
                # Check if it's a custom series
                custom_series = db.get_custom_series_by_id(series)
                if custom_series:
                    folder_path = custom_series['db_folder_path']
            
            if not folder_path or not os.path.exists(folder_path):
                continue
            
            # Collect words from this series
            series_words = Counter()
            series_files = 0
            
            for filename in os.listdir(folder_path):
                if filename.endswith('.db'):
                    db_path = os.path.join(folder_path, filename)
                    try:
                        # Use timeout for external database connections
                        conn = sqlite3.connect(db_path, timeout=30.0)
                        cursor = conn.cursor()
                        
                        # Read word frequencies from this episode's database
                        cursor.execute("SELECT word, frequency FROM word_frequencies")
                        for row in cursor.fetchall():
                            word = row[0].lower().strip()
                            frequency = row[1]
                            series_words[word] += frequency
                        
                        conn.close()
                        series_files += 1
                    except Exception as e:
                        print(f"Error processing {filename}: {e}")
                        continue
            
            # Merge into main counter
            for word, freq in series_words.items():
                all_words_counter[word] += freq
            
            db_files_processed += series_files
            processed_series.append(series)
        
        if not all_words_counter:
            return jsonify({
                'success': False,
                'error': 'No words found in selected series databases'
            }), 404
        
        # Add all words to main database (with proper transaction handling)
        conn_main = None
        try:
            conn_main = db.get_connection()
            cursor_main = conn_main.cursor()
            
            # Start transaction
            words_added = 0
            batch_size = 100
            word_batch = []
            
            for word, total_frequency in all_words_counter.items():
                # Get or add word
                word_id = db.get_or_add_word(word)
                if word_id:
                    word_batch.append((total_frequency, word_id))
                    words_added += 1
                    
                    # Batch update for better performance
                    if len(word_batch) >= batch_size:
                        cursor_main.executemany('UPDATE words SET frequency = ? WHERE id = ?', word_batch)
                        conn_main.commit()
                        word_batch = []
            
            # Update remaining words
            if word_batch:
                cursor_main.executemany('UPDATE words SET frequency = ? WHERE id = ?', word_batch)
                conn_main.commit()
            
            # Generate learning packages from these words
            # Clear existing packages first
            cursor_main.execute('DELETE FROM package_words')
            cursor_main.execute('DELETE FROM learning_packages')
            conn_main.commit()
            
            # Generate new packages
            package_size = 500
            count = db.generate_learning_packages(package_size)
            
            conn_main.commit()
            
            # Auto-translate all words in background
            translated_count = auto_translate_all_words()
            
            return jsonify({
                'success': True,
                'series': processed_series,
                'unique_words': len(all_words_counter),
                'total_frequency': sum(all_words_counter.values()),
                'db_files_processed': db_files_processed,
                'words_added': words_added,
                'packages_created': count,
                'translated_count': translated_count,
                'message': f'Word map built for {", ".join(processed_series)}: {len(all_words_counter)} unique words, {count} packages created, {translated_count} words translated'
            }), 200
            
        except Exception as e:
            if conn_main:
                conn_main.rollback()
            raise e
        finally:
            if conn_main:
                conn_main.close()
        
    except Exception as e:
        import traceback
        print(f"Error building word map: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# Old endpoint removed - now using /api/profile/word-map for combined word map

# ===== PROFILE WORD MAP ROUTES =====

@app.route('/api/profile/word-map', methods=['GET'])
def get_profile_word_map() -> Tuple[Response, int]:
    """Get word map data for the profile page"""
    try:
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 1. General statistics
        # Önce learning_packages var mı kontrol et
        cursor.execute("SELECT COUNT(*) FROM learning_packages")
        total_levels = cursor.fetchone()[0]
        
        # package_words'te kelime var mı kontrol et
        cursor.execute("SELECT COUNT(*) FROM package_words")
        has_package_words = cursor.fetchone()[0] > 0
        
        # Eğer learning packages varsa, sadece package_words'teki kelimeleri say (senkronizasyon için)
        # Yoksa tüm words tablosunu kullan (geriye dönük uyumluluk için)
        if has_package_words and total_levels > 0:
            # Toplam kelime sayısı: sadece package_words'teki kelimeler
            cursor.execute("SELECT COUNT(DISTINCT pw.word_id) FROM package_words pw")
            total_words_result = cursor.fetchone()
            total_words = total_words_result[0] if total_words_result else 0
            
            # Toplam frekans: package_words'teki kelimelerin frekansları
            cursor.execute('''
                SELECT COALESCE(SUM(w.frequency), 0) 
                FROM package_words pw
                JOIN words w ON pw.word_id = w.id
            ''')
            total_freq_result = cursor.fetchone()
            total_freq = total_freq_result[0] if total_freq_result else 0
            
            # Calculate total known words - sadece package_words'teki bilinen kelimeler
            total_known = 0
            if user_id:
                cursor.execute('''
                    SELECT COUNT(DISTINCT uw.word_id)
                    FROM user_words uw
                    JOIN package_words pw ON uw.word_id = pw.word_id
                    WHERE uw.user_id = ? AND uw.known = 1
                ''', (user_id,))
                total_known_result = cursor.fetchone()
                total_known = total_known_result[0] if total_known_result else 0
        else:
            # Learning packages yoksa, tüm words tablosunu kullan
            cursor.execute("SELECT COUNT(*), SUM(frequency) FROM words")
            result = cursor.fetchone()
            total_words = result[0] if result else 0
            total_freq = result[1] if result else 0
            
            # Calculate total known words - tüm bilinen kelimeler
            total_known = 0
            if user_id:
                cursor.execute("SELECT COUNT(*) FROM user_words WHERE user_id = ? AND known = 1", (user_id,))
                total_known_result = cursor.fetchone()
                total_known = total_known_result[0] if total_known_result else 0
        
        # 2. Learning packages
        cursor.execute('''
            SELECT id, package_number, package_name, word_count, min_frequency, max_frequency
            FROM learning_packages ORDER BY package_number
        ''')
        packages = []
        for row in cursor.fetchall():
            packages.append({
                'id': row[0],
                'package_number': row[1],
                'package_name': row[2],
                'word_count': row[3],
                'min_frequency': row[4],
                'max_frequency': row[5]
            })
        
        # 3. User progress for each package
        progress_data = {}
        if user_id:
            cursor.execute('''
                SELECT pw.package_id, COUNT(DISTINCT uw.word_id) as known
                FROM package_words pw
                JOIN user_words uw ON pw.word_id = uw.word_id
                WHERE uw.user_id = ? AND uw.known = 1
                GROUP BY pw.package_id
            ''', (user_id,))
            for row in cursor.fetchall():
                progress_data[row[0]] = row[1]
        
        # 4. Frequency distribution - sadece package_words'teki kelimeler
        freq_buckets = [
            (10000, "Çok Yüksek"),
            (1000, "Yüksek"),
            (100, "Orta-Yüksek"),
            (50, "Orta"),
            (10, "Orta-Düşük"),
            (5, "Düşük"),
            (0, "Çok Düşük")
        ]
        
        freq_distribution = []
        for min_freq, label in freq_buckets:
            cursor.execute('''
                SELECT COUNT(DISTINCT pw.word_id)
                FROM package_words pw
                JOIN words w ON pw.word_id = w.id
                WHERE w.frequency >= ?
            ''', (min_freq,))
            cnt_result = cursor.fetchone()
            cnt = cnt_result[0] if cnt_result else 0
            freq_distribution.append({
                'category': label,
                'min_freq': min_freq,
                'count': cnt
            })
        
        # 5. Top and bottom words - sadece package_words'teki kelimeler
        cursor.execute('''
            SELECT w.word, w.frequency 
            FROM package_words pw
            JOIN words w ON pw.word_id = w.id
            ORDER BY w.frequency DESC 
            LIMIT 20
        ''')
        top_words = []
        for row in cursor.fetchall():
            if hasattr(row, 'keys'):
                top_words.append({'word': row['word'], 'frequency': row['frequency']})
            else:
                top_words.append({'word': row[0], 'frequency': row[1]})
        
        cursor.execute('''
            SELECT w.word, w.frequency 
            FROM package_words pw
            JOIN words w ON pw.word_id = w.id
            ORDER BY w.frequency ASC 
            LIMIT 20
        ''')
        bottom_words = []
        for row in cursor.fetchall():
            if hasattr(row, 'keys'):
                bottom_words.append({'word': row['word'], 'frequency': row['frequency']})
            else:
                bottom_words.append({'word': row[0], 'frequency': row[1]})
        
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_words': total_words,
                'known_words': total_known,
                'total_freq': total_freq,
                'total_levels': total_levels,
                'avg_frequency': round(total_freq / total_words, 2) if total_words > 0 else 0
            },
            'levels': packages,
            'progress': progress_data,
            'freq_distribution': freq_distribution,
            'top_words': top_words,
            'bottom_words': bottom_words
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== DATA MANAGEMENT =====

@app.route('/api/backup', methods=['GET'])
def backup_database() -> Union[Response, Tuple[Response, int]]:
    """Download database backup"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return send_file(
            'learning.db',
            as_attachment=True,
            download_name=f'watch_together_backup_{timestamp}.db'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/restore', methods=['POST'])
def restore_database() -> Tuple[Response, int]:
    """Restore database from backup"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Dosya seçilmedi'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Dosya seçilmedi'}), 400
    
    if file and file.filename and file.filename.endswith('.db'):
        try:
            file.save('learning.db')
            return jsonify({'success': True, 'message': 'Veritabanı başarıyla geri yüklendi. Sayfa yenileniyor...'}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': False, 'error': 'Geçersiz dosya formatı (.db gerekli)'}), 400

# ===== FLASHCARD SYSTEM ROUTES =====

@app.route('/api/flashcards/start', methods=['POST'])
def start_flashcard_session() -> Tuple[Response, int]:
    """Start a new flashcard study session"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    session_type: str = data.get('type', 'all')  # 'level', 'video', 'all', 'problem', 'random'
    target_id: Optional[int] = data.get('target_id')  # package_id or video_id
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    if session_type not in ['level', 'video', 'all', 'problem', 'random']:
        return jsonify({'success': False, 'error': 'Invalid session type'}), 400
    
    if session_type in ['level', 'video'] and not target_id:
        return jsonify({'success': False, 'error': f'target_id required for {session_type} session'}), 400
    
    try:
        session_id = db.create_flashcard_session(user_id, session_type, target_id)
        
        if session_id is None:
            return jsonify({
                'success': False,
                'error': 'No words found to study',
                'message': 'You have studied all available words!'
            }), 400
        
        current_word = db.get_flashcard_current_word(session_id)
        stats = db.get_flashcard_session_stats(session_id)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'session_type': session_type,
            'current_word': current_word,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flashcards/session/<int:session_id>', methods=['GET'])
def get_flashcard_session(session_id: int) -> Tuple[Response, int]:
    """Get current flashcard session state"""
    user_id_str = request.args.get('user_id')
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    user_id = int(user_id_str)
    
    try:
        current_word = db.get_flashcard_current_word(session_id)
        stats = db.get_flashcard_session_stats(session_id)
        
        if not stats:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'current_word': current_word,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flashcards/session/<int:session_id>/answer', methods=['POST'])
def submit_flashcard_answer(session_id: int) -> Tuple[Response, int]:
    """Submit answer for current flashcard"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    word_id: Optional[int] = data.get('word_id')
    is_correct: bool = data.get('correct', False)
    
    if not user_id or not word_id:
        return jsonify({'success': False, 'error': 'User ID and word ID required'}), 400
    
    try:
        result = db.submit_flashcard_answer(session_id, word_id, is_correct, user_id)
        
        if result['next_word'] is None:
            # Session complete
            db.complete_flashcard_session(session_id)
            stats = db.get_flashcard_session_stats(session_id)
            return jsonify({
                'success': True,
                'completed': True,
                'message': '🎉 Tebrikler! Oturumu tamamladınız!',
                'stats': stats
            }), 200
        
        return jsonify({
            'success': True,
            'completed': False,
            'current_word': result['next_word'],
            'session_stats': result['session_stats']
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flashcards/session/<int:session_id>/skip', methods=['POST'])
def skip_flashcard(session_id: int) -> Tuple[Response, int]:
    """Skip current flashcard (will appear again later)"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    user_id: Optional[int] = data.get('user_id')
    word_id: Optional[int] = data.get('word_id')
    
    if not user_id or not word_id:
        return jsonify({'success': False, 'error': 'User ID and word ID required'}), 400
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE flashcard_progress 
            SET status = 'skipped',
                attempts = attempts + 1,
                last_answer_time = CURRENT_TIMESTAMP
            WHERE session_id = ? AND word_id = ?
        ''', (session_id, word_id))
        conn.commit()
        conn.close()
        
        # Get next word
        current_word = db.get_flashcard_current_word(session_id)
        stats = db.get_flashcard_session_stats(session_id)
        
        if current_word is None:
            db.complete_flashcard_session(session_id)
            return jsonify({
                'success': True,
                'completed': True,
                'message': 'Oturum tamamlandı!',
                'stats': stats
            }), 200
        
        return jsonify({
            'success': True,
            'current_word': current_word,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flashcards/session/<int:session_id>/stats', methods=['GET'])
def get_flashcard_session_stats(session_id: int) -> Tuple[Response, int]:
    """Get detailed statistics for a flashcard session"""
    try:
        stats = db.get_flashcard_session_stats(session_id)
        
        if not stats:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flashcards/problems', methods=['GET'])
def get_problem_words() -> Tuple[Response, int]:
    """Get words user has struggled with"""
    user_id_str = request.args.get('user_id')
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    user_id = int(user_id_str)
    limit = int(request.args.get('limit', 20))
    
    try:
        words = db.get_problem_words(user_id, limit)
        return jsonify({
            'success': True,
            'words': words,
            'count': len(words)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flashcards/options', methods=['GET'])
def get_flashcard_options() -> Tuple[Response, int]:
    """Get available flashcard study options for user"""
    user_id_str = request.args.get('user_id')
    if not user_id_str:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    user_id = int(user_id_str)
    
    try:
        # Get learning packages with unknown word counts
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT lp.id, lp.package_number, lp.package_name, lp.word_count,
                   (SELECT COUNT(*) FROM package_words pw2 
                    JOIN user_words uw ON pw2.word_id = uw.word_id 
                    WHERE pw2.package_id = lp.id AND uw.user_id = ? AND uw.known = 1) as known_count
            FROM learning_packages lp
            ORDER BY lp.package_number
        ''', (user_id,))
        
        packages = []
        for row in cursor.fetchall():
            unknown_count = row['word_count'] - row['known_count']
            packages.append({
                'id': row['id'],
                'name': row['package_name'],
                'unknown_words': unknown_count,
                'total_words': row['word_count']
            })
        
        # Get videos with unknown word counts
        cursor.execute('''
            SELECT v.id, v.title, v.word_count,
                   (SELECT COUNT(*) FROM video_words vw2 
                    JOIN user_words uw ON vw2.word_id = uw.word_id 
                    WHERE vw2.video_id = v.id AND uw.user_id = ? AND uw.known = 1) as known_count
            FROM videos v
            ORDER BY v.processed_date DESC
            LIMIT 20
        ''', (user_id,))
        
        videos = []
        for row in cursor.fetchall():
            unknown_count = row['word_count'] - row['known_count']
            videos.append({
                'id': row['id'],
                'title': row['title'] or row['filename'],
                'unknown_words': unknown_count,
                'total_words': row['word_count']
            })
        
        # Get user stats
        user_stats = db.get_user_stats(user_id)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'options': {
                'levels': packages,
                'videos': videos,
                'all_words': {
                    'name': 'Tüm Bilinmeyen Kelimeler',
                    'unknown_words': user_stats.get('unknown', 0)
                },
                'problem_words': {
                    'name': 'Zorlandığım Kelimeler',
                    'unknown_words': len(db.get_problem_words(user_id, 50))
                },
                'random': {
                    'name': 'Rastgele 50 Kelime',
                    'unknown_words': min(50, user_stats.get('unknown', 0))
                }
            },
            'user_stats': user_stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== WORD FREQUENCY API ROUTES =====

@app.route('/api/word-frequencies/<int:video_id>', methods=['GET'])
def get_video_word_frequencies(video_id: int) -> Tuple[Response, int]:
    """Get word frequencies for a specific video"""
    try:
        frequencies = db.get_video_word_frequencies(video_id)
        summary = db.get_video_word_frequency_summary(video_id)
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'frequencies': frequencies,
            'summary': summary
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/word-frequencies', methods=['GET'])
def get_all_word_frequencies() -> Tuple[Response, int]:
    """Get all word frequencies from all videos"""
    try:
        frequencies = db.get_all_word_frequencies()
        
        # Group by video for easier display
        videos_dict: Dict[int, Dict[str, Any]] = {}
        for row in frequencies:
            video_id = row['video_id']
            if video_id not in videos_dict:
                videos_dict[video_id] = {
                    'filename': row['filename'],
                    'words': []
                }
            videos_dict[video_id]['words'].append({
                'word': row['word'],
                'frequency': row['frequency']
            })
        
        return jsonify({
            'success': True,
            'frequencies': frequencies,
            'by_video': videos_dict,
            'total_entries': len(frequencies)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/videos/<int:video_id>/frequencies', methods=['DELETE'])
def delete_video_frequencies(video_id: int) -> Tuple[Response, int]:
    """Delete word frequencies for a video"""
    try:
        success = db.delete_word_frequencies(video_id)
        return jsonify({
            'success': success,
            'message': 'Word frequencies deleted' if success else 'Failed to delete'
        }), 200 if success else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== EPISODE FLASHCARDS ROUTES =====

@app.route('/api/episodes/<int:video_id>/flashcards', methods=['GET'])
def get_episode_video_flashcards(video_id: int) -> Tuple[Response, int]:
    """Get flashcards for a specific video/episode"""
    try:
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        result = db.get_episode_flashcards(video_id, user_id)
        
        if not result.get('success', False):
            return jsonify(result), 404
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== SERIES SPECIFIC ROUTES (Friends & Big Bang Theory) =====

@app.route('/api/series/<series>/videos', methods=['GET'])
def get_series_videos(series: str) -> Tuple[Response, int]:
    """Get videos for a specific series (friends or bigbang)"""
    if series not in ['friends', 'bigbang']:
        return jsonify({'success': False, 'error': 'Invalid series. Use friends or bigbang'}), 400
    
    try:
        season = request.args.get('season', type=int)
        episode = request.args.get('episode', type=int)
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        videos = db.get_series_videos(series, season, episode)
        
        # Add user stats if user_id provided
        if user_id:
            for video in videos:
                video_id = video['id']
                # Get known count for this video
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        COUNT(CASE WHEN uw.known = 1 THEN 1 END) as known,
                        COUNT(CASE WHEN uw.known = 0 OR uw.known IS NULL THEN 1 END) as unknown
                    FROM video_words vw
                    LEFT JOIN user_words uw ON vw.word_id = uw.word_id AND uw.user_id = ?
                    WHERE vw.video_id = ?
                ''', (user_id, video_id))
                stats = cursor.fetchone()
                conn.close()
                video['known_count'] = stats['known']
                video['unknown_count'] = stats['unknown']
        
        return jsonify({
            'success': True,
            'series': series,
            'videos': videos,
            'count': len(videos)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/series/<series>/stats', methods=['GET'])
def get_series_stats(series: str) -> Tuple[Response, int]:
    """Get learning statistics for a specific series"""
    if series not in ['friends', 'bigbang']:
        return jsonify({'success': False, 'error': 'Invalid series. Use friends or bigbang'}), 400
    
    try:
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        stats = db.get_series_stats(series, user_id)
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/series/<series>/episodes', methods=['GET'])
def get_series_episodes(series: str) -> Tuple[Response, int]:
    """Get list of available episodes for a series with database paths"""
    if series not in ['friends', 'bigbang']:
        return jsonify({'success': False, 'error': 'Invalid series. Use friends or bigbang'}), 400
    
    try:
        # Season configuration
        if series == 'friends':
            seasons = {
                1: 24, 2: 24, 3: 25, 4: 24, 5: 24,
                6: 25, 7: 24, 8: 24, 9: 24, 10: 18
            }
        else:  # bigbang
            seasons = {
                1: 17, 2: 23, 3: 23, 4: 24, 5: 24,
                6: 24, 7: 24, 8: 24, 9: 24, 10: 24,
                11: 24, 12: 24
            }
        
        # Subtitles base directory
        subtitles_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
        
        # Build episode list with database status
        episodes = []
        for season, episode_count in seasons.items():
            season_episodes = []
            
            # Determine folder name - use friends_db and bigbang_db folders
            if series == 'friends':
                folder_name = "friends_db"
            else:
                folder_name = "bigbang_db"
            
            folder_path = os.path.join(subtitles_base, folder_name)
            
            for ep_num in range(1, episode_count + 1):
                # Find .db file for this episode
                db_path = None
                
                if os.path.exists(folder_path):
                    # Search for .db files in the folder
                    for filename in os.listdir(folder_path):
                        if filename.endswith('.db'):
                            # Check if filename contains season and episode
                            filename_lower = filename.lower()
                            
                            if series == 'friends':
                                # Support multiple naming patterns: s01e01, friends.1x01, [1x01], 1x01
                                patterns = [
                                    f"s{season:02d}e{ep_num:02d}",  # s01e01
                                    f"s{season}e{ep_num:02d}",       # s1e01
                                    f"friends.{season}x{ep_num:02d}",  # friends.1x01
                                    f"[{season}x{ep_num:02d}]",      # [1x01]
                                    f"{season}x{ep_num:02d}",        # 1x01
                                    f"- {season}x{ep_num:02d} -",    # - 1x01 -
                                    f"- [{season}x{ep_num:02d}] -"   # - [1x01] -
                                ]
                            else:
                                # BigBang Theory: series-1-episode-1-, series-1-episode-01-
                                patterns = [
                                    f"series-{season}-episode-{ep_num}-",
                                    f"series-{season}-episode-{ep_num:02d}-"
                                ]
                            
                            for pattern in patterns:
                                if pattern in filename_lower:
                                    db_path = os.path.join(folder_path, filename)
                                    break
                            if db_path:
                                break
                
                has_db = db_path is not None and os.path.exists(db_path) if db_path else False
                
                season_episodes.append({
                    'episode': ep_num,
                    'has_db': has_db,
                    'db_path': db_path,
                    'word_count': 0,
                    'video_id': None
                })
            
            episodes.append({
                'season': season,
                'episodes': season_episodes
            })
        
        return jsonify({
            'success': True,
            'series': series,
            'episodes': episodes,
            'seasons': seasons
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/series/<series>/episodes/<int:season>/<int:episode>/flashcards', methods=['GET'])
def get_episode_cards_from_db(series: str, season: int, episode: int) -> Tuple[Response, int]:
    """Get flashcards from a subtitle .db file for an episode"""
    if series not in ['friends', 'bigbang']:
        return jsonify({'success': False, 'error': 'Invalid series'}), 400
    
    try:
        # Find the .db file
        subtitles_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
        
        if series == 'friends':
            folder_name = "friends_db"
        else:
            folder_name = "bigbang_db"
        
        folder_path = os.path.join(subtitles_base, folder_name)
        db_path = None
        
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.db'):
                    filename_lower = filename.lower()
                    
                    if series == 'friends':
                        # Support multiple naming patterns: s01e01, friends.1x01, [1x01], 1x01
                        patterns = [
                            f"s{season:02d}e{episode:02d}",  # s01e01
                            f"s{season}e{episode:02d}",       # s1e01
                            f"friends.{season}x{episode:02d}",  # friends.1x01
                            f"[{season}x{episode:02d}]",      # [1x01]
                            f"{season}x{episode:02d}",        # 1x01
                            f"- {season}x{episode:02d} -",    # - 1x01 -
                            f"- [{season}x{episode:02d}] -"   # - [1x01] -
                        ]
                    else:
                        # BigBang Theory: series-1-episode-1-, series-1-episode-01-
                        patterns = [
                            f"series-{season}-episode-{episode}-",
                            f"series-{season}-episode-{episode:02d}-"
                        ]
                    
                    for pattern in patterns:
                        if pattern in filename_lower:
                            db_path = os.path.join(folder_path, filename)
                            break
                    if db_path:
                        break
        
        if not db_path or not os.path.exists(db_path):
            return jsonify({
                'success': False,
                'error': f'Database file not found for {series} S{season}E{episode}'
            }), 404
        
        # Read words from .db file
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT word, frequency FROM word_frequencies ORDER BY frequency DESC")
        db_words = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM word_frequencies")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        # Get user_id from query parameter if provided
        user_id = request.args.get('user_id', type=int)
        
        # Get user's known words if user_id provided
        user_known_words = set()
        if user_id:
            conn_user = db.get_connection()
            cursor_user = conn_user.cursor()
            cursor_user.execute('SELECT word_id FROM user_words WHERE user_id = ? AND known = 1', (user_id,))
            rows = cursor_user.fetchall()
            # Handle both Row objects and tuples
            if rows and hasattr(rows[0], 'keys'):
                user_known_words = {row['word_id'] for row in rows}
            else:
                user_known_words = {row[0] for row in rows}
            conn_user.close()
        
        # Get word details from main database (definition, pronunciation, etc.)
        # Tüm kelimeleri flashcard olarak göster, seviye bilgisi ekle
        flashcards = []
        known_count = 0
        unknown_count = 0
        word_ids_in_episode = []  # Track word IDs for level statistics
        
        # Get all word IDs that are in learning packages (for level info)
        conn_main = db.get_connection()
        cursor_main = conn_main.cursor()
        
        # Get word_id to level mapping
        cursor_main.execute('''
            SELECT pw.word_id, lp.package_number, lp.package_name, lp.id as package_id
            FROM package_words pw
            JOIN learning_packages lp ON pw.package_id = lp.id
        ''')
        word_level_map = {}
        for row in cursor_main.fetchall():
            if hasattr(row, 'keys'):
                word_id = row['word_id']
                word_level_map[word_id] = {
                    'level_number': row['package_number'],
                    'level_name': row['package_name'],
                    'package_id': row['package_id']
                }
            else:
                word_id = row[0]
                word_level_map[word_id] = {
                    'level_number': row[1],
                    'level_name': row[2],
                    'package_id': row[3]
                }
        
        conn_main.close()
        
        for row in db_words:
            word_text = row[0]
            frequency = row[1]
            
            # Get word data from main database
            word_data = db.get_word_by_text(word_text)
            if word_data:
                word_id = word_data.get('id')
                
                # Check if user knows this word
                known = word_id in user_known_words if user_id and word_id else False
                
                # Get level info for this word
                level_info = word_level_map.get(word_id) if word_id else None
                
                # Count for statistics (only words in packages)
                if word_id and word_id in word_level_map:
                    word_ids_in_episode.append(word_id)
                    if known:
                        known_count += 1
                    else:
                        unknown_count += 1
                
                # Add flashcard with level info
                flashcard_data = {
                    'id': word_id,
                    'word': word_data.get('word', word_text),
                    'frequency': frequency,
                    'definition': word_data.get('definition', ''),
                    'pronunciation': word_data.get('pronunciation', ''),
                    'known': known
                }
                
                # Add level information if available
                if level_info:
                    flashcard_data['level_number'] = level_info['level_number']
                    flashcard_data['level_name'] = level_info['level_name']
                    flashcard_data['package_id'] = level_info['package_id']
                else:
                    flashcard_data['level_number'] = None
                    flashcard_data['level_name'] = 'Seviye Dışı'
                    flashcard_data['package_id'] = None
                
                flashcards.append(flashcard_data)
            else:
                # If word not in main database, add basic info
                unknown_count += 1
                flashcards.append({
                    'id': None,
                    'word': word_text,
                    'frequency': frequency,
                    'definition': '',
                    'pronunciation': '',
                    'known': False,
                    'level_number': None,
                    'level_name': 'Seviye Dışı',
                    'package_id': None
                })
        
        # Calculate level statistics (how many words from each level/package are in this episode)
        # Tüm kelimeler için seviye dağılımı (sadece package_words'teki değil)
        level_stats = {}
        level_stats_all = {}  # Tüm kelimeler için (package_words'te olmayanlar dahil)
        
        # Initialize level_stats_all before processing flashcards
        level_stats_all = {}
        
        # Package_words'teki kelimeler için seviye dağılımı
        if word_ids_in_episode and len(word_ids_in_episode) > 0:
            try:
                conn_main = db.get_connection()
                cursor_main = conn_main.cursor()
                
                # Get level distribution for words in this episode
                placeholders = ','.join('?' * len(word_ids_in_episode))
                cursor_main.execute(f'''
                    SELECT lp.package_number, lp.package_name, COUNT(DISTINCT pw.word_id) as word_count
                    FROM package_words pw
                    JOIN learning_packages lp ON pw.package_id = lp.id
                    WHERE pw.word_id IN ({placeholders})
                    GROUP BY lp.package_number, lp.package_name
                    ORDER BY lp.package_number
                ''', word_ids_in_episode)
                
                rows = cursor_main.fetchall()
                for row in rows:
                    # Handle both Row objects and tuples
                    if hasattr(row, 'keys'):
                        level_num = row['package_number']
                        level_name = row['package_name']
                        word_count = row['word_count']
                    else:
                        level_num = row[0]
                        level_name = row[1]
                        word_count = row[2]
                    
                    level_stats[level_num] = {
                        'level_number': level_num,
                        'level_name': level_name,
                        'word_count': word_count
                    }
                
                conn_main.close()
            except Exception as e:
                print(f"Error calculating level stats: {e}")
                # Continue without level stats if there's an error
        
        # Tüm flashcard'lardaki kelimeler için seviye dağılımı (package_words'te olmayanlar dahil)
        for flashcard in flashcards:
            if flashcard.get('level_number') is not None:
                level_num = flashcard['level_number']
                if level_num not in level_stats_all:
                    level_stats_all[level_num] = {
                        'level_number': level_num,
                        'level_name': flashcard.get('level_name', f'Seviye {level_num}'),
                        'word_count': 0
                    }
                level_stats_all[level_num]['word_count'] += 1
            else:
                # Seviye dışı kelimeler
                if 'Seviye Dışı' not in level_stats_all:
                    level_stats_all['Seviye Dışı'] = {
                        'level_number': None,
                        'level_name': 'Seviye Dışı',
                        'word_count': 0
                    }
                level_stats_all['Seviye Dışı']['word_count'] += 1
        
        # Generate title
        if series == 'friends':
            title = f"Friends - {season}x{episode:02d}"
        else:
            title = f"Big Bang Theory - {season}x{episode:02d}"
        
        return jsonify({
            'success': True,
            'video': {
                'id': 0,
                'title': title,
                'filename': title,
                'word_count': total
            },
            'flashcards': flashcards,
            'total_cards': len(flashcards),
            'known_count': known_count,
            'unknown_count': unknown_count,
            'level_stats': level_stats,  # Package_words'teki kelimeler için
            'level_stats_all': level_stats_all  # Tüm kelimeler için (seviye dışı dahil)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== CUSTOM SERIES ROUTES =====

@app.route('/api/custom-series', methods=['GET'])
def get_custom_series() -> Tuple[Response, int]:
    """Get all custom series"""
    try:
        series_list = db.get_custom_series()
        return jsonify({
            'success': True,
            'series': series_list
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/custom-series/add', methods=['POST'])
def add_custom_series() -> Tuple[Response, int]:
    """Add a new custom series from a video URL"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    video_url = data.get('url')
    series_name = data.get('name')
    icon = data.get('icon', '🎬')
    user_id = data.get('user_id')
    
    if not video_url or not series_name:
        return jsonify({'success': False, 'error': 'URL ve dizi adı gerekli'}), 400
    
    try:
        import re
        import sqlite3
        from collections import Counter
        
        # Generate series_id from name
        series_id = re.sub(r'[^a-z0-9]', '_', series_name.lower().strip())
        series_id = re.sub(r'_+', '_', series_id).strip('_')
        
        if not series_id:
            series_id = f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Check if series already exists
        existing = db.get_custom_series_by_id(series_id)
        if existing:
            return jsonify({'success': False, 'error': f'"{series_name}" adında bir dizi zaten mevcut'}), 400
        
        # Create folder for this series
        subtitles_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Subtitles")
        series_folder = os.path.join(subtitles_base, f"{series_id}_db")
        os.makedirs(series_folder, exist_ok=True)
        
        print(f"🎬 Processing video from URL: {video_url}")
        print(f"📁 Series folder: {series_folder}")
        
        # Process video from URL
        result = speech_processor.process_video_from_url(video_url)
        
        if not result or not result[0]:
            return jsonify({'success': False, 'error': 'Video indirilemedi veya işlenemedi'}), 500
        
        filename = result[0]
        words_set = result[1]
        transcript = result[2]
        
        if not transcript or len(transcript.strip()) < 10:
            return jsonify({'success': False, 'error': 'Video transkripti alınamadı veya çok kısa'}), 500
        
        # Save transcript to file
        transcript_filename = f"{series_id}_episode_1.txt"
        transcript_path = os.path.join(series_folder, transcript_filename)
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        print(f"📝 Transcript saved: {transcript_path}")
        
        # Extract words and calculate frequencies
        cleaned_transcript = re.sub(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', ' ', transcript)
        cleaned_transcript = re.sub(r'<[^>]+>', ' ', cleaned_transcript)
        cleaned_transcript = re.sub(r'\[[^\]]*\]', ' ', cleaned_transcript)
        
        transcript_words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", cleaned_transcript.lower())
        filtered_words = [w for w in transcript_words if len(w) > 1 or w in ['a', 'i']]
        word_counts = Counter(filtered_words)
        
        # Create episode database
        db_filename = f"{series_id}_episode_1.db"
        db_path = os.path.join(series_folder, db_filename)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""
            CREATE TABLE word_frequencies (
                word TEXT PRIMARY KEY,
                frequency INTEGER NOT NULL
            )
        """)
        
        cursor.execute("DROP TABLE IF EXISTS episode_info")
        cursor.execute("""
            CREATE TABLE episode_info (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('filename', filename))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('total_words', str(len(filtered_words))))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('unique_words', str(len(word_counts))))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('source_url', video_url))
        
        sorted_data = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        cursor.executemany("INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)", sorted_data)
        
        conn.commit()
        conn.close()
        
        print(f"🗄️ Database created: {db_path}")
        print(f"📊 Total words: {len(filtered_words)}, Unique words: {len(word_counts)}")
        
        # Generate a nice gradient color
        gradients = [
            'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
            'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
            'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
            'linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)',
            'linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%)',
        ]
        import random
        gradient = random.choice(gradients)
        
        # Add to custom_series table
        display_name = f"{icon} {series_name}"
        series_db_id = db.add_custom_series(
            series_id=series_id,
            name=series_name,
            display_name=display_name,
            db_folder_path=series_folder,
            icon=icon,
            gradient=gradient,
            source_url=video_url,
            created_by=user_id
        )
        
        if series_db_id:
            db.update_custom_series_episodes(series_id, 1)
        
        return jsonify({
            'success': True,
            'series_id': series_id,
            'name': series_name,
            'display_name': display_name,
            'icon': icon,
            'gradient': gradient,
            'db_folder': series_folder,
            'word_count': len(filtered_words),
            'unique_words': len(word_counts),
            'message': f'"{series_name}" başarıyla eklendi! {len(word_counts)} benzersiz kelime işlendi.'
        }), 200
        
    except Exception as e:
        print(f"Error adding custom series: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/custom-series/<series_id>/episodes', methods=['GET'])
def get_custom_series_episodes(series_id: str) -> Tuple[Response, int]:
    """Get episodes for a custom series"""
    import sqlite3
    try:
        series = db.get_custom_series_by_id(series_id)
        if not series:
            return jsonify({'success': False, 'error': 'Series not found'}), 404
        
        db_folder = series['db_folder_path']
        episodes = []
        
        if os.path.exists(db_folder):
            for filename in sorted(os.listdir(db_folder)):
                if filename.endswith('.db'):
                    db_path = os.path.join(db_folder, filename)
                    episode_name = filename.replace('.db', '').replace(f'{series_id}_', '')
                    
                    # Get word count from db
                    try:
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT value FROM episode_info WHERE key = 'unique_words'")
                        row = cursor.fetchone()
                        word_count = int(row[0]) if row else 0
                        conn.close()
                    except:
                        word_count = 0
                    
                    episodes.append({
                        'episode_file': filename,
                        'episode_name': episode_name,
                        'db_path': db_path,
                        'word_count': word_count,
                        'has_db': True
                    })
        
        return jsonify({
            'success': True,
            'series': series,
            'episodes': episodes,
            'count': len(episodes)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/custom-series/<series_id>/add-episode', methods=['POST'])
def add_custom_series_episode(series_id: str) -> Tuple[Response, int]:
    """Add a new episode to an existing custom series"""
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    video_url = data.get('url')
    episode_name = data.get('episode_name', '')
    
    if not video_url:
        return jsonify({'success': False, 'error': 'Video URL gerekli'}), 400
    
    try:
        import re
        import sqlite3
        from collections import Counter
        
        series = db.get_custom_series_by_id(series_id)
        if not series:
            return jsonify({'success': False, 'error': 'Series not found'}), 404
        
        series_folder = series['db_folder_path']
        
        # Get next episode number
        existing_episodes = [f for f in os.listdir(series_folder) if f.endswith('.db')] if os.path.exists(series_folder) else []
        episode_num = len(existing_episodes) + 1
        
        if not episode_name:
            episode_name = f"episode_{episode_num}"
        
        print(f"🎬 Adding episode {episode_num} to {series_id}")
        
        # Process video
        result = speech_processor.process_video_from_url(video_url)
        
        if not result or not result[0]:
            return jsonify({'success': False, 'error': 'Video indirilemedi'}), 500
        
        filename = result[0]
        transcript = result[2]
        
        if not transcript or len(transcript.strip()) < 10:
            return jsonify({'success': False, 'error': 'Transkript alınamadı'}), 500
        
        # Save transcript
        transcript_filename = f"{series_id}_{episode_name}.txt"
        transcript_path = os.path.join(series_folder, transcript_filename)
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        # Extract words
        cleaned_transcript = re.sub(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', ' ', transcript)
        cleaned_transcript = re.sub(r'<[^>]+>', ' ', cleaned_transcript)
        cleaned_transcript = re.sub(r'\[[^\]]*\]', ' ', cleaned_transcript)
        
        transcript_words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", cleaned_transcript.lower())
        filtered_words = [w for w in transcript_words if len(w) > 1 or w in ['a', 'i']]
        word_counts = Counter(filtered_words)
        
        # Create database
        db_filename = f"{series_id}_{episode_name}.db"
        db_path = os.path.join(series_folder, db_filename)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""
            CREATE TABLE word_frequencies (
                word TEXT PRIMARY KEY,
                frequency INTEGER NOT NULL
            )
        """)
        
        cursor.execute("DROP TABLE IF EXISTS episode_info")
        cursor.execute("""
            CREATE TABLE episode_info (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('filename', filename))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('total_words', str(len(filtered_words))))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('unique_words', str(len(word_counts))))
        cursor.execute("INSERT INTO episode_info VALUES (?, ?)", ('source_url', video_url))
        
        sorted_data = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        cursor.executemany("INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)", sorted_data)
        
        conn.commit()
        conn.close()
        
        # Update episode count
        db.update_custom_series_episodes(series_id, episode_num)
        
        return jsonify({
            'success': True,
            'episode_name': episode_name,
            'episode_number': episode_num,
            'word_count': len(filtered_words),
            'unique_words': len(word_counts),
            'message': f'Bölüm {episode_num} eklendi!'
        }), 200
        
    except Exception as e:
        print(f"Error adding episode: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/custom-series/<series_id>/delete', methods=['DELETE'])
def delete_custom_series(series_id: str) -> Tuple[Response, int]:
    """Delete a custom series and its files"""
    try:
        series = db.get_custom_series_by_id(series_id)
        if not series:
            return jsonify({'success': False, 'error': 'Series not found'}), 404
        
        # Delete folder and files
        db_folder = series['db_folder_path']
        if os.path.exists(db_folder):
            import shutil
            shutil.rmtree(db_folder)
        
        # Delete from database
        db.delete_custom_series(series_id)
        
        return jsonify({
            'success': True,
            'message': f'{series["name"]} silindi'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/custom-series/<series_id>/flashcards', methods=['GET'])
def get_custom_series_flashcards(series_id: str) -> Tuple[Response, int]:
    """Get flashcards for a custom series episode"""
    try:
        import sqlite3
        
        series = db.get_custom_series_by_id(series_id)
        if not series:
            return jsonify({'success': False, 'error': 'Series not found'}), 404
        
        episode = request.args.get('episode', 'episode_1')
        user_id_str = request.args.get('user_id')
        user_id = int(user_id_str) if user_id_str else None
        
        db_folder = series['db_folder_path']
        db_path = os.path.join(db_folder, f"{series_id}_{episode}.db")
        
        if not os.path.exists(db_path):
            # Try without series_id prefix
            for f in os.listdir(db_folder):
                if f.endswith('.db'):
                    db_path = os.path.join(db_folder, f)
                    break
        
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'error': 'Episode not found'}), 404
        
        # Read words from episode database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT word, frequency FROM word_frequencies ORDER BY frequency DESC")
        word_rows = cursor.fetchall()
        conn.close()
        
        flashcards = []
        known_count = 0
        unknown_count = 0
        
        for word, frequency in word_rows:
            # Check if user knows this word
            word_id = db.get_word_id(word) if hasattr(db, 'get_word_id') else None
            
            if word_id is None:
                # Add word to main database
                word_id = db.get_or_add_word(word)
            
            known = False
            if user_id and word_id:
                main_conn = db.get_connection()
                main_cursor = main_conn.cursor()
                main_cursor.execute(
                    'SELECT known FROM user_words WHERE user_id = ? AND word_id = ?',
                    (user_id, word_id)
                )
                row = main_cursor.fetchone()
                known = row['known'] == 1 if row else False
                main_conn.close()
            
            if known:
                known_count += 1
            else:
                unknown_count += 1
                
                # Get definition
                definition = ''
                pronunciation = ''
                if word_id:
                    main_conn = db.get_connection()
                    main_cursor = main_conn.cursor()
                    main_cursor.execute(
                        'SELECT definition, pronunciation FROM words WHERE id = ?',
                        (word_id,)
                    )
                    row = main_cursor.fetchone()
                    if row:
                        definition = row['definition'] or ''
                        pronunciation = row['pronunciation'] or ''
                    main_conn.close()
                
                flashcards.append({
                    'id': word_id,
                    'word': word,
                    'definition': definition,
                    'pronunciation': pronunciation,
                    'frequency': frequency,
                    'known': False
                })
        
        return jsonify({
            'success': True,
            'series': series,
            'episode': episode,
            'flashcards': flashcards,
            'total_cards': len(flashcards),
            'known_count': known_count,
            'unknown_count': unknown_count
        }), 200
        
    except Exception as e:
        print(f"Error getting custom series flashcards: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, debug=False, port=port, host='0.0.0.0', allow_unsafe_werkzeug=True) 
    
