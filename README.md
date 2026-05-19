# EmlakBot

> Emlakçılar için WhatsApp lead yakalama + mini CRM SaaS.
> Sahibinden / Hepsiemlak ilanlarına gelen mesajları 7/24 cevaplar, müşteriyi kalifiye eder, dashboard'da takip ettirir.

## Özellikler (MVP)

- ✅ Çok kiracılı (multi-tenant) hesap sistemi — e-posta + şifre ile kayıt/giriş
- ✅ Her hesaba izole veri (lead'ler, ayarlar, sohbet geçmişi)
- ✅ WhatsApp Cloud API entegrasyonu — her tenant kendi WhatsApp hattını bağlar
- ✅ AI kalifikasyon botu (OpenRouter ücretsiz modeller + Ollama fallback)
- ✅ Mini CRM: Yeni / Arandı / Randevu / Satış / Kayıp durumları
- ✅ Lead başına notlar ve zamanlanmış hatırlatmalar
- ✅ Lead listesini Excel'e export
- ✅ Bot tonunu (profesyonel / samimi / lüks) ve ek talimatları özelleştirme
- ✅ Pazarlama landing sayfası + fiyatlandırma

## Kurulum

```bash
# Bağımlılıklar
pip install -r requirements.txt

# Ortam değişkenleri
cp .env.example .env
# .env dosyasını açıp SESSION_SECRET, OPENROUTER_API_KEY vs. doldurun

# Sunucuyu çalıştır
py -m uvicorn src.main:app --reload --port 8000

# (Opsiyonel) Demo verisi yükle — satış sunumu için
py seed_demo.py
```

Veya tek tıkla: `baslat.bat`

## URL'ler

| Yol | Ne işe yarar |
|---|---|
| `/` | Pazarlama anasayfası |
| `/register` | Yeni hesap kaydı |
| `/login` | Giriş |
| `/app` | Lead dashboard'u |
| `/app/leads/{id}` | Lead detayı (durum, notlar, hatırlatma) |
| `/app/settings` | Ofis bilgileri, bot tonu, WhatsApp bağlantısı |
| `/app/export` | Lead listesini Excel olarak indir |
| `/webhook` | Meta WhatsApp Cloud API webhook |

## Demo Hesabı

`py seed_demo.py` çalıştırdıktan sonra:

- **E-posta:** `demo@emlakbot.test`
- **Şifre:** `demo1234`

## WhatsApp Cloud API Bağlama (Müşteri Onboarding'i)

1. Meta for Developers'tan WhatsApp Business uygulaması oluştur
2. Phone Number ID ve sürekli token al
3. EmlakBot → Ayarlar sayfasında bu bilgileri gir
4. Meta panel → Webhook URL: `https://<senin-domain>/webhook`, verify token: `.env`'deki `VERIFY_TOKEN`
5. `messages` event'ine abone ol

## Mimari

```
src/
├── main.py                 FastAPI uygulaması, tüm endpoint'ler
├── auth/
│   ├── security.py         bcrypt + session helpers
│   └── routes.py           login / register / logout
├── bot/
│   ├── agent.py            LLM ajanı, dinamik sistem promptu
│   └── tools.py            Lead kaydetme
├── database/
│   ├── local_db.py         SQLite veri katmanı (multi-tenant)
│   └── db.py               Supabase istemcisi (opsiyonel yedek)
├── whatsapp/
│   └── client.py           Meta WhatsApp Cloud API
└── templates/
    └── (HTML inline'da, main.py içinde)
```

## Yol Haritası

Detaylı plan için: [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md)

- **V1 (şimdi):** MVP — yukarıdaki özellikler
- **V2:** iyzico/Stripe otomatik abonelik, ekip yönetimi, e-posta/SMS bildirim
- **V3:** Portföy/ilan yönetimi, AI öneri, Sahibinden API senkron

## Lisans

Özel mülk — Yusuf'a aittir.
