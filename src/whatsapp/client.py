"""
WhatsApp Cloud API istemcisi — tenant başına farklı token desteği ile.

Eğer fonksiyona token/phone_id geçilirse onları kullanır. Geçilmezse .env'deki
global değerlere düşer (geliştirme için kolaylık). Hiçbiri yoksa simülasyon modu.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TOKEN = os.getenv("WHATSAPP_TOKEN")
DEFAULT_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _resolve(token: str | None, phone_id: str | None) -> tuple[str | None, str | None]:
    t = token or DEFAULT_TOKEN
    p = phone_id or DEFAULT_PHONE_ID
    if t == "your_meta_whatsapp_token":
        t = None
    return t, p


def send_whatsapp_message(to_phone: str, text: str,
                          token: str | None = None, phone_id: str | None = None):
    t, p = _resolve(token, phone_id)
    if not t or not p:
        safe_print(f"[WhatsApp Simülasyon → {to_phone}] {text}")
        return {"simulation": True, "status": "simulated", "message": text}

    url = f"https://graph.facebook.com/v17.0/{p}/messages"
    headers = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        with httpx.Client() as client:
            resp = client.post(url, headers=headers, json=data, timeout=10.0)
            if resp.status_code != 200:
                safe_print(f"WhatsApp mesaj hatası ({resp.status_code}): {resp.text}")
            else:
                safe_print(f"WhatsApp mesajı gönderildi -> {to_phone}")
            return resp.json()
    except Exception as e:
        safe_print(f"WhatsApp API bağlantı hatası: {e}")
        return None


def send_whatsapp_image(to_phone: str, image_url: str, caption: str = "",
                        token: str | None = None, phone_id: str | None = None):
    t, p = _resolve(token, phone_id)
    if not t or not p:
        safe_print(f"[WhatsApp Simülasyon → Resim {to_phone}] {image_url} | {caption}")
        return {"simulation": True}
    url = f"https://graph.facebook.com/v17.0/{p}/messages"
    headers = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    try:
        with httpx.Client() as client:
            resp = client.post(url, headers=headers, json=data, timeout=10.0)
            return resp.json()
    except Exception as e:
        safe_print(f"WhatsApp resim hatası: {e}")
        return None


def send_whatsapp_video(to_phone: str, video_url: str, caption: str = "",
                        token: str | None = None, phone_id: str | None = None):
    t, p = _resolve(token, phone_id)
    if not t or not p:
        safe_print(f"[WhatsApp Simülasyon → Video {to_phone}] {video_url} | {caption}")
        return {"simulation": True}
    url = f"https://graph.facebook.com/v17.0/{p}/messages"
    headers = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "video",
        "video": {"link": video_url, "caption": caption},
    }
    try:
        with httpx.Client() as client:
            resp = client.post(url, headers=headers, json=data, timeout=10.0)
            return resp.json()
    except Exception as e:
        safe_print(f"WhatsApp video hatası: {e}")
        return None
