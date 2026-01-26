import os
import re
from typing import List, Set, Tuple, Optional
import subprocess
import tempfile
import shutil
import glob

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

class SpeechProcessor:
    def __init__(self):
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'it', 'as', 'if', 'that', 'this', 'what',
            'which', 'who', 'when', 'where', 'why', 'how', 'up', 'down', 'out', 'so',
            'than', 'then', 'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'her', 'our', 'their', 'there', 'here',
            'just', 'only', 'very', 'no', 'not', 'don', 't', 's', 're', 've', 'll', 'd',
            'm', 'am', 'im', 'dont', 'doesnt', 'wont', 'cant', 'shouldnt', 'wouldnt',
            'couldnt', 'hasnt', 'havent', 'isnt', 'arent', 'wasnt', 'werent', 'oh',
            'ah', 'um', 'like', 'well', 'really', 'actually', 'basically', 'actually'
        }
        self.model = None
    
    def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Extract audio from video file using ffmpeg"""
        audio_path = video_path.replace(os.path.splitext(video_path)[1], '.wav')
        
        try:
            cmd = [
                'ffmpeg', '-i', video_path,
                '-q:a', '9', '-n',
                '-loglevel', 'error',
                audio_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_path
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None
    
    def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """Transcribe audio file using local Whisper model"""
        try:
            import whisper
            if self.model is None:
                self.model = whisper.load_model("base")
            result = self.model.transcribe(audio_path)
            return result["text"]
        except Exception as e:
            print(f"Error transcribing with local Whisper: {e}")
            return None
    
    def extract_words(self, text: str) -> Set[str]:
        """Extract unique words from text"""
        # Convert to lowercase and remove punctuation
        text = text.lower()
        # Keep only alphabetic characters and spaces
        text = re.sub(r"[^a-z\s']", "", text)
        # Split into words
        words = text.split()
        
        # Filter out stop words and short words
        words = {
            word.strip("'") for word in words 
            if len(word.strip("'")) > 2 and word.strip("'") not in self.stop_words
        }
        
        return words
    
    def process_video(self, video_path: str) -> Tuple[Set[str], str]:
        """Process video file and extract unique words"""
        print(f"Processing video: {video_path}")
        
        # Extract audio
        audio_path = self.extract_audio_from_video(video_path)
        if not audio_path:
            print(f"Failed to extract audio from {video_path}")
            return set(), ""
        
        # Transcribe
        text = self.transcribe_audio(audio_path)
        if not text:
            print(f"Failed to transcribe audio from {video_path}")
            return set(), ""
        
        print(f"Transcription: {text[:200]}...")
        
        # Extract words
        words = self.extract_words(text)
        
        # Cleanup audio file
        try:
            os.remove(audio_path)
        except:
            pass
        
        return words, text
    
    def process_directory(self, directory: str, skip_filenames: Set[str] = None) -> List[Tuple[str, Set[str], str]]:
        """Process all videos in directory"""
        results = []
        
        if skip_filenames is None:
            skip_filenames = set()
        
        # Video extensions to look for
        video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv')
        subtitle_extensions = ('.srt', '.vtt')
        
        if not os.path.exists(directory):
            print(f"Directory not found: {directory}")
            return results
        
        for filename in os.listdir(directory):
            if filename in skip_filenames:
                print(f"Skipping already processed video: {filename}")
                continue
                
            if filename.lower().endswith(video_extensions):
                video_path = os.path.join(directory, filename)
                words, transcript = self.process_video(video_path)
                results.append((filename, words, transcript))
            elif filename.lower().endswith(subtitle_extensions):
                file_path = os.path.join(directory, filename)
                print(f"Processing subtitle file: {filename}")
                transcript = self.parse_subtitle_file(file_path)
                if transcript:
                    words = self.extract_words(transcript)
                    results.append((filename, words, transcript))
        
        return results
    
    def download_video_from_url(self, video_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download video from URL (YouTube, Vimeo, Dailymotion, etc.) using yt-dlp"""
        if not yt_dlp:
            print("Error: yt-dlp not installed")
            return None, None
        
        try:
            # Create temporary directory for download
            temp_dir = tempfile.mkdtemp()
            
            ydl_opts = {
                'format': 'best[ext=mp4]/best[ext=webm]/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'socket_timeout': 60,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                },
                'referer': 'https://www.google.com/',
                'cookie_file': None,
                'proxy': None,
                # Farklı siteler için ayarlar
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['js', 'configs']
                    },
                    'vimeo': {},  # Vimeo extract_args
                    'dailymotion': {},  # Dailymotion extract_args
                    'generic': {
                        'prefer_free_formats': True
                    }
                },
                # SSL ve bağlantı ayarları
                'skip_unavailable_fragments': True,
                'fragment_retries': 10,
                'retries': 10,
                'file_access_retries': 10,
                'noprogress': False,
                'verbose': True,
                'ignoreerrors': False,
                'default_search': 'auto',
                'playlistend': 1,  # Playlist ise sadece ilk videoyu indir
                # Alt yazı ayarları
                'writesubtitles': True,       # Alt yazıları indir
                'writeautomaticsub': True,    # Otomatik alt yazıları da indir (YouTube vb. için)
                'subtitleslangs': ['en', 'en-US', 'en-GB'], # Sadece İngilizce
            }
            
            print(f"📥 Video indiriliyor: {video_url}")
            
            video_file = None
            subtitle_file = None
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(video_url, download=True)
                except Exception as extract_error:
                    print(f"⚠️ İlk deneme başarısız: {extract_error}")
                    # Fallback: Format seçimini basitleştir
                    ydl_opts['format'] = 'best'
                    ydl_opts['ignoreerrors'] = True
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                            info = ydl_fallback.extract_info(video_url, download=True)
                    except:
                        print("❌ Fallback da başarısız oldu")
                        return None, None
                
                # Playlist yapısı halinde dönerse ilk videoyu al
                if isinstance(info, dict):
                    if 'entries' in info and isinstance(info['entries'], list) and len(info['entries']) > 0:
                        info = info['entries'][0]
                    
                    if isinstance(info, dict) and 'ext' in info:
                        video_file = ydl.prepare_filename(info)
                elif isinstance(info, str):
                    # Info doğrudan dosya yoluysa
                    video_file = info
            
            # Dosya kontrolleri
            if not video_file:
                print("❌ Hata: Video dosyası belirlenemedi")
                return None, None
                
            if not os.path.exists(video_file):
                print(f"❌ Hata: İndirilen dosya bulunamadı: {video_file}")
                # Temp dizinde başka video dosyası var mı?
                video_files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.webm', '.mkv', '.avi'))]
                if video_files:
                    print(f"⚠️ Dosya yolu hatalı, {len(video_files)} video dosyası bulundu")
                    video_file = os.path.join(temp_dir, video_files[0])
                else:
                    print("❌ Temp dizinde video dosyası yok")
                    return None, None
            
            if os.path.getsize(video_file) == 0:
                print("❌ Hata: İndirilen dosya boş")
                return None, None
            
            # Alt yazı dosyası kontrolü (.vtt veya .srt)
            # yt-dlp video ismine benzer isim verir: video.en.vtt gibi
            base_name = os.path.splitext(os.path.basename(video_file))[0]
            all_subs = glob.glob(os.path.join(temp_dir, f"{base_name}*.vtt")) + \
                       glob.glob(os.path.join(temp_dir, f"{base_name}*.srt"))
            
            if all_subs:
                # İngilizce işaretli olanları önceliklendir (.en.vtt gibi)
                english_subs = [s for s in all_subs if '.en' in os.path.basename(s).lower()]
                if english_subs:
                    subtitle_file = english_subs[0]
                else:
                    subtitle_file = all_subs[0]
                print(f"✅ Alt yazı bulundu: {os.path.basename(subtitle_file)}")
                
            print(f"✅ Video indirildi: {os.path.basename(video_file)} ({os.path.getsize(video_file) / (1024*1024):.1f} MB)")
            return video_file, subtitle_file
        
        except Exception as e:
            print(f"❌ Video indirme hatası: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def parse_subtitle_text(self, content: str) -> str:
        """Parse subtitle content string to plain text"""
        try:
            lines = content.splitlines()
            text_lines = []
            
            # Basit VTT/SRT temizleme
            for line in lines:
                line = line.strip()
                # Zaman damgalarını atla (00:00:00.000 --> ...)
                if '-->' in line:
                    continue
                # Sayısal indeksleri atla (sadece sayı olan satırlar)
                if line.isdigit():
                    continue
                # WEBVTT başlığını atla
                if line == 'WEBVTT' or line.startswith('Kind:') or line.startswith('Language:'):
                    continue
                # Boş satırları atla
                if not line:
                    continue
                # HTML taglerini temizle (<c>, <i>, <b> vb.)
                line = re.sub(r'<[^>]+>', '', line)
                # Remove { ... } style tags often found in some SRTs
                line = re.sub(r'\{[^}]+\}', '', line)
                
                # Tekrar eden satırları engelle (bazı vtt'lerde olur)
                if text_lines and text_lines[-1] == line:
                    continue
                    
                text_lines.append(line)
            
            return ' '.join(text_lines)
        except Exception as e:
            print(f"Error parsing subtitle text: {e}")
            return ""

    def parse_subtitle_file(self, subtitle_path: str) -> str:
        """Parse VTT or SRT subtitle file to plain text"""
        try:
            with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.parse_subtitle_text(content)
        except Exception as e:
            print(f"Error reading subtitle file: {e}")
            return ""
    
    def process_video_from_url(self, video_url: str) -> Tuple[Optional[str], Set[str], str]:
        """Process video from URL and return (filename, words)"""
        video_path, subtitle_path = self.download_video_from_url(video_url)

        if not video_path:
            return None, set(), ""

        temp_dir = os.path.dirname(video_path)

        try:
            transcript = ""
            words = set()

            # Eğer alt yazı indiyse onu kullan (Whisper'dan çok daha hızlıdır)
            if subtitle_path and os.path.exists(subtitle_path):
                print("📝 İndirilen alt yazı dosyası işleniyor...")
                transcript = self.parse_subtitle_file(subtitle_path)
                if transcript:
                    words = self.extract_words(transcript)
                    print(f"✅ Alt yazıdan {len(words)} kelime çıkarıldı.")

            # Alt yazı yoksa veya boşsa Whisper ile sesi yazıya dök
            if not transcript:
                print("🎙️ Alt yazı bulunamadı, ses işleniyor (Whisper)...")
                words, transcript = self.process_video(video_path)

            filename = os.path.basename(video_path)
            return filename, words, transcript
        except Exception as e:
            print(f"Error processing video from URL: {e}")
            return None, set(), ""
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"Error cleaning up temp directory {temp_dir}: {e}")
