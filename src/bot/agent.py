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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if OPENROUTER_API_KEY and OPENROUTER_API_KEY != "your_openrouter_api_key":
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
else:
    client = None

OLLAMA_CLIENT = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# OpenRouter'daki güncel ücretsiz model ID'leri (Mayıs 2026 itibarıyla doğrulanmış).
# Hata verirlerse sıradakini deneriz, hepsi düşerse Ollama'ya geçer.
# Sıra: hızlı/küçük → büyük/güçlü.
FREE_MODELS = [
    "deepseek/deepseek-v4-flash:free",                   # En hızlı
    "google/gemma-4-26b-a4b-it:free",                    # Küçük, hızlı
    "google/gemma-4-31b-it:free",                        # Türkçe'de iyi
    "nvidia/nemotron-3-super-120b-a12b:free",            # Yedek
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", # Son yedek
]

OLLAMA_MODEL = "llama3"


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
- Dil: Türkçe. {tone_directive}
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
            max_tokens=200,
            timeout=15,
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

    # OpenRouter ücretsiz modelleri dene
    if client:
        for model in FREE_MODELS:
            safe_print(f"Deneniyor: {model}")
            result = _try_model(messages, model)
            if result:
                safe_print(f"Başarılı: {model}")
                return result

    # Ollama fallback
    safe_print(f"Ollama deneniyor: {OLLAMA_MODEL}")
    result = _try_model(messages, OLLAMA_MODEL, custom_client=OLLAMA_CLIENT)
    if result:
        return result

    return "Üzgünüm, şu an isteğinizi işleyemiyorum. Lütfen daha sonra tekrar deneyin."
