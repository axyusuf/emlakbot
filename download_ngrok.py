import urllib.request
import zipfile
import os

NGROK_URL = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
ZIP_PATH = "ngrok.zip"
EXE_PATH = "ngrok.exe"

def download_and_extract():
    if os.path.exists(EXE_PATH):
        print("✅ ngrok.exe zaten mevcut.")
        return

    print("ngrok indiriliyor...")
    urllib.request.urlretrieve(NGROK_URL, ZIP_PATH)
    print("ngrok arşivden çıkarılıyor...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(".")
    print("✅ ngrok başarıyla kuruldu!")

if __name__ == "__main__":
    download_and_extract()
