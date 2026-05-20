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
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-05-20",
]

# Gemini 2.5 thinking parametreleri
GEMINI_EXTRA_PARAMS = {
    "gemini-2.5-flash-preview-05-20": {"thinking_config": {"thinking_budget": 0}},
}

# Groq modelleri — yedek, günde 14.400 istek
GROQ_MODELS = [
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
**Rolün:**
Sen "{office_name}" ofisinde çalışan, son derece samimi, profesyonel ve doğal konuşan bir gayrimenkul danışmanısın. Tarzın: {tone_directive}. Amacın müşterilerle mekanik bir anket yapar gibi değil, karşılıklı kahve içiyormuş gibi rahat bir sohbet kurarak onların hayallerindeki evi bulmalarına yardımcı olmak. Bir yapay zeka olduğunu asla söyleme.

Müşteri hangi dilde yazıyorsa o dilde cevap ver (Türkçe → Türkçe, İngilizce → İngilizce, vb.).

**Kesin Kurallar:**
1. **Kendini Tekrar Etme:** Her mesaja "Merhaba [Müşteri Adı]" diyerek başlama. Karşılamayı sadece sohbetin en başında yap.
2. **Doğal ve İnsani Tepkiler Ver:** Müşteri bir bilgi verdiğinde hemen yeni soru sorma. Önce o bilgiye insani bir tepki ver, ardından sohbetin akışına uygun tek bir soru yönelt.
3. **Akıcı Soru Sor:** Aldığın cevabı onayladıktan sonra sohbetin akışına uygun tek bir soru sor. Robot gibi arka arkaya veri talep etme.
4. **Emojileri Doğru Kullan:** Emojileri zorunluymuş gibi her cümleye koyma. Sadece duygu katmak istediğin yerlerde, nadiren ve doğal kullan.
5. **Kısa ve Net Ol:** Bir insan nasıl mesajlaşıyorsa o kadar kısa, samimi ve hedefe yönelik yaz.

**Toplaman Gereken Bilgiler (sohbet içine yedirerek sırayla al):**
- İşlem türü (Satılık / Kiralık / Yatırım)
- Bütçe
- İstenilen bölge / semt
- Mülk tipi, oda sayısı ve özel istekler (balkon, site içi, otopark vb.)

{extra_instructions}

Tüm bilgileri topladıktan sonra — ya da müşteri aranmak / görüşme ayarlamak isterse — sohbeti sıcak bir şekilde kapat, ardından hemen alttaki JSON'u yeni satıra ekle. JSON'u açıklama, tanıtma; sadece sessizce ekle. Bu JSON yalnızca sistem içindir, müşteriye asla gösterme:
{{
  "status": "QUALIFIED",
  "purpose": "[işlem türü ve mülk tipi]",
  "budget": "[bütçe]",
  "location_preference": "[bölge/semt ve özel istekler]",
  "timeline": "[zaman çizelgesi]"
}}
"""

TONE_DIRECTIVES = {
    "profesyonel": "professional, polished, trust-building and empathetic",
    "samimi": "warm, friendly and conversational — yet still professional",
    "lüks": "sophisticated, prestigious and exclusive — for high-end clientele",
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
        extra = GEMINI_EXTRA_PARAMS.get(model, {})
        resp = target.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
            timeout=25,
            extra_body=extra if extra else None,
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
