# EmlakBot — Ürün Dönüşüm Planı

> Bu klasördeki kişisel proje "EmlakBot" adıyla, **emlak ilanı veren danışmanlara/ofislere aylık abonelikle satılan, WhatsApp lead yakalama + mini CRM SaaS'ine** dönüştürülecek.

---

## 1. Ürün Tek Cümleyle

Sahibinden / Hepsiemlak / sosyal medya ilanlarına gelen WhatsApp mesajlarını 7/24 yapay zekâ ile karşılayan, müşteriyi kalifiye eden ve emlakçıya hazır lead olarak teslim eden mini CRM.

## 2. Sorun → Çözüm

| Emlakçının yaşadığı sorun | EmlakBot'un çözümü |
|---|---|
| Akşam 22:00'de gelen WhatsApp mesajını kaçırıyor, başka emlakçıya kaptırıyor | Bot 7/24 anında cevap verir |
| Aynı 4 soruyu (amaç, bütçe, lokasyon, zaman) her müşteriye tekrar tekrar sormak yorucu | Bot bunları profesyonel tonla otomatik sorar |
| "Sadece bakıyorum" diyen vakit hırsızlarına saatler harcıyor | Bot kalifiye olmayanı eler, danışmana yalnız sıcak lead düşer |
| Lead'leri WhatsApp'ta kaybediyor, kim kim takip edilmedi belli değil | Mini CRM: Yeni / Arandı / Randevu / Sattım / Kayıp |

## 3. Hedef Müşteri (Persona)

**Birincil:** Bireysel emlak danışmanı veya 1-5 kişilik küçük ofis. Sahibinden/Hepsiemlak'ta ilan veriyor, ayda 50+ WhatsApp mesajı geliyor, hepsini takip edemiyor.

**İkincil:** Orta ölçekli ofis (5-15 danışman) — sonraki sürümde danışman atama özelliği eklenir.

## 4. Fiyatlandırma Önerisi (3 paket)

| Paket | Aylık | Sınır | Hedef |
|---|---|---|---|
| **Bireysel** | 499 TL | 1 WhatsApp hattı, 200 lead/ay | Tek danışman |
| **Ofis** | 1.499 TL | 3 hat, 1.000 lead/ay, Excel export, ekip | 3-15 kişilik ofis |
| **Kurumsal** | 4.999 TL+ | Sınırsız, API erişimi, özel onboarding | Franchise/büyük ofis |

İlk 14 gün ücretsiz deneme. WhatsApp Cloud API masrafı (Meta'ya konuşma başına ücret) müşteriye ayrı olarak yansır veya pakete dahil edilir.

## 5. MVP Kapsamı (V1 — bu projede yapılacak)

- ✅ Email/şifre ile kayıt + login (multi-tenant)
- ✅ Her hesabın izole lead verisi
- ✅ WhatsApp bot (mevcut, iyileştirilmiş — düzgün LLM bağlantısı)
- ✅ Bot'un sistem promptu/ofis adı/tonu hesap bazında özelleştirilebilir
- ✅ Mini CRM dashboard:
  - Lead listesi (filtre: durum, tarih, arama)
  - Durum geçişleri (Yeni → Arandı → Randevu → Satış / Kayıp)
  - Lead başına not ekleme + zamanlanmış hatırlatma
  - Excel export
- ✅ Ayarlar sayfası: WhatsApp token, ofis bilgisi, bot tonu
- ✅ Basit landing/pazarlama sayfası
- ❌ Ödeme/abonelik altyapısı (manuel — IBAN ile) — V2'de iyzico/Stripe

## 6. Sonraki Sürümler

**V2 (3 ay sonra):**
- iyzico/Stripe ile otomatik abonelik
- Ekip & danışman atama (lead bir danışmana otomatik düşer)
- E-mail/SMS bildirim (yeni lead geldiğinde)

**V3 (6 ay sonra):**
- Portföy/ilan yönetimi — bot ilana özel cevap verir, resim/video paylaşır
- Müşteri ↔ ilan eşleştirme (AI destekli "şu lead şu daireye uygun")
- Sahibinden / Hepsiemlak API entegrasyonu (ilanları senkron çek)

**V4:**
- Sesli arama (AI sesli asistan)
- Randevu takvim entegrasyonu (Google Calendar)

## 7. Teknik Mimari (MVP)

- **Backend:** FastAPI (mevcut)
- **DB:** SQLite (MVP) → Postgres (V2)
- **Auth:** bcrypt + cookie-session (Starlette SessionMiddleware), basit ve yeterli
- **LLM:** OpenRouter ücretsiz modeller + Ollama fallback (mevcut, model isimleri düzeltilecek)
- **WhatsApp:** Meta Cloud API (mevcut)
- **Frontend:** Jinja2 template + Tailwind CDN (build adımı yok, hızlı)
- **Deploy:** Tek VPS + ngrok (MVP) → Railway/Render (V2)

### Yeni Veri Modeli

```
tenants            (id, name, email, password_hash, plan, created_at, settings_json)
                   settings_json: { whatsapp_token, whatsapp_phone_id, office_name, bot_tone, system_prompt_extras }

users              (id, tenant_id, email, password_hash, role, name)   -- V2 için, MVP'de tenant = tek kullanıcı

leads              (id, tenant_id, lead_id, name, phone, purpose, budget,
                    location_preference, timeline, status, assigned_to,
                    source, created_at, last_contact_at)
                   status enum: NEW, CONTACTED, APPOINTMENT, WON, LOST

lead_notes         (id, lead_id, tenant_id, body, created_at, created_by)

lead_reminders     (id, lead_id, tenant_id, remind_at, body, done)

conversations      (id, tenant_id, phone, role, content, created_at)   -- chat history kalıcı
```

## 8. Build Sırası (MVP — 1-2 haftalık gerçek iş)

1. **Veri modeli + migration** — yeni şema, eski verinin upgrade'i
2. **Auth** — kayıt, login, çıkış, session middleware
3. **Tenant scoping** — tüm sorgular `WHERE tenant_id = ?` ile
4. **Bot tenant-aware** — webhook URL'inde tenant_id, sistem promptu DB'den
5. **CRM endpoint'leri** — lead listele, durum değiştir, not ekle, hatırlatma
6. **Yeni dashboard UI** — Tailwind, login + lead listesi + lead detay
7. **Ayarlar sayfası** — WhatsApp token, ofis bilgisi
8. **Landing page** — `/` adresinde tanıtım, fiyat, "Ücretsiz başla" butonu
9. **Onboarding** — kayıt sonrası WhatsApp bağlama rehberi
10. **Demo tenant + örnek lead'ler** — satış görüşmesi için
11. **Mevcut sorunları düzeltme:** model isimleri, ngrok yolu, .env güvenliği, dashboard auth'u

## 9. Demo Senaryosu (5 dk satış konuşması)

1. **Açılış (30 sn):** "Sahibinden ilanına 22:00'de mesaj geldi, sen uyuyorsun. EmlakBot uyumuyor."
2. **Login + Dashboard (1 dk):** Bugünkü lead'leri göster — "İşte gece gelen 3 lead, bütçe ve lokasyon bilgisiyle hazır."
3. **Lead detayı (1 dk):** Bir lead'e tıkla, durumunu "Arandı" yap, not ekle, yarına hatırlatma kur.
4. **Bot konuşması (2 dk):** Telefonda test mesajı at, müşteri rolüne gir, bot'un 4 soruyu doğal akışla sorduğunu göster.
5. **Ayarlar (30 sn):** Ofis adı, bot tonu — "Kendi markanla, kendi tonunla."
6. **Kapanış:** "14 gün ücretsiz dene. Aylık 499 TL'den başlıyor. Ofis paketinde Excel export var."

## 10. Riskler ve Açık Sorular

- **Meta WhatsApp Cloud API onayı:** Her müşterinin kendi Meta Business hesabını bağlaması gerekiyor. Onboarding adımı kritik — kullanıcı burada düşerse satış biter. Çözüm: rehberli video + bizim adımıza kurma seçeneği (ekstra ücret).
- **LLM maliyeti:** Ücretsiz modeller (OpenRouter free tier) kesilirse maliyet artar. Kontrol: kullanım limiti + paid model fallback.
- **KVKK:** Telefon numarası + isim + bütçe topluyoruz. Aydınlatma metni + veri silme talebi endpoint'i gerekli.
- **Rakipler:** TR'de "WhatsApp bot + CRM" satan birçok ajans var (RobotChat, Hubsoft vs). Farklılık: emlak'a özgün, kalifikasyon soruları hazır, Sahibinden kullanıcısına direkt.
- **Soru:** Hangi kanaldan satacağız? (Hepsıemlak danışman grupları, Instagram reels, soğuk arama?)

## 11. Bu Plandan Sonraki Adım

Onaylarsan: önce **veri modeli + auth**'u kuracağım. Sonra bot'u tenant-aware yapıp CRM dashboard'unu inşa edeceğim. Her büyük adım sonunda sana göstereceğim.
