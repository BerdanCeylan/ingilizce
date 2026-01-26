# 🎬 Watch Together - Film İzle Beraber

Arkadaşlarınızla **eş zamanlı film izleme**, **sohbet**, **ekran paylaşma** ve **video senkronizasyonu** özelliklerine sahip bir web uygulaması.

## ✨ Özellikler

### 1. 📺 Film İzleme Odaları
- Yeni oda oluşturun veya mevcut odalara katılın
- Kaç kişi katıldığını görün
- Oda yöneticisi tarafından video URL'i ayarlanabilir

### 2. 💬 Canlı Sohbet
- Odadaki tüm üyelerle gerçek zamanlı sohbet
- Socket.IO aracılığıyla anlık mesaj gönderme/alma
- Sohbet geçmişi görüntüle

### 3. ▶️ Video Senkronizasyonu
- Bir kişi play/pause/seek yaparsa diğer herkese senkronize olur
- Eş zamanlı film izleme deneyimi
- Toleranslı senkronizasyon (0.5 saniye)

### 4. 📺 Ekran Paylaşma (WebRTC)
- Chrome/Edge'den ekranınızı paylaşın
- WebRTC ile P2P bağlantı
- STUN sunucularla NAT traversal

### 5. 👥 Kullanıcı Yönetimi
- Kullanıcı adı ile giriş yapın
- Odalara katılın/ayrılın
- Profil sayfasında istatistikler görün

### 6. 📚 İngilizce Öğrenme (Eski Özellik)
- Videoları işleyerek kelimeleri çıkartın
- Kelime bilgisi takibi
- İstatistikler

## 🚀 Kurulum

### Gereksinimler
- Python 3.8+
- pip

### Adımlar

```bash
# 1. Sanal ortam oluştur
python -m venv venv

# 2. Sanal ortamı aktif et
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows

# 3. Paketleri kur
pip install -r requirements.txt

# 4. Uygulamayı başlat
python app.py
```

## 🌐 Kullanım

1. **Tarayıcıda açın:** `http://localhost:5000`
2. **Kullanıcı adınızı girin** ve giriş yapın
3. **Oda Seçin:**
   - Mevcut odalardan birine katılın veya
   - Yeni oda oluşturun
4. **Film İzleyin:**
   - Video oynatıcıyı kontrol edin (otomatik senkronize olur)
   - Sohbet et
   - Ekran paylaş (WebRTC)

## 🏗️ Proje Yapısı

```
english-learning-app/
├── app.py                 # Flask + SocketIO backend
├── database.py            # SQLite veritabanı işlemleri
├── speech_processor.py    # Video işleme (Whisper)
├── requirements.txt       # Python paketleri
├── templates/
│   └── index.html        # Ana HTML (yeni UI)
├── static/
│   ├── css/
│   │   └── style.css     # CSS stilleri
│   └── js/
│       └── app.js        # Frontend JavaScript (Socket.IO)
└── learning.db           # SQLite veritabanı
```

## 🔧 Teknik Detaylar

### Backend (Flask + Socket.IO)

**API Endpoints:**
- `POST /api/users` - Kullanıcı oluştur/giriş yap
- `GET /api/rooms` - Aktif odaları listele
- `POST /api/rooms` - Yeni oda oluştur
- `GET /api/rooms/<id>` - Oda detaylarını getir
- `POST /api/rooms/<id>/join` - Odaya katıl
- `POST /api/rooms/<id>/leave` - Odadan ayrıl

**Socket.IO Events:**
- `join_room` - Kullanıcı odaya katılır
- `leave_room` - Kullanıcı odadan ayrılır
- `send_message` - Sohbet mesajı gönder
- `video_sync` - Video senkronizasyonu
- `screen_share_start` - Ekran paylaşmaya başla
- `screen_share_stop` - Ekran paylaşmayı durdur
- `webrtc_offer/answer/ice_candidate` - WebRTC sinyal

### Database (SQLite)

Tablolar:
- `users` - Kullanıcılar
- `watch_rooms` - Film izleme odaları
- `room_members` - Oda üyeleri
- `chat_messages` - Sohbet mesajları
- `words` - Kelime veritabanı (öğrenme için)
- `user_words` - Kullanıcı kelimeleri
- `videos` - İşlenen videolar

### Frontend (Vanilla JavaScript)

Teknolojiler:
- Socket.IO client - Gerçek zamanlı iletişim
- WebRTC - Ekran paylaşma
- HTML5 Video API - Video kontrol

## 🔒 Güvenlik Notları

- Production için SECRET_KEY değiştirin (app.py)
- HTTPS kullanın (ekran paylaşma WebRTC için zorunlu)
- Database path'i güvenli bir yerde tutun
- CORS ayarlarını gereksinimlere göre güncelleyin

## 📝 Gelecek Geliştirmeler

- [ ] Kullanıcı kaydı ve şifre koruması
- [ ] Video dosyası yükleme
- [ ] Ses paylaşma
- [ ] Dinamik video çözünürlüğü
- [ ] Oda şifresi
- [ ] İstatistikler ve analitikler
- [ ] Mobil uygulaması
- [ ] Dosya paylaşma
- [ ] Emoji desteği

## 🐛 Sorun Giderme

### "Ekran paylaşma çalışmıyor"
- HTTPS üzerinde erişim sağlayın
- Tarayıcı izni verin
- Tarayıcı versiyonunu güncelleyin

### "Video senkronize olmuyor"
- WebSocket bağlantısını kontrol edin
- Network bağlantısını kontrol edin
- Browser konsolunda hata mesajlarını kontrol edin

### "Socket.IO hatası"
- Backend'in çalıştığından emin olun
- Port 5000'in açık olduğundan emin olun
- Socket.IO versiyonlarını kontrol edin

## 📞 İletişim

Sorularınız için lütfen bir issue açın.

## 📄 Lisans

MIT Lisansı altında yayınlanmıştır.

---

**Made with ❤️ for learning together**
