"""
EmlakBot — Tenant-aware LLM ajanı.

Her tenant'ın kendi:
- ofis adı
- bot tonu
- ek talimatları (settings_json.system_prompt_extras)

ayarlarına göre dinamik sistem promptu üretir.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if GEMINI_API_KEY:
    gemini_client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
else:
    gemini_client = None

if GROQ_API_KEY:
    groq_client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )
else:
    groq_client = None

if OPENROUTER_API_KEY and OPENROUTER_API_KEY != "your_openrouter_api_key":
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
else:
    client = None

# Gemini modelleri — birincil, günde 1.500 ücretsiz istek
GEMINI_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
]

# Groq modelleri — yedek, günde 14.400 istek
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# OpenRouter son yedek
FREE_MODELS = [
    "deepseek/deepseek-v4-flash:free",
    "google/gemma-4-31b-it:free",
]


BASE_PROMPT_TEMPLATE = """
# ROL VE MİSYON
Sen "{office_name}" gayrimenkul ofisinde çalışan, profesyonel, güven veren ve çözüm odaklı bir
"Gayrimenkul Satış Öncesi Destek ve Kalifikasyon Yapay Zekâ Asistanı"sın. Görevin, ilanlar veya
reklamlar üzerinden ofisimize ulaşan potansiyel müşterilerle (lead) WhatsApp üzerinden
insan benzeri, samimi ama kurumsal bir dille iletişim kurup onları kalifiye etmektir.

# TEMEL AMAÇLARIN
Müşteriyi sıkmadan, cana yakın bir sohbet akışı içinde şu 4 kritik bilgiyi öğrenmelisin:
1. Arayış Amacı: Oturumluk mu, yatırımlık mı? (Konut, arsa, ticari?)
2. Bütçe Aralığı: Maksimum bütçe nedir ve ödeme şekli (Nakit, kredi, takas) nasıl?
3. Lokasyon ve Özellik Tercihi: İlgilendiği bölge veya olmazsa olmaz özellik var mı?
4. Zaman Planı: Ne kadar sürede satın almayı planlıyor? (Hemen, 1-3 ay, sadece bakıyor?)

# İLETİŞİM VE TONLAMA KURALLARI
- Language: Always respond in the same language the customer writes in. If they write in Turkish, respond in Turkish. If English, respond in English. If Arabic, respond in Arabic. Etc. {tone_directive}
- Kısa ve Net: WhatsApp mesajları uzun olmamalı. Her mesajda maksimum 2-3 cümle.
- Tek Tek Soru Sor: Asla tüm soruları tek bir mesajda sorma! Cevaba göre empati yap,
  onayla ve bir sonraki mantıklı soruyu yönelt.
- Zorlama: Müşteri bütçe gibi hassas bir bilgi vermek istemezse zorlama,
  "Yaklaşık bir aralık belirtmeniz size en doğru ilanları seçmemize yardımcı olur" diyerek esneklik sağla.

{extra_instructions}

# ÇIKTI VE AKSİYON (GİZLİ KOMUT)
4 bilgiyi başarıyla topladığında veya müşteri "Beni bir danışman arasın / randevu istiyorum"
dediğinde, sohbeti nazikçe kapat:
"Harika, tüm detayları not aldım. Sizinle ilgilenmesi için uzman gayrimenkul danışmanımız
en kısa sürede iletişime geçecek."
Sonra sistemin algılayabilmesi için konuşmayı şu JSON ile bitir:
{{
  "status": "QUALIFIED",
  "purpose": "[Oturumluk/Yatırımlık]",
  "budget": "[Bütçe Verisi]",
  "location_preference": "[Lokasyon Bilgisi]",
  "timeline": "[Zaman Planı]"
}}
"""

TONE_DIRECTIVES = {
    "profesyonel": "Son derece profesyonel, nazik, güven verici ve empati kuran bir ton kullan.",
    "samimi": "Sıcak, samimi ve günlük konuşma tonunda ol — ama profesyonelliği kaybetme.",
    "lüks": "Lüks segment müşterisine hitap ettiğin bilinci ile şık, kurumsal ve prestijli bir ton kullan.",
}


def build_system_prompt(tenant_settings: dict, office_name: str) -> str:
    tone = tenant_settings.get("bot_tone", "profesyonel")
    tone_directive = TONE_DIRECTIVES.get(tone, TONE_DIRECTIVES["profesyonel"])
    extras = tenant_settings.get("system_prompt_extras", "").strip()
    extra_section = ""
    if extras:
        extra_section = f"# OFİSE ÖZEL TALİMATLAR\n{extras}\n"
    return BASE_PROMPT_TEMPLATE.format(
        office_name=office_name or "Gayrimenkul Ofisi",
        tone_directive=tone_directive,
        extra_instructions=extra_section,
    )


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _try_model(messages: list, model: str, custom_client=None) -> str | None:
    target = custom_client if custom_client else client
    if target is None:
        return None
    try:
        resp = target.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=350,
            timeout=20,
        )
        return resp.choices[0].message.content
    except Exception as e:
        safe_print(f"Model hatası ({model}): {e}")
        return None


def handle_message(
    user_message: str,
    user_phone: str,
    office_name: str,
    tenant_settings: dict,
    chat_history: list | None = None,
) -> str:
    """Mesajı işle ve bot cevabını döndür. Tenant bilgisi sistem promptuna girer."""
    system_prompt = build_system_prompt(tenant_settings, office_name)
    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        messages.extend(chat_history)
    messages.append({
        "role": "user",
        "content": f"Misafirin Telefonu: {user_phone}. Mesajı: {user_message}",
    })

    # Gemini (birincil — güçlü, Türkçe'de en iyi)
    if gemini_client:
        for model in GEMINI_MODELS:
            safe_print(f"Gemini deneniyor: {model}")
            result = _try_model(messages, model, custom_client=gemini_client)
            if result:
                safe_print(f"Gemini başarılı: {model}")
                return result

    # Groq (yedek — günde 14.400 istek)
    if groq_client:
        for model in GROQ_MODELS:
            safe_print(f"Groq deneniyor: {model}")
            result = _try_model(messages, model, custom_client=groq_client)
            if result:
                safe_print(f"Groq başarılı: {model}")
                return result

    # OpenRouter (son yedek)
    if client:
        for model in FREE_MODELS:
            safe_print(f"OpenRouter deneniyor: {model}")
            result = _try_model(messages, model)
            if result:
                safe_print(f"OpenRouter başarılı: {model}")
                return result

    return "Üzgünüm, şu an isteğinizi işleyemiyorum. Lütfen daha sonra tekrar deneyin."
