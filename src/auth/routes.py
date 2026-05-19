"""Kayıt / giriş / çıkış endpoint'leri."""

import re
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from src.database.local_db import (
    create_tenant, get_tenant_by_email, get_tenant,
)
from src.auth.security import (
    hash_password, verify_password, login_user, logout_user, current_tenant_id,
)

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _layout(title: str, body: str, error: str = "") -> str:
    err_html = f'<div class="err">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="UTF-8"><title>{title} — EmlakBot</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#333}}
.card{{background:white;border-radius:16px;padding:40px;width:100%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.brand{{font-size:24px;font-weight:700;color:#1a1a2e;text-align:center;margin-bottom:6px}}
.brand span{{color:#27ae60}}
.subtitle{{text-align:center;color:#888;font-size:13px;margin-bottom:28px}}
h2{{font-size:18px;margin-bottom:20px;color:#1a1a2e}}
label{{display:block;font-size:13px;color:#555;margin-bottom:6px;margin-top:14px;font-weight:500}}
input{{width:100%;padding:12px 14px;border:1px solid #e0e0e0;border-radius:8px;font-size:14px;transition:border .15s}}
input:focus{{outline:none;border-color:#1a1a2e}}
button{{width:100%;background:#1a1a2e;color:white;border:none;padding:14px;border-radius:8px;font-size:15px;font-weight:600;margin-top:24px;cursor:pointer;transition:opacity .2s}}
button:hover{{opacity:.88}}
.err{{background:#fee;color:#c33;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px}}
.link{{text-align:center;margin-top:20px;font-size:13px;color:#666}}
.link a{{color:#1a1a2e;font-weight:600;text-decoration:none}}
</style></head><body>
<div class="card">
  <div class="brand">Emlak<span>Bot</span></div>
  <div class="subtitle">WhatsApp lead yakalama + mini CRM</div>
  {err_html}
  {body}
</div></body></html>"""


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    if current_tenant_id(request):
        return RedirectResponse("/app", status_code=303)
    body = """
    <h2>Giriş Yap</h2>
    <form method="post" action="/login">
      <label>E-posta</label>
      <input type="email" name="email" required autofocus>
      <label>Şifre</label>
      <input type="password" name="password" required>
      <button type="submit">Giriş Yap</button>
    </form>
    <div class="link">Hesabın yok mu? <a href="/register">14 gün ücretsiz dene</a></div>
    """
    return HTMLResponse(_layout("Giriş", body, error))


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    t = get_tenant_by_email(email)
    if not t or not verify_password(password, t["password_hash"]):
        return RedirectResponse("/login?error=E-posta+veya+şifre+hatalı", status_code=303)
    login_user(request, t["id"])
    return RedirectResponse("/app", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: str = ""):
    if current_tenant_id(request):
        return RedirectResponse("/app", status_code=303)
    body = """
    <h2>14 Gün Ücretsiz Dene</h2>
    <form method="post" action="/register">
      <label>Ofis / İsim</label>
      <input name="office_name" required placeholder="Örn: Yıldız Emlak">
      <label>Yetkili Adı</label>
      <input name="contact_name" placeholder="Ad Soyad">
      <label>E-posta</label>
      <input type="email" name="email" required>
      <label>Şifre (en az 8 karakter)</label>
      <input type="password" name="password" required minlength="8">
      <button type="submit">Hesap Oluştur</button>
    </form>
    <div class="link">Zaten hesabın var mı? <a href="/login">Giriş yap</a></div>
    """
    return HTMLResponse(_layout("Kayıt", body, error))


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    office_name: str = Form(...),
    contact_name: str = Form(""),
):
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        return RedirectResponse("/register?error=Geçersiz+e-posta", status_code=303)
    if len(password) < 8:
        return RedirectResponse("/register?error=Şifre+en+az+8+karakter+olmalı", status_code=303)
    if get_tenant_by_email(email):
        return RedirectResponse("/register?error=Bu+e-posta+zaten+kayıtlı", status_code=303)
    if not office_name.strip():
        return RedirectResponse("/register?error=Ofis+ismi+gerekli", status_code=303)

    tenant_id = create_tenant(
        email=email,
        password_hash=hash_password(password),
        office_name=office_name.strip(),
        contact_name=contact_name.strip(),
    )
    login_user(request, tenant_id)
    return RedirectResponse("/app", status_code=303)


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=303)
