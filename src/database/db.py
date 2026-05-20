import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

try:
    from supabase import create_client
    _SUPABASE_OK = True
except Exception:
    _SUPABASE_OK = False


def get_supabase_client():
    if not _SUPABASE_OK:
        return None
    if not SUPABASE_URL or not SUPABASE_KEY or SUPABASE_URL == "your_supabase_project_url":
        print("Uyarı: Supabase URL veya Key yapılandırılmamış.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase bağlantı hatası: {e}")
        return None
