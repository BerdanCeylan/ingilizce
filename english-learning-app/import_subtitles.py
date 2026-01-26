#!/usr/bin/env python3
import os
import sys
from database import Database
from speech_processor import SpeechProcessor

def main():
    print("🎬 Alt Yazı İçe Aktarma Aracı")
    print("--------------------------------")
    
    if len(sys.argv) < 2:
        print("Kullanım: python import_subtitles.py <alt_yazi_klasoru> [user_id]")
        print("Örnek: python import_subtitles.py /home/user/Downloads/Friends 1")
        return

    directory = sys.argv[1]
    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    if not os.path.exists(directory):
        print(f"❌ Klasör bulunamadı: {directory}")
        return

    print(f"📂 Klasör taranıyor: {directory}")
    print(f"👤 Kullanıcı ID: {user_id}")

    db = Database()
    processor = SpeechProcessor()
    
    count = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.srt', '.vtt')):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, directory)
                print(f"   📄 İşleniyor: {rel_path}")
                
                try:
                    transcript = processor.parse_subtitle_file(file_path)
                    if not transcript or len(transcript.strip()) < 10:
                        print("      ⚠️ Boş veya geçersiz dosya, atlanıyor.")
                        continue
                        
                    words = processor.extract_words(transcript)
                    word_list = list(words)
                    
                    # Video kaydı oluştur (Transkript olarak)
                    title = f"Subtitle: {os.path.basename(file)}"
                    
                    video_id = db.add_video_record(
                        filename=os.path.basename(file),
                        word_count=len(word_list),
                        transcript=transcript,
                        video_url="",
                        title=title,
                        description=f"Imported from: {rel_path}"
                    )
                    
                    if video_id:
                        # Kelimeleri video ile ilişkilendir
                        for word in word_list:
                            word_id = db.get_or_add_word(word)
                            if word_id:
                                db.add_video_word(video_id, word_id)
                                # Not: Kullanıcı kelimeleri zaten words tablosunda olduğu için
                                # ve get_user_words artık hepsini getirdiği için
                                # add_user_word çağırmamıza gerek yok, ama ilişki kurmak için çağırabiliriz.
                                db.add_user_word(user_id, word_id)
                        
                        count += 1
                        print(f"      ✅ Eklendi ({len(word_list)} kelime)")
                        
                except Exception as e:
                    print(f"      ❌ Hata: {e}")

    print(f"\n🏁 Tamamlandı! Toplam {count} alt yazı dosyası işlendi ve veritabanına eklendi.")

if __name__ == "__main__":
    main()