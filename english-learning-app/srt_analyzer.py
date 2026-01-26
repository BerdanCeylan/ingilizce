#!/usr/bin/env python3
import os
import re
import sqlite3
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict, Counter
import argparse

class SRTAnalyzer:
    def __init__(self, db_path: str = 'learning.db'):
        self.db_path = db_path
        self.word_levels: Dict[str, int] = {}
        self.word_frequencies: Dict[str, int] = {}
        self.load_word_database()
    
    def load_word_database(self):
        """Veritabanından kelimeleri ve seviyelerini yükler"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Öğrenme paketleri varsa onları kullan
            cursor.execute('''
                SELECT w.word, w.frequency, lp.package_number 
                FROM words w
                JOIN package_words pw ON w.id = pw.word_id
                JOIN learning_packages lp ON pw.package_id = lp.id
                ORDER BY w.frequency DESC
            ''')
            
            for row in cursor.fetchall():
                word = row[0].lower()
                self.word_levels[word] = row[2]  # package_number = level
                self.word_frequencies[word] = row[1]
                
        except sqlite3.OperationalError:
            # Öğrenme paketleri yoksa basit frekans tabanlı seviyendirme
            cursor.execute('SELECT word, frequency FROM words ORDER BY frequency DESC')
            words = cursor.fetchall()
            total_words = len(words)
            words_per_level = total_words // 10  # 10 seviye
            
            for i, (word, freq) in enumerate(words):
                level = (i // words_per_level) + 1 if words_per_level > 0 else 1
                self.word_levels[word.lower()] = min(level, 10)
                self.word_frequencies[word.lower()] = freq
        
        conn.close()
        print(f"✅ {len(self.word_levels)} kelime veritabanından yüklendi")
    
    def extract_words_from_srt(self, srt_content: str) -> List[str]:
        """SRT içeriğinden kelimeleri çıkarır"""
        # SRT formatındaki zaman damgaları ve numaraları temizle
        content = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', srt_content)
        content = re.sub(r'\d+\n', '', content)
        content = re.sub(r'<[^>]+>', '', content)  # HTML etiketlerini temizle
        content = re.sub(r'\([^)]*\)', '', content)  # Parantez içi açıklamaları temizle
        content = re.sub(r'\[[^\]]*\]', '', content)  # Köşeli parantez içi açıklamaları temizle
        
        # Kelimeleri ayıkla
        words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", content.lower())
        
        # Stop words ve çok kısa kelimeleri filtrele
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'among', 'under', 'over', 'i', 'you', 'he', 'she', 'it', 'we',
            'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their',
            'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
            'can', 'shall', 'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom',
            'whose', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
            'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
            'same', 'so', 'than', 'too', 'very', 'just', 'now', 'oh', 'yeah', 'yes', 'no'
        }
        
        filtered_words = [
            word for word in words 
            if len(word) >= 3 and word not in stop_words and not word.isdigit()
        ]
        
        return filtered_words
    
    def analyze_srt_file(self, file_path: str) -> Dict[str, Any]:
        """Tek bir SRT dosyasını analiz eder"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                    content = f.read()
            except:
                return {"error": f"Dosya okunamadı: {file_path}"}
        
        words = self.extract_words_from_srt(content)
        
        # Kelime sayımları
        word_counter = Counter(words)
        
        # Seviye bazında analiz
        level_stats: Dict[int, Dict[str, Any]] = {}
        unknown_words: List[Tuple[str, int]] = []  # (word, count)
        
        for word, count in word_counter.items():
            level = self.word_levels.get(word)
            if level:
                if level not in level_stats:
                    level_stats[level] = {
                        "words": [],
                        "total_count": 0,
                        "unique_words": 0
                    }
                level_stats[level]["words"].append((word, count))
                level_stats[level]["total_count"] += count
                level_stats[level]["unique_words"] += 1
            else:
                unknown_words.append((word, count))
        
        # Her seviyeyi kelime sayısına göre sırala
        for level in level_stats:
            level_stats[level]["words"].sort(key=lambda x: x[1], reverse=True)
        
        # Bilinmeyen kelimeleri sırala
        unknown_words.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "file_path": file_path,
            "total_words": len(words),
            "unique_words": len(word_counter),
            "level_stats": level_stats,
            "unknown_words": unknown_words[:50],  # İlk 50 bilinmeyen kelime
            "total_unknown_count": sum(count for _, count in unknown_words),
            "coverage_percentage": round(
                (sum(word_counter.get(word, 0) for word in self.word_levels.keys() if word in word_counter) / len(words) * 100) 
                if words else 0, 2
            )
        }
    
    def analyze_directory(self, directory_path: str, pattern: str = None) -> List[Dict[str, Any]]:
        """Dizindeki tüm SRT dosyalarını analiz eder"""
        if not os.path.exists(directory_path):
            print(f"❌ Dizin bulunamadı: {directory_path}")
            return []
        
        results = []
        srt_files = []
        
        # SRT dosyalarını bul
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith(('.srt', '.sub', '.vtt')):
                    if pattern is None or pattern.lower() in file.lower():
                        srt_files.append(os.path.join(root, file))
        
        print(f"🔍 {len(srt_files)} SRT dosyası bulundu")
        
        for i, file_path in enumerate(srt_files, 1):
            print(f"📄 [{i}/{len(srt_files)}] {os.path.basename(file_path)} analiz ediliyor...")
            result = self.analyze_srt_file(file_path)
            results.append(result)
        
        return results
    
    def generate_summary_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tüm analizler için özet rapor oluşturur"""
        total_files = len(results)
        total_words = sum(r.get("total_words", 0) for r in results)
        total_unique_words = sum(r.get("unique_words", 0) for r in results)
        total_unknown = sum(r.get("total_unknown_count", 0) for r in results)
        
        # Seviye bazında toplam istatistikler
        all_level_stats: Dict[int, Dict[str, Any]] = {}
        all_unknown_words: Counter = Counter()
        
        for result in results:
            # Seviye istatistiklerini topla
            for level, stats in result.get("level_stats", {}).items():
                if level not in all_level_stats:
                    all_level_stats[level] = {
                        "total_count": 0,
                        "unique_words": set(),
                        "files": []
                    }
                all_level_stats[level]["total_count"] += stats["total_count"]
                all_level_stats[level]["unique_words"].update([w[0] for w in stats["words"]])
                all_level_stats[level]["files"].append(os.path.basename(result["file_path"]))
            
            # Bilinmeyen kelimeleri topla
            for word, count in result.get("unknown_words", []):
                all_unknown_words[word] += count
        
        # Seviye istatistiklerini formatla
        for level in all_level_stats:
            all_level_stats[level]["unique_words"] = len(all_level_stats[level]["unique_words"])
        
        # En çok geçen bilinmeyen kelimeler
        top_unknown_words = all_unknown_words.most_common(50)
        
        return {
            "total_files": total_files,
            "total_words": total_words,
            "total_unique_words": total_unique_words,
            "total_unknown": total_unknown,
            "coverage_percentage": round(((total_words - total_unknown) / total_words * 100) if total_words > 0 else 0, 2),
            "level_stats": all_level_stats,
            "top_unknown_words": top_unknown_words,
            "files_analyzed": [os.path.basename(r["file_path"]) for r in results]
        }
    
    def print_detailed_report(self, results: List[Dict[str, Any]], show_unknown_words: bool = False, max_files: int = None):
        """Detaylı analiz raporu yazdırır"""
        if max_files:
            results = results[:max_files]
        
        print("\n" + "="*80)
        print("📊 FİLM BÖLÜM KELİME ANALİZ RAPORU")
        print("="*80)
        
        # Özet rapor
        summary = self.generate_summary_report(results)
        
        print(f"\n📈 GENEL ÖZET:")
        print(f"   • Analiz edilen dosya sayısı: {summary['total_files']}")
        print(f"   • Toplam kelime sayısı: {summary['total_words']:,}")
        print(f"   • Benzersiz kelime sayısı: {summary['total_unique_words']:,}")
        print(f"   • Bilinmeyen kelime sayısı: {summary['total_unknown']:,}")
        print(f"   • Kelime havuzu kapsama oranı: %{summary['coverage_percentage']}")
        
        print(f"\n📚 SEVİYE DAĞILIMI:")
        for level in sorted(summary['level_stats'].keys()):
            stats = summary['level_stats'][level]
            print(f"   • Level {level}: {stats['total_count']:,} kelime ({stats['unique_words']} benzersiz)")
        
        # Dosya bazında detaylar
        print(f"\n📄 DOSYA BAZINDA ANALİZ:")
        for i, result in enumerate(results, 1):
            filename = os.path.basename(result["file_path"])
            print(f"\n{i}. {filename}")
            print(f"   • Toplam kelime: {result['total_words']:,}")
            print(f"   • Benzersiz kelime: {result['unique_words']:,}")
            print(f"   • Bilinmeyen kelime: {result['total_unknown_count']:,}")
            print(f"   • Kapsama oranı: %{result['coverage_percentage']}")
            
            # Seviye dağılımı
            if result["level_stats"]:
                print("   • Seviye dağılımı:")
                for level in sorted(result["level_stats"].keys()):
                    stats = result["level_stats"][level]
                    print(f"     - Level {level}: {stats['total_count']} kelime ({stats['unique_words']} benzersiz)")
                
                # En çok geçen 5 kelime (en düşük seviyeden)
                lowest_level = min(result["level_stats"].keys())
                top_words = result["level_stats"][lowest_level]["words"][:5]
                print(f"   • En çok geçen kelimeler (Level {lowest_level}): {', '.join([f'{w}({c})' for w, c in top_words])}")
            
            # Bilinmeyen kelimeler
            if show_unknown_words and result["unknown_words"]:
                print(f"   • Bilinmeyen kelimeler (ilk 10): {', '.join([f'{w}({c})' for w, c in result['unknown_words'][:10]])}")
        
        # En çok geçen bilinmeyen kelimeler
        if summary["top_unknown_words"]:
            print(f"\n❓ EN ÇOK GEÇEN BİLİNMEYEN KELİMELER:")
            for i, (word, count) in enumerate(summary["top_unknown_words"][:20], 1):
                print(f"   {i:2d}. {word:<15} ({count} kez)")
        
        print("\n" + "="*80)

def main():
    """Ana fonksiyon - komut satırı arayüzü"""
    parser = argparse.ArgumentParser(description='SRT dosyalarını kelime seviyesine göre analiz eder')
    parser.add_argument('path', help='Analiz edilecek dosya veya dizin yolu')
    parser.add_argument('--pattern', '-p', help='Dosya adında arama deseni (örn: "s01e01")')
    parser.add_argument('--unknown', '-u', action='store_true', help='Bilinmeyen kelimeleri göster')
    parser.add_argument('--max-files', '-m', type=int, help='Maksimum gösterilecek dosya sayısı')
    parser.add_argument('--summary', '-s', action='store_true', help='Sadece özet rapor göster')
    
    args = parser.parse_args()
    
    analyzer = SRTAnalyzer()
    
    if os.path.isfile(args.path):
        # Tek dosya analizi
        print(f"📄 Dosya analiz ediliyor: {args.path}")
        result = analyzer.analyze_srt_file(args.path)
        analyzer.print_detailed_report([result], args.unknown, args.max_files)
    elif os.path.isdir(args.path):
        # Dizin analizi
        print(f"📁 Dizin analiz ediliyor: {args.path}")
        results = analyzer.analyze_directory(args.path, args.pattern)
        
        if results:
            if args.summary:
                summary = analyzer.generate_summary_report(results)
                print(f"\n📊 ÖZET RAPOR:")
                print(f"   • Toplam dosya: {summary['total_files']}")
                print(f"   • Toplam kelime: {summary['total_words']:,}")
                print(f"   • Kapsama oranı: %{summary['coverage_percentage']}")
            else:
                analyzer.print_detailed_report(results, args.unknown, args.max_files)
        else:
            print("❌ Analiz edilecek dosya bulunamadı")
    else:
        print(f"❌ Geçersiz yol: {args.path}")

if __name__ == "__main__":
    main()
