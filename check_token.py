import os
import httpx
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

def check_whatsapp_config():
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID or WHATSAPP_TOKEN == "your_meta_whatsapp_token":
        print("[HATA] WhatsApp token veya Phone ID henuz yapilandirilmamis (.env dosyasini kontrol edin).")
        return

    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                print("[BASARILI] WhatsApp API Token ve Phone ID gecerli! Baglanti basarili.")
                print(f"Detaylar: {response.json()}")
            else:
                print(f"[HATA] WhatsApp API Hatasi ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"[BAGLANTI HATASI] Baglanti hatasi: {e}")

if __name__ == "__main__":
    check_whatsapp_config()
