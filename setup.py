#!/usr/bin/env python3
"""
Watch Together - Film İzle Beraber
Setup script - Kurulum Scripti
"""

import os
import sys
import subprocess
import platform

def print_header():
    print("\n" + "="*50)
    print("🎬 Watch Together - Film İzle Beraber")
    print("Kurulum Scriptı")
    print("="*50 + "\n")

def check_python_version():
    """Python versiyonunu kontrol et"""
    print("✓ Python versiyonu kontrol ediliyor...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ gerekli. Mevcut: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor} - Uygun\n")
    return True

def create_venv():
    """Sanal ortam oluştur"""
    print("✓ Sanal ortam oluşturuluyor...")
    if os.path.exists("venv"):
        print("⚠️  Sanal ortam zaten var\n")
        return True
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Sanal ortam oluşturuldu\n")
        return True
    except subprocess.CalledProcessError:
        print("❌ Sanal ortam oluşturulamadı\n")
        return False

def install_packages():
    """Paketleri yükle"""
    print("✓ Paketler yükleniyor...")
    
    # Sanal ortamın komutunu belirle
    if platform.system() == "Windows":
        pip_cmd = os.path.join("venv", "Scripts", "pip")
    else:
        pip_cmd = os.path.join("venv", "bin", "pip")
    
    if not os.path.exists(pip_cmd):
        print("❌ Pip komutu bulunamadı\n")
        return False
    
    try:
        subprocess.run(
            [pip_cmd, "install", "-r", "english-learning-app/requirements.txt"],
            check=True,
            cwd="."
        )
        print("✅ Paketler yüklendi\n")
        return True
    except subprocess.CalledProcessError:
        print("❌ Paketler yüklenemedi\n")
        return False

def create_database():
    """Veritabanını oluştur"""
    print("✓ Veritabanı oluşturuluyor...")
    try:
        os.chdir("english-learning-app")
        from database import Database
        db = Database()
        print("✅ Veritabanı oluşturuldu\n")
        os.chdir("..")
        return True
    except Exception as e:
        print(f"❌ Veritabanı oluşturulamadı: {e}\n")
        os.chdir("..")
        return False

def main():
    print_header()
    
    # Kontroller
    if not check_python_version():
        sys.exit(1)
    
    if not create_venv():
        sys.exit(1)
    
    if not install_packages():
        sys.exit(1)
    
    if not create_database():
        print("⚠️  Veritabanı oluşturmada hata oldu ama devam etilebilir")
    
    print("="*50)
    print("✅ Kurulum Tamamlandı!")
    print("="*50 + "\n")
    
    print("🚀 Uygulamayı başlatmak için:\n")
    
    if platform.system() == "Windows":
        print("  venv\\Scripts\\activate")
        print("  cd english-learning-app")
        print("  python app.py\n")
        print("Tarayıcıda açın: http://localhost:5000")
    else:
        print("  source venv/bin/activate")
        print("  cd english-learning-app")
        print("  python app.py\n")
        print("Tarayıcıda açın: http://localhost:5000")
    
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
