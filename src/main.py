"""
EmlakBot — WhatsApp lead yakalama + mini CRM SaaS

Endpoint haritası:
  /                              Landing (pazarlama)
  /pricing                       Fiyatlandırma
  /login, /register, /logout     Auth (src/auth/routes.py)
  /app                           Dashboard (login gerekli)
  /app/leads/{id}                Lead detay
  /app/leads/{id}/status         POST: durum değiştir
  /app/leads/{id}/note           POST: not ekle
  /app/leads/{id}/reminder       POST: hatırlatma ekle
  /app/settings                  Ayarlar
  /app/export                    Excel export
  /webhook                       WhatsApp Cloud API webhook (Meta)
  /healthz                       Sağlık kontrolü
"""

import os
import io
import json
import re
import secrets
from datetime import datetime
from html import escape

import httpx
from fastapi import FastAPI, Request, BackgroundTasks, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from src.auth.routes import router as auth_router
from src.auth.security import require_tenant, current_tenant_id
from src.bot.agent import handle_message
from src.bot.tools import save_qualified_lead
from src.whatsapp.client import send_whatsapp_message
from src.database.local_db import (
    init_db, get_tenant, get_tenant_settings, update_tenant_settings, update_tenant,
    find_tenant_by_whatsapp_phone_id, list_leads, get_lead, update_lead_status,
    add_note, list_notes, add_reminder, list_reminders, mark_reminder_done,
    count_by_status, count_today, append_message, get_recent_messages,
    ALL_STATUSES, STATUS_LABELS_TR,
)

load_dotenv()

app = FastAPI(title="EmlakBot API")

# Session secret — production'da .env'den okunmalı
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_hex(32)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 24 * 14)

# Auth router
app.include_router(auth_router)

# DB init
try:
    init_db()
except Exception as _db_err:
    print(f"DB init hatası (uygulama yine de başlıyor): {_db_err}")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "gayri_menkul").strip()


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


# 401 (login_required) → /login yönlendirmesi
@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and exc.detail == "login_required":
        return RedirectResponse("/login", status_code=303)
    return await http_exception_handler(request, exc)


# =============== LAYOUT ===============

def _shell(title: str, body: str, tenant: dict | None = None) -> str:
    nav = ""
    if tenant:
        nav = f"""
        <nav class="nav">
          <div class="brand">Emlak<span>Bot</span></div>
          <div class="navlinks">
            <a href="/app">Dashboard</a>
            <a href="/app/settings">Ayarlar</a>
            <a href="/app/export">Excel</a>
            <span class="who">{escape(tenant.get('office_name',''))}</span>
            <a href="/logout" class="logout">Çıkış</a>
          </div>
        </nav>"""
    return f"""<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="UTF-8"><title>{escape(title)} — EmlakBot</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',-apple-system,sans-serif;background:#f4f5f9;color:#222;min-height:100vh}}
.nav{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:14px 32px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 10px rgba(0,0,0,.15)}}
.brand{{font-size:20px;font-weight:700}}
.brand span{{color:#27ae60}}
.navlinks{{display:flex;gap:24px;align-items:center;font-size:14px}}
.navlinks a{{color:#cbd0e0;text-decoration:none;transition:color .15s}}
.navlinks a:hover{{color:white}}
.navlinks .who{{color:#888;font-size:13px;border-left:1px solid #333;padding-left:24px}}
.navlinks .logout{{background:rgba(255,255,255,.08);padding:6px 14px;border-radius:6px}}
.container{{max-width:1280px;margin:0 auto;padding:32px}}
h1{{font-size:22px;margin-bottom:20px;color:#1a1a2e}}
h2{{font-size:16px;margin-bottom:14px;color:#444}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:24px}}
.stat{{background:white;border-radius:12px;padding:18px 22px;box-shadow:0 2px 6px rgba(0,0,0,.05)}}
.stat .n{{font-size:30px;font-weight:700;color:#1a1a2e}}
.stat .l{{font-size:12px;color:#888;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
.stat.green .n{{color:#27ae60}}
.stat.blue .n{{color:#2563eb}}
.stat.orange .n{{color:#e67e22}}
.stat.red .n{{color:#c0392b}}
.card{{background:white;border-radius:14px;box-shadow:0 2px 6px rgba(0,0,0,.06);padding:24px;margin-bottom:20px}}
.filters{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}}
.filters input,.filters select{{padding:9px 14px;border:1px solid #e0e0e0;border-radius:8px;font-size:13px;background:white}}
.filters .btn{{background:#1a1a2e;color:white;border:none;padding:9px 18px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:600}}
.filters .btn:hover{{opacity:.88}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden}}
thead tr{{background:#1a1a2e;color:white}}
thead th{{padding:12px 16px;text-align:left;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}}
tbody tr{{border-bottom:1px solid #f0f0f4;transition:background .12s}}
tbody tr:hover{{background:#fafbff;cursor:pointer}}
tbody td{{padding:13px 16px;font-size:14px}}
.badge{{display:inline-block;padding:3px 11px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.3px}}
.b-NEW{{background:#e8f0ff;color:#2563eb}}
.b-CONTACTED{{background:#fff5e0;color:#e67e22}}
.b-APPOINTMENT{{background:#f0e8ff;color:#7e3eb8}}
.b-WON{{background:#e8f8f0;color:#27ae60}}
.b-LOST{{background:#fbe5e5;color:#c0392b}}
.phone{{color:#666;font-family:monospace;font-size:13px}}
.date{{color:#999;font-size:12px}}
.empty{{text-align:center;padding:60px;color:#aaa;font-size:14px}}
a.lead-link{{color:#1a1a2e;font-weight:600;text-decoration:none}}
.button{{background:#1a1a2e;color:white;border:none;padding:10px 18px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:600;text-decoration:none;display:inline-block}}
.button:hover{{opacity:.88}}
.button.green{{background:#27ae60}}
.button.outline{{background:transparent;color:#1a1a2e;border:1px solid #1a1a2e}}
label{{display:block;font-size:13px;color:#555;margin-bottom:6px;margin-top:14px;font-weight:500}}
input[type=text],input[type=email],input[type=tel],input[type=password],input[type=datetime-local],textarea,select{{width:100%;padding:10px 14px;border:1px solid #e0e0e0;border-radius:8px;font-size:14px;font-family:inherit}}
textarea{{resize:vertical;min-height:80px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
@media(max-width:800px){{.grid2{{grid-template-columns:1fr}}}}
.note-item,.rem-item{{background:#f8f9fb;padding:12px 14px;border-radius:8px;margin-bottom:10px;font-size:13px}}
.note-item .date,.rem-item .date{{font-size:11px;margin-bottom:4px}}
.row-actions{{margin-top:8px}}
.row-actions form{{display:inline}}
.row-actions button{{background:transparent;border:1px solid #ddd;padding:4px 10px;border-radius:6px;font-size:11px;cursor:pointer;margin-right:4px}}
.row-actions button:hover{{background:#f0f0f0}}
/* landing */
.hero{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:80px 32px;text-align:center}}
.hero h1{{font-size:42px;margin-bottom:18px;color:white}}
.hero p{{font-size:18px;color:#cbd0e0;max-width:680px;margin:0 auto 30px}}
.hero .button{{background:#27ae60;font-size:16px;padding:16px 36px}}
.features{{padding:60px 32px;max-width:1080px;margin:0 auto}}
.feature-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin-top:30px}}
.feature{{background:white;padding:28px;border-radius:14px;box-shadow:0 2px 6px rgba(0,0,0,.05)}}
.feature h3{{font-size:17px;margin-bottom:8px;color:#1a1a2e}}
.feature p{{font-size:14px;color:#666;line-height:1.6}}
.pricing{{padding:60px 32px;max-width:1080px;margin:0 auto}}
.plans{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;margin-top:24px}}
.plan{{background:white;padding:32px;border-radius:14px;box-shadow:0 4px 12px rgba(0,0,0,.06);text-align:center;border:2px solid transparent}}
.plan.featured{{border-color:#27ae60;transform:scale(1.03)}}
.plan h3{{font-size:18px;color:#1a1a2e;margin-bottom:6px}}
.plan .price{{font-size:38px;font-weight:700;color:#1a1a2e;margin:10px 0}}
.plan .price span{{font-size:14px;color:#888;font-weight:400}}
.plan ul{{list-style:none;text-align:left;margin:20px 0 24px}}
.plan li{{padding:6px 0;color:#555;font-size:14px}}
.plan li::before{{content:"✓ ";color:#27ae60;font-weight:700}}
footer{{background:#1a1a2e;color:#888;padding:30px 32px;text-align:center;font-size:13px}}
footer a{{color:#cbd0e0;text-decoration:none}}
</style></head><body>
{nav}
{body}
</body></html>"""


# =============== LANDING ===============

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    if current_tenant_id(request):
        return RedirectResponse("/app", status_code=303)
    body = """
    <section class="hero">
      <h1>Sahibinden mesajları artık geceleri de cevaplanıyor.</h1>
      <p>EmlakBot, ilan mesajlarınıza 7/24 cevap veren WhatsApp asistanıdır. Müşteriyi kalifiye eder,
      bütçesini ve lokasyon tercihini öğrenir, size hazır lead olarak teslim eder.</p>
      <a href="/register" class="button">14 Gün Ücretsiz Dene</a>
    </section>

    <section class="features">
      <h2 style="text-align:center;font-size:26px;color:#1a1a2e;margin-bottom:8px">Neden EmlakBot?</h2>
      <div class="feature-grid">
        <div class="feature"><h3>🌙 7/24 cevap</h3><p>Gece 02:00'de gelen mesaja bot cevap verir, müşteri başka emlakçıya gitmez.</p></div>
        <div class="feature"><h3>🎯 Otomatik kalifikasyon</h3><p>4 kritik soruyu (amaç, bütçe, lokasyon, zaman) doğal akışta sorar, sıcak lead'i ayırır.</p></div>
        <div class="feature"><h3>📋 Mini CRM</h3><p>Yeni → Arandı → Randevu → Satış. Lead başına not ve hatırlatma.</p></div>
        <div class="feature"><h3>📊 Excel export</h3><p>Tüm lead'lerini tek tıkla Excel'e aktar, ekiple paylaş.</p></div>
        <div class="feature"><h3>🎨 Markalandırma</h3><p>Bot kendini senin ofisinin adıyla tanıtır, senin tonunla konuşur.</p></div>
        <div class="feature"><h3>🔒 KVKK uyumlu</h3><p>Müşteri verisi senin hesabında izole. Başka emlakçıyla paylaşılmaz.</p></div>
      </div>
    </section>

    <section class="pricing">
      <h2 style="text-align:center;font-size:26px;color:#1a1a2e;margin-bottom:8px">Fiyatlandırma</h2>
      <p style="text-align:center;color:#666">İlk 14 gün ücretsiz. Kredi kartı gerekmez.</p>
      <div class="plans">
        <div class="plan">
          <h3>Bireysel</h3>
          <div class="price">499₺<span>/ay</span></div>
          <ul><li>1 WhatsApp hattı</li><li>200 lead/ay</li><li>Mini CRM</li><li>E-posta destek</li></ul>
          <a href="/register" class="button outline">Başla</a>
        </div>
        <div class="plan featured">
          <h3>Ofis ⭐</h3>
          <div class="price">1.499₺<span>/ay</span></div>
          <ul><li>3 WhatsApp hattı</li><li>1.000 lead/ay</li><li>Mini CRM + Excel export</li><li>Ekip kullanımı</li><li>Öncelikli destek</li></ul>
          <a href="/register" class="button">Başla</a>
        </div>
        <div class="plan">
          <h3>Kurumsal</h3>
          <div class="price">4.999₺<span>/ay</span></div>
          <ul><li>Sınırsız hat & lead</li><li>API erişimi</li><li>Özel onboarding</li><li>Telefon destek</li></ul>
          <a href="mailto:satis@emlakbot.com.tr" class="button outline">İletişim</a>
        </div>
      </div>
    </section>

    <footer>EmlakBot © 2026 — <a href="/login">Giriş</a> · <a href="/register">Kayıt</a></footer>
    """
    return HTMLResponse(_shell("Anasayfa", body))


# =============== DASHBOARD ===============

@app.get("/app", response_class=HTMLResponse)
def dashboard(request: Request, status: str = "", q: str = ""):
    tid = require_tenant(request)
    tenant = get_tenant(tid)
    leads = list_leads(tid, status=status or None, search=q or None)
    counts = count_by_status(tid)
    today = count_today(tid)

    rows = ""
    if leads:
        for lead in leads:
            st = lead.get("status", "NEW")
            rows += f"""
            <tr onclick="location.href='/app/leads/{lead['id']}'">
              <td><a class="lead-link" href="/app/leads/{lead['id']}">{escape(lead.get('name') or '—')}</a></td>
              <td class="phone">{escape(lead.get('phone') or '')}</td>
              <td>{escape(lead.get('purpose') or '')}</td>
              <td>{escape(lead.get('budget') or '')}</td>
              <td>{escape(lead.get('location_preference') or '')}</td>
              <td>{escape(lead.get('timeline') or '')}</td>
              <td><span class="badge b-{st}">{escape(STATUS_LABELS_TR.get(st,st))}</span></td>
              <td class="date">{escape(_fmt_dt(lead.get('created_at')))}</td>
            </tr>"""
    else:
        rows = '<tr><td colspan="8" class="empty">Henüz lead yok. WhatsApp\'a ilk mesaj geldiğinde burada görünecek.</td></tr>'

    # Filtre seçenekleri
    status_options = '<option value="">Tüm Durumlar</option>'
    for s in ALL_STATUSES:
        sel = " selected" if status == s else ""
        status_options += f'<option value="{s}"{sel}>{STATUS_LABELS_TR[s]}</option>'

    body = f"""
    <div class="container">
      <h1>Lead Dashboard</h1>
      <div class="stats">
        <div class="stat blue"><div class="n">{counts['TOTAL']}</div><div class="l">Toplam Lead</div></div>
        <div class="stat green"><div class="n">{today}</div><div class="l">Bugün Gelen</div></div>
        <div class="stat blue"><div class="n">{counts['NEW']}</div><div class="l">Yeni</div></div>
        <div class="stat orange"><div class="n">{counts['CONTACTED']}</div><div class="l">Arandı</div></div>
        <div class="stat orange"><div class="n">{counts['APPOINTMENT']}</div><div class="l">Randevu</div></div>
        <div class="stat green"><div class="n">{counts['WON']}</div><div class="l">Satış</div></div>
        <div class="stat red"><div class="n">{counts['LOST']}</div><div class="l">Kayıp</div></div>
      </div>

      <div class="card">
        <form method="get" action="/app" class="filters">
          <input type="text" name="q" placeholder="İsim, telefon veya lokasyon ara..." value="{escape(q)}" style="flex:1;min-width:200px">
          <select name="status">{status_options}</select>
          <button class="btn" type="submit">Filtrele</button>
          <a href="/app" class="btn" style="text-decoration:none;background:#888">Temizle</a>
        </form>

        <table>
          <thead><tr>
            <th>Ad Soyad</th><th>Telefon</th><th>Amaç</th><th>Bütçe</th>
            <th>Lokasyon</th><th>Zaman</th><th>Durum</th><th>Tarih</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
    """
    return HTMLResponse(_shell("Dashboard", body, tenant))


# =============== LEAD DETAY ===============

@app.get("/app/leads/{lead_pk}", response_class=HTMLResponse)
def lead_detail(request: Request, lead_pk: int):
    tid = require_tenant(request)
    tenant = get_tenant(tid)
    lead = get_lead(tid, lead_pk)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead bulunamadı")

    notes = list_notes(tid, lead_pk)
    reminders = list_reminders(tid, lead_pk)

    st = lead.get("status", "NEW")
    status_buttons = ""
    for s in ALL_STATUSES:
        active = " style=\"background:#1a1a2e;color:white\"" if s == st else ""
        status_buttons += f"""
          <form method="post" action="/app/leads/{lead_pk}/status">
            <input type="hidden" name="status" value="{s}">
            <button type="submit"{active}>{STATUS_LABELS_TR[s]}</button>
          </form>"""

    notes_html = ""
    if notes:
        for n in notes:
            notes_html += f'<div class="note-item"><div class="date">{_fmt_dt(n["created_at"])}</div>{escape(n["body"])}</div>'
    else:
        notes_html = '<p style="color:#aaa;font-size:13px">Henüz not yok.</p>'

    rem_html = ""
    if reminders:
        for r in reminders:
            check = "✓" if r["done"] else "○"
            done_form = "" if r["done"] else f"""
              <form method="post" action="/app/leads/{lead_pk}/reminder/{r['id']}/done" style="display:inline">
                <button type="submit" style="font-size:11px;padding:2px 8px;margin-left:8px">Tamamlandı</button>
              </form>"""
            rem_html += f'<div class="rem-item"><div class="date">{check} {_fmt_dt(r["remind_at"])}</div>{escape(r["body"] or "")}{done_form}</div>'
    else:
        rem_html = '<p style="color:#aaa;font-size:13px">Henüz hatırlatma yok.</p>'

    body = f"""
    <div class="container">
      <a href="/app" style="color:#666;text-decoration:none;font-size:13px">← Dashboard'a dön</a>
      <h1 style="margin-top:14px">{escape(lead.get('name') or 'İsimsiz Lead')}
        <span class="badge b-{st}" style="font-size:13px;margin-left:8px">{STATUS_LABELS_TR.get(st,st)}</span>
      </h1>

      <div class="grid2">
        <div class="card">
          <h2>Müşteri Bilgileri</h2>
          <div style="line-height:2">
            <div><strong>Telefon:</strong> <span class="phone">{escape(lead.get('phone') or '')}</span></div>
            <div><strong>Amaç:</strong> {escape(lead.get('purpose') or '—')}</div>
            <div><strong>Bütçe:</strong> {escape(lead.get('budget') or '—')}</div>
            <div><strong>Lokasyon:</strong> {escape(lead.get('location_preference') or '—')}</div>
            <div><strong>Zaman planı:</strong> {escape(lead.get('timeline') or '—')}</div>
            <div><strong>Geldiği yer:</strong> {escape(lead.get('source') or '—')}</div>
            <div class="date" style="margin-top:8px">Eklendi: {_fmt_dt(lead.get('created_at'))}</div>
            {f'<div class="date">Son temas: {_fmt_dt(lead.get("last_contact_at"))}</div>' if lead.get('last_contact_at') else ''}
          </div>

          <h2 style="margin-top:24px">Durum Değiştir</h2>
          <div class="row-actions">{status_buttons}</div>
        </div>

        <div>
          <div class="card">
            <h2>Notlar</h2>
            <form method="post" action="/app/leads/{lead_pk}/note">
              <textarea name="body" placeholder="Müşteriyle ilgili bir not yaz..." required></textarea>
              <button type="submit" class="button" style="margin-top:10px">Not Ekle</button>
            </form>
            <div style="margin-top:18px">{notes_html}</div>
          </div>

          <div class="card">
            <h2>Hatırlatmalar</h2>
            <form method="post" action="/app/leads/{lead_pk}/reminder">
              <label>Tarih/saat</label>
              <input type="datetime-local" name="remind_at" required>
              <label>Konu</label>
              <input type="text" name="body" placeholder="Örn: Mesaiden çıkınca ara">
              <button type="submit" class="button" style="margin-top:14px">Hatırlatma Ekle</button>
            </form>
            <div style="margin-top:18px">{rem_html}</div>
          </div>
        </div>
      </div>
    </div>
    """
    return HTMLResponse(_shell(f"Lead: {lead.get('name','')}", body, tenant))


@app.post("/app/leads/{lead_pk}/status")
def post_status(request: Request, lead_pk: int, status: str = Form(...)):
    tid = require_tenant(request)
    update_lead_status(tid, lead_pk, status)
    return RedirectResponse(f"/app/leads/{lead_pk}", status_code=303)


@app.post("/app/leads/{lead_pk}/note")
def post_note(request: Request, lead_pk: int, body: str = Form(...)):
    tid = require_tenant(request)
    if get_lead(tid, lead_pk):
        add_note(tid, lead_pk, body.strip())
    return RedirectResponse(f"/app/leads/{lead_pk}", status_code=303)


@app.post("/app/leads/{lead_pk}/reminder")
def post_reminder(
    request: Request, lead_pk: int,
    remind_at: str = Form(...), body: str = Form(""),
):
    tid = require_tenant(request)
    if get_lead(tid, lead_pk):
        add_reminder(tid, lead_pk, remind_at, body.strip())
    return RedirectResponse(f"/app/leads/{lead_pk}", status_code=303)


@app.post("/app/leads/{lead_pk}/reminder/{rid}/done")
def reminder_done(request: Request, lead_pk: int, rid: int):
    tid = require_tenant(request)
    mark_reminder_done(tid, rid)
    return RedirectResponse(f"/app/leads/{lead_pk}", status_code=303)


# =============== SETTINGS ===============

@app.get("/app/settings", response_class=HTMLResponse)
def settings_page(request: Request, saved: int = 0):
    tid = require_tenant(request)
    tenant = get_tenant(tid)
    s = get_tenant_settings(tid)

    saved_html = '<div class="card" style="background:#e8f8f0;color:#1e7c3a;padding:12px 18px;font-size:14px">Ayarlar kaydedildi.</div>' if saved else ""

    tones = ["profesyonel", "samimi", "lüks"]
    tone_opts = "".join(
        f'<option value="{t}"{" selected" if s.get("bot_tone","profesyonel")==t else ""}>{t.title()}</option>'
        for t in tones
    )

    body = f"""
    <div class="container">
      <h1>Ayarlar</h1>
      {saved_html}
      <div class="card">
        <form method="post" action="/app/settings">
          <h2>Ofis Bilgileri</h2>
          <label>Ofis Adı (botun kendini tanıtacağı isim)</label>
          <input type="text" name="office_name" value="{escape(tenant.get('office_name',''))}" required>
          <label>Yetkili Adı</label>
          <input type="text" name="contact_name" value="{escape(tenant.get('contact_name') or '')}">
          <label>Telefon</label>
          <input type="tel" name="phone" value="{escape(tenant.get('phone') or '')}">

          <h2 style="margin-top:24px">Bot Tonu</h2>
          <label>Konuşma tarzı</label>
          <select name="bot_tone">{tone_opts}</select>

          <label>Ek talimatlar (opsiyonel)</label>
          <textarea name="system_prompt_extras" placeholder="Örn: Müşteriye projemizin sosyal alanlarından bahset...">{escape(s.get('system_prompt_extras',''))}</textarea>

          <h2 style="margin-top:24px">WhatsApp Bağlantısı</h2>
          <label>Meta WhatsApp Token</label>
          <input type="text" name="whatsapp_token" value="{escape(s.get('whatsapp_token',''))}" placeholder="EAAxxx...">
          <label>Meta Phone Number ID</label>
          <input type="text" name="whatsapp_phone_id" value="{escape(s.get('whatsapp_phone_id',''))}" placeholder="123456789012345">
          <p style="color:#888;font-size:12px;margin-top:6px">Webhook URL: <code>https://&lt;domain&gt;/webhook</code> · Verify token: <code>{escape(VERIFY_TOKEN)}</code></p>

          <button type="submit" class="button" style="margin-top:24px">Kaydet</button>
        </form>
      </div>
    </div>
    """
    return HTMLResponse(_shell("Ayarlar", body, tenant))


def _sync_token_to_render(new_token: str):
    api_key = os.getenv("RENDER_API_KEY")
    service_id = os.getenv("RENDER_SERVICE_ID")
    if not api_key or not service_id:
        return
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"https://api.render.com/v1/services/{service_id}/env-vars",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                return
            items = resp.json()
            put_vars = []
            found = False
            for item in items:
                ev = item.get("envVar", item)
                key = ev.get("key", "")
                val = ev.get("value", "")
                if key == "WHATSAPP_TOKEN":
                    put_vars.append({"key": key, "value": new_token})
                    found = True
                else:
                    put_vars.append({"key": key, "value": val})
            if not found:
                put_vars.append({"key": "WHATSAPP_TOKEN", "value": new_token})
            resp2 = client.put(
                f"https://api.render.com/v1/services/{service_id}/env-vars",
                headers={"Authorization": f"Bearer {api_key}"},
                json=put_vars,
            )
            safe_print(f"Render token sync: {resp2.status_code}")
    except Exception as e:
        safe_print(f"Render token sync hatası: {e}")


@app.post("/app/settings")
def settings_save(
    request: Request,
    background_tasks: BackgroundTasks,
    office_name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    bot_tone: str = Form("profesyonel"),
    system_prompt_extras: str = Form(""),
    whatsapp_token: str = Form(""),
    whatsapp_phone_id: str = Form(""),
):
    tid = require_tenant(request)
    update_tenant(tid, office_name.strip(), contact_name.strip(), phone.strip())
    settings = get_tenant_settings(tid)
    new_token = whatsapp_token.strip()
    settings.update({
        "bot_tone": bot_tone,
        "system_prompt_extras": system_prompt_extras.strip(),
        "whatsapp_token": new_token,
        "whatsapp_phone_id": whatsapp_phone_id.strip(),
    })
    update_tenant_settings(tid, settings)
    if new_token:
        background_tasks.add_task(_sync_token_to_render, new_token)
    return RedirectResponse("/app/settings?saved=1", status_code=303)


# =============== EXCEL EXPORT ===============

@app.get("/app/export")
def export_excel(request: Request):
    tid = require_tenant(request)
    tenant = get_tenant(tid)
    leads = list_leads(tid)

    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl yüklü değil. requirements.txt'i kurun.")

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append([
        "Lead ID", "Ad Soyad", "Telefon", "Amaç", "Bütçe",
        "Lokasyon", "Zaman", "Durum", "Geldiği Yer", "Eklendi", "Son Temas",
    ])
    for L in leads:
        ws.append([
            L.get("lead_id", ""), L.get("name", ""), L.get("phone", ""),
            L.get("purpose", ""), L.get("budget", ""), L.get("location_preference", ""),
            L.get("timeline", ""), STATUS_LABELS_TR.get(L.get("status", ""), L.get("status", "")),
            L.get("source", ""), _fmt_dt(L.get("created_at")), _fmt_dt(L.get("last_contact_at")),
        ])
    # Otomatik kolon genişliği
    for col in ws.columns:
        max_len = max((len(str(c.value)) if c.value else 0 for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"emlakbot-leads-{tenant['office_name'].replace(' ','_')}-{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# =============== WHATSAPP WEBHOOK ===============

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        safe_print("Webhook verified")
        return PlainTextResponse(challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Verification token mismatch")


def _process_whatsapp_message(body: dict):
    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        metadata = value.get("metadata", {})

        if not messages:
            return

        # Tenant'ı phone_number_id'den çöz
        phone_id = metadata.get("phone_number_id")
        tenant = find_tenant_by_whatsapp_phone_id(phone_id) if phone_id else None
        if not tenant:
            safe_print(f"Bu phone_id için tenant bulunamadı: {phone_id}")
            return

        tid = tenant["id"]
        settings = get_tenant_settings(tid)

        msg = messages[0]
        if msg.get("type") != "text":
            return

        user_phone = msg.get("from")
        user_message = msg.get("text", {}).get("body") or ""
        user_name = "Bilinmiyor"
        if contacts:
            user_name = contacts[0].get("profile", {}).get("name", "Bilinmiyor")

        safe_print(f"[Tenant {tid}] Gelen Mesaj ({user_phone} - {user_name}): {user_message}")

        # Geçmişi DB'den çek
        chat_history = get_recent_messages(tid, user_phone, limit=20)
        ai_response = handle_message(
            user_message, user_phone,
            office_name=tenant["office_name"],
            tenant_settings=settings,
            chat_history=chat_history,
        )
        if not ai_response:
            return

        # Geçmişi kaydet
        append_message(tid, user_phone, "user", user_message)
        append_message(tid, user_phone, "assistant", ai_response)

        # Thinking bloklarını temizle (<think>...</think> veya <thinking>...</thinking>)
        ai_response = re.sub(r'<think(?:ing)?[\s\S]*?</think(?:ing)?>', '', ai_response, flags=re.IGNORECASE).strip()

        # JSON kalifikasyon bloğu var mı? (her zaman sil — müşteriye asla gösterme)
        json_match = re.search(r'\{[\s\S]*?"status"[\s\S]*?\}', ai_response)
        clean_response = ai_response
        if json_match:
            clean_response = ai_response.replace(json_match.group(0), "").strip()
            try:
                data = json.loads(json_match.group(0))
                if data.get("status") == "QUALIFIED":
                    safe_print(f"[Tenant {tid}] Kalifikasyon: {data}")
                    save_qualified_lead(
                        tenant_id=tid,
                        name=user_name,
                        phone=user_phone,
                        purpose=data.get("purpose", ""),
                        budget=data.get("budget", ""),
                        location_preference=data.get("location_preference", ""),
                        timeline=data.get("timeline", ""),
                    )
            except json.JSONDecodeError as e:
                safe_print(f"JSON çözüm hatası: {e}")

        if clean_response.strip():
            send_whatsapp_message(
                user_phone, clean_response.strip(),
                token=settings.get("whatsapp_token"),
                phone_id=settings.get("whatsapp_phone_id"),
            )

    except Exception as e:
        safe_print(f"Mesaj işleme hatası: {e}")


@app.post("/webhook")
async def webhook_post(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        background_tasks.add_task(_process_whatsapp_message, body)
        return {"status": "ok"}
    except Exception as e:
        safe_print(f"Webhook POST hatası: {e}")
        return {"status": "error"}


# =============== HEALTH ===============

@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "emlakbot"}


# =============== HELPERS ===============

def _fmt_dt(s: str | None) -> str:
    if not s:
        return ""
    # ISO veya eski "dd.mm.yyyy HH:MM" formatlarını hoş bir şekilde göster
    try:
        if "T" in s:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%d.%m.%Y %H:%M")
        return s
    except Exception:
        return s
