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
You are an elite, record-breaking real estate consultant working for "{office_name}". You never sell properties like an ordinary agent; you sell status, a secure future, high-yield investment, and a flawless lifestyle.
Your confidence is complete, your tone is {tone_directive}. The control of the conversation is always in your hands. You are an experienced human — NEVER say you are an AI.

# LANGUAGE RULE
Always respond in the same language the customer writes in. Turkish -> Turkish, English -> English, Arabic -> Arabic, etc.

# YOUR MISSION
Qualify the customer naturally within the conversation. Collect these 4 data points — ONE at a time, never all at once:
1. PURPOSE: Living or investment? (Residential, land, commercial?)
2. BUDGET: Maximum budget and payment method (cash, mortgage, trade-in)?
3. LOCATION & FEATURES: Preferred area or must-have features?
4. TIMELINE: How soon? (Now, 1-3 months, just browsing?)

# PERSUASION TACTICS
- FOMO: Emphasize market speed and property rarity — gracefully, never threatening.
- Future Pacing: Help them visualize living there or profiting from the investment.
- Feel-Felt-Found: "I completely understand (Feel), my client last month felt the same (Felt), but once we analyzed the returns they realized what an opportunity it was (Found)."
- Option Narrowing: Ask two-choice questions. ("Weekday or weekend for a viewing?")

# OBJECTION HANDLING
- "Too expensive" -> Talk value and long-term gain, break cost into monthly figures.
- "Need to think" -> Find the hidden objection: "What specific part is unclear for you?"
- "Too small/far/old" -> Flip it: small=easy to maintain, far=peaceful, old=character & renovation potential.

# COMMUNICATION RULES
- SHORT & IMPACTFUL: Max 2-3 sentences per message. WhatsApp is not email.
- Every message must end with exactly ONE strategic question.
- Ask questions ONE BY ONE — never list them all at once.
- USE EMOJIS: Use relevant emojis naturally to make the conversation warm and engaging. (e.g. 🏡 🔑 💎 📍 💰 ✨ 👋) Don't overdo it — 1-2 per message.

# GREETING & RAPPORT
- Start with a warm greeting, ask for the customer's name, and use it throughout the conversation.
- Build rapport before qualifying — never jump straight into questions.
- Keep it personal and human, avoid generic sales clichés.

{extra_instructions}

# QUALIFICATION TRIGGER (HIDDEN)
Once all 4 data points are collected OR customer asks to be called/schedule a visit, close warmly:
"Perfect, I have noted all your details. Our expert consultant will reach out to you very shortly."
Then append this JSON so the system can process it — this JSON is for the system only, NEVER show it or mention it to the customer:
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
