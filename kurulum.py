"""
Kişisel hesabı kuran tek seferlik script.

- vjook444@gmail.com hesabını oluşturur (varsa şifresini günceller)
- .env'deki WhatsApp tokenını ve phone_id'yi bu hesabın ayarlarına yazar
- Webhook bu hesaba düşecek şekilde tenant'ı eşler

Çalıştırma:
    py kurulum.py
"""

import os
import sqlite3
from dotenv import load_dotenv

from src.database.local_db import (
    init_db, get_tenant_by_email, create_tenant,
    update_tenant_settings, get_tenant_settings, DB_PATH,
)
from src.auth.security import hash_password

load_dotenv()

EMAIL = "vjook444@gmail.com"
PASSWORD = "mleach123@#"
OFFICE_NAME = "EmlakBot"
CONTACT_NAME = "Yusuf Gök"
BOT_TONE = "profesyonel"
SYSTEM_PROMPT_EXTRAS = ""


def main():
    init_db()

    existing = get_tenant_by_email(EMAIL)
    new_hash = hash_password(PASSWORD)

    if existing:
        tid = existing["id"]
        # Var olan hesabı güncelle
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE tenants SET password_hash=?, office_name=?, contact_name=? WHERE id=?",
                (new_hash, OFFICE_NAME, CONTACT_NAME, tid),
            )
            conn.commit()
        print(f"Hesap güncellendi (id={tid})")
    else:
        tid = create_tenant(
            email=EMAIL,
            password_hash=new_hash,
            office_name=OFFICE_NAME,
            contact_name=CONTACT_NAME,
        )
        print(f"Yeni hesap oluşturuldu (id={tid})")

    # WhatsApp bilgilerini .env'den al ve bu tenant'a yaz
    wa_token = os.getenv("WHATSAPP_TOKEN", "")
    wa_phone_id = os.getenv("WHATSAPP_PHONE_ID", "")
    wa_business_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")

    settings = get_tenant_settings(tid)
    settings.update({
        "whatsapp_token": wa_token,
        "whatsapp_phone_id": wa_phone_id,
        "whatsapp_business_account_id": wa_business_id,
        "bot_tone": BOT_TONE,
        "system_prompt_extras": SYSTEM_PROMPT_EXTRAS,
    })
    update_tenant_settings(tid, settings)
    print(f"WhatsApp ayarları kaydedildi (phone_id={wa_phone_id})")

    print()
    print("=" * 50)
    print("  Hesabın hazır!")
    print(f"  E-posta: {EMAIL}")
    print(f"  Şifre:   {PASSWORD}")
    print()
    print("  Login:    http://localhost:8000/login")
    print("  Sonra:    http://localhost:8000/app/settings")
    print("=" * 50)


if __name__ == "__main__":
    main()
