"""Şifre hash'leme ve oturum yardımcıları."""

import bcrypt
from typing import Optional
from fastapi import Request, HTTPException, Depends
from starlette.responses import RedirectResponse


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def current_tenant_id(request: Request) -> Optional[int]:
    return request.session.get("tenant_id")


def require_tenant(request: Request) -> int:
    """FastAPI dependency: login değilse /login'e yönlendirir."""
    tid = current_tenant_id(request)
    if not tid:
        # 401 yerine yönlendirme istiyoruz; HTTPException ile özel handle yapacağız.
        raise HTTPException(status_code=401, detail="login_required")
    return tid


def login_user(request: Request, tenant_id: int):
    request.session["tenant_id"] = tenant_id


def logout_user(request: Request):
    request.session.clear()
