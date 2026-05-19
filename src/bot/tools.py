"""Lead kaydetme yardımcısı — tenant-aware."""

import uuid
from src.database.local_db import insert_lead
from src.database.db import get_supabase_client


def save_qualified_lead(
    tenant_id: int,
    name: str,
    phone: str,
    purpose: str,
    budget: str,
    location_preference: str,
    timeline: str,
) -> str:
    """Kalifiye olmuş lead'i hem yerel SQLite'a hem (varsa) Supabase'e kaydeder."""
    try:
        lead_id = str(uuid.uuid4())[:8]

        # Yerel SQLite (dashboard)
        insert_lead(
            tenant_id=tenant_id,
            lead_id=lead_id,
            name=name,
            phone=phone,
            purpose=purpose,
            budget=budget,
            location_preference=location_preference,
            timeline=timeline,
            source="whatsapp",
        )
        print(f"[Dashboard] Lead kaydedildi: tenant={tenant_id} {lead_id} - {name}")

        # Supabase (opsiyonel yedek)
        client = get_supabase_client()
        if client:
            try:
                client.table("leads").insert({
                    "tenant_id": tenant_id,
                    "lead_id": lead_id,
                    "name": name,
                    "phone": phone,
                    "purpose": purpose,
                    "budget": budget,
                    "location_preference": location_preference,
                    "timeline": timeline,
                    "status": "NEW",
                }).execute()
                print(f"[Supabase] Lead kaydedildi: {lead_id}")
            except Exception as e:
                print(f"[Supabase] Kayıt hatası (dashboard etkilenmez): {e}")

        return f"Müşteri kaydı tamamlandı. Lead ID: {lead_id}"

    except Exception as e:
        print(f"save_qualified_lead error: {e}")
        return f"Sistemsel bir hata oluştu: {str(e)}"
