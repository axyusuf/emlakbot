import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase_client() -> Client | None:
    """Supabase istemcisini döndürür. Ayarlar eksikse None döner."""
    if not SUPABASE_URL or not SUPABASE_KEY or SUPABASE_URL == "your_supabase_project_url":
        print("Uyarı: Supabase URL veya Key yapılandırılmamış. Veritabanı işlemleri atlanacak.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase bağlantı hatası: {e}")
        return None
