# Görev Planı: Dizi Veri Seti Entegrasyonu

## Tamamlanan İşler

### ✅ 1. Database Metodları (database.py)
- `get_series_videos(series, season, episode)` - Diziye göre video filtreleme
- `get_series_stats(series, user_id)` - Dizi bazlı istatistikler
- `get_episode_flashcards(video_id, user_id)` - Bölüm flash kartları
- `mark_word_known(word_id, user_id, known)` - Kelime bilme durumu

### ✅ 2. API Endpoint'leri (app.py)
- `GET /api/series/<series>/videos` - Dizinin videolarını getir
- `GET /api/series/<series>/stats` - Dizi istatistiklerini getir
- `GET /api/series/<series>/episodes` - Tüm bölümleri listele
- `GET /api/episodes/<video_id>/flashcards` - Bölüm flash kartları

### ✅ 3. Frontend Güncellemeleri (templates/index.html)
- Friends posteri (mor gradient)
- Big Bang Theory posteri (pembe gradient)
- Sezon/Bölüm dropdown'ları
- Flash kart gösterimi

## Veri Kaynakları

### Friends (Subtitles/Friends1-10/)
- Format: friends.s01e01.720p.bluray.x264-psychd.srt
- Toplam: ~236 bölüm

### Big Bang Theory (Subtitles/BigBangTheory/)
- Format: series-1-episode-1-pilot-episode.txt
- Toplam: ~279 bölüm

## API Kullanımı

### Örnek İstekler:

```bash
# Friends tüm videolar
GET /api/series/friends/videos

# Friends Sezon 1 videolar
GET /api/series/friends/videos?season=1

# Friends istatistikleri
GET /api/series/friends/stats?user_id=1

# Big Bang Theory tüm bölümler
GET /api/series/bigbang/episodes

# Bölüm flash kartları
GET /api/episodes/123/flashcards?user_id=1
```

## Sonraki Adımlar
- [ ] Veritabanını sıfırdan oluşturma
- [ ] Friends altyazılarını işleyip veritabanına aktarma
- [ ] Big Bang Theory transkriptlerini işleyip veritabanına aktarma
- [ ] Frontend'de dizi istatistiklerini gösterme

