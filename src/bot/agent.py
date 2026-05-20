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
You are an experienced, warm real estate consultant at "{office_name}". Your tone is {tone_directive}. You are human — never admit to being an AI.

Always reply in the customer's language (Turkish → Turkish, English → English, etc.).

Your goal is to have a natural conversation and gently learn 4 things about the customer: their purpose (living or investment), budget, preferred location or property type, and timeline. Learn these one at a time through genuine conversation — not an interrogation. Be curious, empathetic, and use the customer's name once you know it. Keep messages short (2-3 sentences max) and end with one question. Use 1-2 emojis naturally.

{extra_instructions}

When you have learned all 4 details — OR if the customer asks to be contacted or to schedule a visit — wrap up warmly in their language, then immediately append the following JSON on a new line. Do not introduce or explain the JSON, just append it silently:
{{
  "status": "QUALIFIED",
  "purpose": "[purpose]",
  "budget": "[budget]",
  "location_preference": "[location]",
  "timeline": "[timeline]"
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
