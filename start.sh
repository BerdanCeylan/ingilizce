#!/bin/bash
# Watch Together - Film İzle Beraber Başlat
# Start script for the Watch Together application

echo "🎬 Watch Together - Film İzle Beraber Başlatılıyor..."

# Sanal ortamı kontrol et
if [ ! -d "venv" ]; then
    echo "❌ Sanal ortam bulunamadı. Lütfen venv/bin/activate'i kontrol edin."
    exit 1
fi

# Sanal ortamı aktif et
source venv/bin/activate

# Flask uygulamasını başlat
cd english-learning-app

# Eski process'leri temizle
echo "⏹️  Eski process'ler temizleniyor..."
lsof -i :5000 -t 2>/dev/null | xargs kill -9 2>/dev/null

sleep 1

echo "✅ Sanal ortam aktif edildi."
echo "🚀 Flask uygulaması başlatılıyor..."

# Flask'ı arka planda başlat
python app.py &
FLASK_PID=$!

# Flask'ın başlaması için bekle
sleep 3

# Tarayıcıyı aç
echo "🌐 Tarayıcı açılıyor..."
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:5000 &
elif command -v open > /dev/null; then
    open http://localhost:5000 &
elif command -v firefox > /dev/null; then
    firefox http://localhost:5000 &
elif command -v chromium > /dev/null; then
    chromium http://localhost:5000 &
else
    echo "⚠️  Tarayıcı bulunamadı. Lütfen http://localhost:5000 adresini manuel olarak açın."
fi

echo "✅ Uygulama çalışıyor: http://localhost:5000"
echo "📌 Uygulamayı durdurmak için CTRL+C basın"
echo ""

# Flask'ın çalışmasını bekleme
wait $FLASK_PID

# Sonlandırma mesajı
echo ""
echo "❌ Uygulama durduruldu."
deactivate
