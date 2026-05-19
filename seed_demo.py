"""
Demo verisi: bir demo hesabı + örnek lead'ler oluşturur.
Satış sunumu/demo için kullanılır.

Çalıştırmak için:
    py seed_demo.py

Sonra http://localhost:8000/login → demo@emlakbot.test / demo1234
"""

from datetime import datetime, timedelta
from src.database.local_db import (
    init_db, get_tenant_by_email, create_tenant, insert_lead,
    update_tenant_settings, get_tenant_settings,
    add_note, add_reminder, update_lead_status,
)
from src.auth.security import hash_password


DEMO_EMAIL = "demo@emlakbot.test"
DEMO_PASSWORD = "demo1234"


def seed():
    init_db()

    existing = get_tenant_by_email(DEMO_EMAIL)
    if existing:
        tid = existing["id"]
        print(f"Demo hesabı zaten var (id={tid}, e-posta={DEMO_EMAIL})")
    else:
        tid = create_tenant(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            office_name="Demo Lüks Emlak",
            contact_name="Yusuf Demir",
            phone="05551234567",
        )
        print(f"Demo hesabı oluşturuldu (id={tid})")
        # Bot tonu ve ayarlar
        settings = get_tenant_settings(tid)
        settings.update({
            "bot_tone": "lüks",
            "system_prompt_extras": "Müşterilere Ataşehir ve Maslak bölgelerindeki lüks projelerimizden bahset.",
        })
        update_tenant_settings(tid, settings)

    # Örnek lead'ler
    samples = [
        ("Mehmet Kaya", "905321112233", "Oturumluk", "5-7 milyon ₺ nakit",
         "Ataşehir, 3+1, havuzlu", "1 ay içinde", "NEW",
         ["Sahibinden ilanı üzerinden geldi"], []),
        ("Ayşe Yılmaz", "905334445566", "Yatırımlık", "2-3 milyon ₺ kredi+nakit",
         "Maslak, küçük metrekare", "3 ay içinde", "CONTACTED",
         ["Aradık, Cumartesi tekrar görüşeceğiz."], [(2, "Cumartesi 14:00 ofise gelecek")]),
        ("Ali Şahin", "905367778899", "Oturumluk", "10+ milyon ₺ nakit",
         "Bahçeşehir, müstakil villa", "Hemen", "APPOINTMENT",
         ["Cumartesi 15:00 villa gezisi.", "Eşi de gelecek."], [(1, "Yarın hatırlatma araması")]),
        ("Zeynep Demir", "905401122334", "Oturumluk", "2.5 milyon ₺",
         "Kadıköy, deniz manzaralı", "1-2 ay", "WON",
         ["Sözleşme imzalandı! Komisyon: 100k"], []),
        ("Burak Öztürk", "905445566778", "Yatırımlık", "Belirsiz",
         "Sadece bakıyor", "Belirsiz", "LOST",
         ["Bütçesi düşük, ciddi alıcı değil."], []),
        ("Selin Arslan", "905558899001", "Oturumluk", "4-5 milyon ₺ kredi",
         "Beşiktaş, 2+1", "2-3 ay", "NEW", [], []),
        ("Emre Çelik", "905661122334", "Yatırımlık", "1.5 milyon ₺",
         "Kartal, stüdyo", "Hemen", "NEW", [], []),
    ]

    print(f"\n{len(samples)} örnek lead ekleniyor...")
    for i, (name, phone, purpose, budget, loc, timeline, status, notes, reminders) in enumerate(samples):
        lead_id = f"DEMO{i+1:03d}"
        pk = insert_lead(tid, lead_id, name, phone, purpose, budget, loc, timeline, source="whatsapp")
        if status != "NEW":
            update_lead_status(tid, pk, status)
        for note_body in notes:
            add_note(tid, pk, note_body)
        for days_ahead, body in reminders:
            remind_at = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M")
            add_reminder(tid, pk, remind_at, body)
        print(f"  ✓ {name} ({status})")

    print(f"\n✅ Demo hazır!")
    print(f"   URL:    http://localhost:8000/login")
    print(f"   E-posta: {DEMO_EMAIL}")
    print(f"   Şifre:   {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
