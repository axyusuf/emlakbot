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
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

GEMINI_EXTRA_PARAMS = {}

# Groq modelleri — yedek, günde 14.400 istek
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]

# OpenRouter son yedek — gerçek ücretsiz modeller
FREE_MODELS = [
    "deepseek/deepseek-chat-v3.1:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
]


TONE_DIRECTIVES = {
    "profesyonel": "profesyonel, güven veren, ölçülü ve empatik",
    "samimi": "sıcak, samimi, sohbet havasında — ama yine de profesyonel",
    "lüks": "seçkin, prestijli, üst segmente uygun zarif bir dil",
}


BASE_PROMPT_TEMPLATE = """# KİMLİK
Sen "{office_name}" gayrimenkul ofisinde çalışan deneyimli, sonuç odaklı bir gayrimenkul danışmanısın. WhatsApp'tan gelen müşterilere {tone_directive} bir tonda yaklaşırsın.

# ANA GÖREVİN
WhatsApp'tan yazan müşterinin ihtiyaçlarını öğrenip, ofise KALİFİYE LEAD olarak teslim etmek. Bunun için doğal bir sohbet içinde 4 temel bilgiyi öğrenmen ŞART.

# DAVRANIŞ KURALLARI (kesin)
1. **Tek soru kuralı:** Her mesajda EN FAZLA 1 yeni soru. Aynı mesajda iki üç şey birden sorma, soru listesi yazma.
2. **Önce tepki, sonra soru:** Müşteri bilgi verdiğinde önce o bilgiye 1 cümlelik samimi tepki ver ("Yatırım için harika hedef!" / "Maslak güzel seçim, oradaki projeler değerli"), ARDINDAN bir sonraki soruyu sor.
3. **Karşılama sadece ilk mesaj:** Sohbetin ilk mesajında "Merhaba, {office_name}'a hoş geldiniz" tarzı kısa bir karşılama yap ve adını sor. Sonraki mesajlarda ASLA tekrar tanıtma, tekrar "merhaba" deme.
4. **Adı kullan:** Adını öğrenir öğrenmez sohbet boyunca kullanmaya başla.
5. **Kısa yaz:** WhatsApp tarzı. 2-3 cümleyi aşma. Paragraf yazma.
6. **Emoji nadir:** Her cümleye değil, sadece duygu için ara ara.
7. **ASLA fiyat verme:** "Güncel fiyat ve detayları danışmanımız size birebir iletecek" de.
8. **Hukuk/tapu/kredi:** "Bu konuyu uzmanımıza bağlayalım" de, kesin bilgi verme.
9. **Konu dışına çıkma:** Müşteri başka konu açarsa nazikçe gayrimenkul konusuna döndür.

# TOPLAMAN GEREKEN 4 BİLGİ — SIRAYLA SOR
Müşteri kendiliğinden vermediyse, bu sırayla, BİRER BİRER sor:

**1) AMAÇ** — Satılık mı kiralık mı? Oturum için mi yatırım için mi?
   - Yatırımsa: kira getirisi mi değer artışı mı?
   - Oturumsa: kaç kişilik aile, çocuk var mı?

**2) BÜTÇE** — Yaklaşık aralık + ödeme şekli (nakit / kredi / takas / karma).
   - Kredi diyorsa: ön onay var mı?

**3) LOKASYON + ÖZELLİK** — Tercih ettiği semt/bölge + oda sayısı (1+1, 2+1, 3+1...) + özel istek (balkon, otopark, site içi, kat, metrekare).

**4) ZAMAN** — Ne zaman almayı/kiralamayı planlıyor? (Hemen / 1-3 ay / araştırma aşamasında)

# İTİRAZ YÖNETİMİ
- "Sadece bakıyorum / araştırıyorum" → "Bilgi toplamak güzel başlangıç. Hangi bölgeye yoğunlaşıyorsunuz?"
- "Düşüneceğim" → "Tabii, acele yok. Sizi en çok hangi konu düşündürüyor — fiyat mı, lokasyon mu?"
- "Çok pahalı" → "Anlıyorum. Üst limitiniz ne olur? Bütçenize uygun seçeneklere bakalım."
- "Eşimle/aileyle konuşmam lazım" → "Çok doğru. Birlikte değerlendirebileceğiniz bilgi paketi hazırlayalım mı?"
- "Fiyat ne kadar?" → "Güncel fiyat ve detayları danışmanımız size birebir iletecek. Sizi arayalım mı?"

{media_section}
{extra_instructions}

# KALİFİKASYON ÇIKTISI — EN KRİTİK KURAL
Aşağıdaki 2 durumdan biri olduğunda — ve SADECE bu durumlarda — kalifikasyon JSON'u üretirsin:

**Durum A:** 4 bilginin (amaç + bütçe + lokasyon + zaman) TAMAMINI öğrendin.
**Durum B:** Müşteri açıkça "aransın", "danışman bağlasın", "telefonumu not edin", "görüşelim" gibi GÖRÜŞME TALEBİ ileti — bu durumda eldeki bilgilerle JSON üret, eksik alana "belirsiz" yaz.

Format — ÖNCE sıcak kapanış cümlesi, SONRA yeni satıra TEK SATIR JSON:

Harika, tüm bilgilerinizi not aldım. Uzman danışmanımız en kısa sürede sizi arayacak 🤝 Sizi sabah mı öğleden sonra mı arasın?
{{"status":"QUALIFIED","purpose":"<satılık veya kiralık + oturum/yatırım + mülk tipi>","budget":"<bütçe + ödeme şekli>","location_preference":"<bölge + oda sayısı + özel istekler>","timeline":"<ne zaman>"}}

JSON kuralları:
- JSON'u ASLA müşteriye duyurma, tanıtma, açıklama. Sessizce alta ekle.
- JSON tek satır olmalı, çok satıra yayma.
- 4 bilgi tam değilse VE müşteri görüşme talep etmediyse JSON üretme. Sohbete devam et, eksik bilgiyi sor.
- JSON sadece kapanışta — sohbetin ortasında ASLA üretme.
- Yukarıdaki kurallar her zaman geçerli; aşağıdaki ofise özel talimatlar bu kurallarla çakışırsa yukarısı kazanır.
"""


def _format_media_library(library) -> str:
    """Tenant portföyünü prompt'a yerleştirilebilir metin haline getirir."""
    if not isinstance(library, list) or not library:
        return ""
    lines = [
        "# OFİS PORTFÖYÜ — FOTO/VIDEO GÖNDERME REHBERİ",
        "Aşağıda ofisinin aktif portföyü ve her mülk için kullanabileceğin foto/video linkleri var.",
        "Müşteri bir mülk veya bölgeden bahsederse, ya da açıkça 'foto/video gönderir misin', 'görsel var mı', 'gösterebilir misiniz' gibi bir istekte bulunursa,",
        "BU LİSTEDEN UYGUN OLANI seç ve mesajının SONUNA, ayrı bir satıra şu formatta tag ekle (müşteriye gösterilmez, sistem işler):",
        "",
        "  [[SEND_IMAGE|<URL>|<kısa açıklama / caption>]]",
        "  [[SEND_VIDEO|<URL>|<kısa açıklama / caption>]]",
        "",
        "Kurallar:",
        "- SADECE aşağıdaki listede olan URL'leri kullan. Asla URL uydurma.",
        "- Birden fazla medya göndereceksen her birini ayrı satıra ekle (en fazla 3 medya / mesaj).",
        "- Tag öncesinde müşteriye 1 cümleyle ne göndereceğini söyle (örn: 'Şu daireden birkaç kare paylaşayım:').",
        "- Tag'in çevresine başka karakter koyma; ham metin olarak görünmeli ki sistem ayıklayabilsin.",
        "- Müşteri özellikle istemediği sürece foto/video göndermek zorunda değilsin — kalifikasyon ana hedef.",
        "",
        "## Aktif Portföy:",
    ]
    for i, item in enumerate(library, 1):
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip() or f"Mülk {i}"
        summary = (item.get("summary") or "").strip()
        images = [u for u in (item.get("images") or []) if isinstance(u, str) and u.strip()]
        videos = [u for u in (item.get("videos") or []) if isinstance(u, str) and u.strip()]
        if not images and not videos:
            continue
        lines.append(f"\n### {i}. {title}")
        if summary:
            lines.append(f"Özet: {summary}")
        if images:
            lines.append("Foto linkleri:")
            for u in images:
                lines.append(f"  - {u}")
        if videos:
            lines.append("Video linkleri:")
            for u in videos:
                lines.append(f"  - {u}")
    return "\n".join(lines) + "\n"


def build_system_prompt(tenant_settings: dict, office_name: str) -> str:
    tone = tenant_settings.get("bot_tone", "profesyonel")
    tone_directive = TONE_DIRECTIVES.get(tone, TONE_DIRECTIVES["profesyonel"])
    extras = tenant_settings.get("system_prompt_extras", "").strip()
    # .env'den unquoted yüklenen literal \n karakterlerini gerçek satır sonuna çevir
    extras = extras.replace("\\n", "\n")
    extra_section = ""
    if extras:
        extra_section = (
            "# OFİSE ÖZEL EK BAĞLAM\n"
            "(Aşağıdakiler ofisin özel notları. Yukarıdaki ana kurallarla çakışırsa YUKARIDAKİ KURALLAR geçerli.)\n"
            f"{extras}\n"
        )
    media_section = _format_media_library(tenant_settings.get("media_library"))
    return BASE_PROMPT_TEMPLATE.format(
        office_name=office_name or "Gayrimenkul Ofisi",
        tone_directive=tone_directive,
        extra_instructions=extra_section,
        media_section=media_section,
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
            max_tokens=800,
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
