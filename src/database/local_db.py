"""
EmlakBot — Çok kiracılı veri katmanı.

Ortam:
  DATABASE_URL  set → PostgreSQL (Render/Supabase)
  DATABASE_URL  yok → SQLite    (yerel geliştirme)

Tablolar:
- tenants          : Hesap (emlakçı/ofis). Login + ofise özel ayarlar.
- leads            : Potansiyel müşteriler. tenant_id ile izole.
- lead_notes       : Lead başına serbest notlar.
- lead_reminders   : Zamanlanmış hatırlatmalar.
- conversations    : WhatsApp sohbet geçmişi.
"""

import os
import json
from datetime import datetime
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_PG = bool(DATABASE_URL)

# Lead durum sabitleri
STATUS_NEW = "NEW"
STATUS_CONTACTED = "CONTACTED"
STATUS_APPOINTMENT = "APPOINTMENT"
STATUS_WON = "WON"
STATUS_LOST = "LOST"

ALL_STATUSES = [STATUS_NEW, STATUS_CONTACTED, STATUS_APPOINTMENT, STATUS_WON, STATUS_LOST]

STATUS_LABELS_TR = {
    STATUS_NEW: "Yeni",
    STATUS_CONTACTED: "Arandı",
    STATUS_APPOINTMENT: "Randevu",
    STATUS_WON: "Satış",
    STATUS_LOST: "Kayıp",
}

# ─────────────────────────────────────────────
# Bağlantı katmanı — PG veya SQLite
# ─────────────────────────────────────────────

if _USE_PG:
    import psycopg2
    import psycopg2.extras

    DB_PATH = None

    def _connect():
        conn = psycopg2.connect(DATABASE_URL)
        return conn

    def _execute(conn, sql, args=()):
        sql = sql.replace("?", "%s")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, args)
        return cur

    def _insert(conn, sql, args=()):
        sql = sql.replace("?", "%s").rstrip(";") + " RETURNING id"
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, args)
        conn.commit()
        row = cur.fetchone()
        return row["id"] if row else None

    def _fetchone(cur):
        row = cur.fetchone()
        return dict(row) if row else None

    def _fetchall(cur):
        return [dict(r) for r in cur.fetchall()]

    def _commit(conn):
        conn.commit()

    def _close(conn):
        conn.close()

    _PG_AUTO = "SERIAL PRIMARY KEY"
    _PG_INT_AUTO = "BIGSERIAL PRIMARY KEY"

else:
    import sqlite3

    DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "leads.db"))

    def _connect():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _execute(conn, sql, args=()):
        return conn.execute(sql, args)

    def _insert(conn, sql, args=()):
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid

    def _fetchone(cur):
        row = cur.fetchone()
        return dict(row) if row else None

    def _fetchall(cur):
        return [dict(r) for r in cur.fetchall()]

    def _commit(conn):
        conn.commit()

    def _close(conn):
        conn.close()

    _PG_AUTO = "INTEGER PRIMARY KEY AUTOINCREMENT"
    _PG_INT_AUTO = "INTEGER PRIMARY KEY AUTOINCREMENT"


# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────

def init_db():
    """Tabloları oluşturur ve gerekirse eski şemayı taşır."""
    conn = _connect()
    try:
        if _USE_PG:
            _init_pg(conn)
        else:
            _init_sqlite(conn)
        _commit(conn)
    finally:
        _close(conn)


def _init_pg(conn):
    _execute(conn, f"""
        CREATE TABLE IF NOT EXISTS tenants (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            office_name TEXT NOT NULL,
            contact_name TEXT,
            phone TEXT,
            plan TEXT DEFAULT 'trial',
            trial_ends_at TEXT,
            settings_json TEXT DEFAULT '{{}}',
            created_at TEXT NOT NULL
        )
    """)
    _execute(conn, f"""
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            lead_id TEXT NOT NULL,
            name TEXT,
            phone TEXT,
            purpose TEXT,
            budget TEXT,
            location_preference TEXT,
            timeline TEXT,
            status TEXT NOT NULL DEFAULT 'NEW',
            source TEXT,
            created_at TEXT NOT NULL,
            last_contact_at TEXT,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )
    """)
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id)")
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(tenant_id, phone)")
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(tenant_id, status)")
    _execute(conn, f"""
        CREATE TABLE IF NOT EXISTS lead_notes (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_notes_lead ON lead_notes(lead_id)")
    _execute(conn, f"""
        CREATE TABLE IF NOT EXISTS lead_reminders (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            body TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_reminders_lead ON lead_reminders(lead_id)")
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_reminders_due ON lead_reminders(tenant_id, done, remind_at)")
    _execute(conn, f"""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    _execute(conn, "CREATE INDEX IF NOT EXISTS idx_conv_lookup ON conversations(tenant_id, phone, id)")


def _init_sqlite(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            office_name TEXT NOT NULL,
            contact_name TEXT,
            phone TEXT,
            plan TEXT DEFAULT 'trial',
            trial_ends_at TEXT,
            settings_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    # Eski (tek-kiracılı) leads tablosu varsa taşı
    leads_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
    ).fetchone()
    legacy_renamed = False
    if leads_exists:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()]
        if "tenant_id" not in cols:
            conn.execute("ALTER TABLE leads RENAME TO leads_legacy")
            legacy_renamed = True

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            lead_id TEXT NOT NULL,
            name TEXT,
            phone TEXT,
            purpose TEXT,
            budget TEXT,
            location_preference TEXT,
            timeline TEXT,
            status TEXT NOT NULL DEFAULT 'NEW',
            source TEXT,
            created_at TEXT NOT NULL,
            last_contact_at TEXT,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(tenant_id, phone)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(tenant_id, status)")

    if legacy_renamed:
        _copy_legacy_leads_to_new(conn)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_lead ON lead_notes(lead_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            body TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_lead ON lead_reminders(lead_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due ON lead_reminders(tenant_id, done, remind_at)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_lookup ON conversations(tenant_id, phone, id)")
    conn.commit()


def _copy_legacy_leads_to_new(conn):
    import bcrypt
    c = conn
    row = c.execute("SELECT id FROM tenants ORDER BY id LIMIT 1").fetchone()
    if row:
        default_tid = row[0] if not hasattr(row, "keys") else row["id"]
    else:
        now = datetime.now().isoformat()
        pw_hash = bcrypt.hashpw(b"demo1234", bcrypt.gensalt()).decode("utf-8")
        c.execute(
            "INSERT INTO tenants (email, password_hash, office_name, contact_name, plan, created_at) VALUES (?,?,?,?,?,?)",
            ("demo@emlakbot.test", pw_hash, "Demo Emlak Ofisi", "Demo Danışman", "trial", now),
        )
        default_tid = c.lastrowid
        print(f"[Migration] Varsayılan tenant oluşturuldu (id={default_tid})")

    legacy_cols = [r[1] for r in c.execute("PRAGMA table_info(leads_legacy)").fetchall()]
    def has(col): return col in legacy_cols

    select_parts = [
        f"{default_tid} AS tenant_id",
        "lead_id" if has("lead_id") else "'' AS lead_id",
        "name" if has("name") else "'' AS name",
        "phone" if has("phone") else "'' AS phone",
        "purpose" if has("purpose") else "'' AS purpose",
        "budget" if has("budget") else "'' AS budget",
        "location_preference" if has("location_preference") else "'' AS location_preference",
        "timeline" if has("timeline") else "'' AS timeline",
        "'NEW' AS status",
        "'whatsapp' AS source",
        "created_at" if has("created_at") else "datetime('now') AS created_at",
    ]
    c.execute(f"""
        INSERT INTO leads (tenant_id, lead_id, name, phone, purpose, budget,
           location_preference, timeline, status, source, created_at)
        SELECT {', '.join(select_parts)} FROM leads_legacy
    """)
    n = c.execute("SELECT changes()").fetchone()[0]
    c.execute("DROP TABLE leads_legacy")
    print(f"[Migration] {n} eski lead yeni şemaya taşındı.")


def ensure_default_tenant() -> int:
    from src.auth.security import hash_password
    conn = _connect()
    try:
        row = _fetchone(_execute(conn, "SELECT id FROM tenants ORDER BY id LIMIT 1"))
        if row:
            return row["id"]
        now = datetime.now().isoformat()
        return _insert(conn,
            "INSERT INTO tenants (email, password_hash, office_name, contact_name, plan, created_at) VALUES (?,?,?,?,?,?)",
            ("demo@emlakbot.test", hash_password("demo1234"), "Demo Emlak Ofisi", "Demo Danışman", "trial", now),
        )
    finally:
        _close(conn)


# ─────────────────────────────────────────────
# TENANT
# ─────────────────────────────────────────────

def create_tenant(email: str, password_hash: str, office_name: str,
                  contact_name: str = "", phone: str = "") -> int:
    now = datetime.now().isoformat()
    conn = _connect()
    try:
        return _insert(conn,
            "INSERT INTO tenants (email, password_hash, office_name, contact_name, phone, plan, created_at) VALUES (?,?,?,?,?,'trial',?)",
            (email.lower().strip(), password_hash, office_name, contact_name, phone, now),
        )
    finally:
        _close(conn)


def get_tenant_by_email(email: str) -> Optional[dict]:
    conn = _connect()
    try:
        return _fetchone(_execute(conn, "SELECT * FROM tenants WHERE email = ?", (email.lower().strip(),)))
    finally:
        _close(conn)


def get_tenant(tenant_id: int) -> Optional[dict]:
    conn = _connect()
    try:
        return _fetchone(_execute(conn, "SELECT * FROM tenants WHERE id = ?", (tenant_id,)))
    finally:
        _close(conn)


def get_tenant_settings(tenant_id: int) -> dict:
    t = get_tenant(tenant_id)
    if not t:
        return {}
    try:
        return json.loads(t.get("settings_json") or "{}")
    except json.JSONDecodeError:
        return {}


def update_tenant_settings(tenant_id: int, settings: dict):
    conn = _connect()
    try:
        _execute(conn, "UPDATE tenants SET settings_json = ? WHERE id = ?",
                 (json.dumps(settings, ensure_ascii=False), tenant_id))
        _commit(conn)
    finally:
        _close(conn)


def update_tenant(tenant_id: int, office_name: str, contact_name: str, phone: str):
    conn = _connect()
    try:
        _execute(conn,
            "UPDATE tenants SET office_name=?, contact_name=?, phone=? WHERE id=?",
            (office_name, contact_name, phone, tenant_id))
        _commit(conn)
    finally:
        _close(conn)


def find_tenant_by_whatsapp_phone_id(phone_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        rows = _fetchall(_execute(conn, "SELECT * FROM tenants"))
        for t in rows:
            settings = json.loads(t.get("settings_json") or "{}")
            if settings.get("whatsapp_phone_id") == phone_id:
                return t
        # Fallback: global WHATSAPP_PHONE_ID env var eşleşirse ilk tenant'ı dön
        global_phone_id = os.getenv("WHATSAPP_PHONE_ID", "").strip()
        if global_phone_id and phone_id == global_phone_id and rows:
            return rows[0]
        return None
    finally:
        _close(conn)


# ─────────────────────────────────────────────
# LEADS
# ─────────────────────────────────────────────

def insert_lead(tenant_id: int, lead_id: str, name: str, phone: str, purpose: str,
                budget: str, location_preference: str, timeline: str,
                source: str = "whatsapp") -> int:
    now = datetime.now().isoformat()
    conn = _connect()
    try:
        return _insert(conn,
            "INSERT INTO leads (tenant_id, lead_id, name, phone, purpose, budget, location_preference, timeline, status, source, created_at) VALUES (?,?,?,?,?,?,?,?,'NEW',?,?)",
            (tenant_id, lead_id, name, phone, purpose, budget, location_preference, timeline, source, now),
        )
    finally:
        _close(conn)


def list_leads(tenant_id: int, status: Optional[str] = None,
               search: Optional[str] = None) -> list:
    sql = "SELECT * FROM leads WHERE tenant_id = ?"
    args = [tenant_id]
    if status and status in ALL_STATUSES:
        sql += " AND status = ?"
        args.append(status)
    if search:
        sql += " AND (name LIKE ? OR phone LIKE ? OR location_preference LIKE ?)"
        pat = f"%{search}%"
        args.extend([pat, pat, pat])
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return _fetchall(_execute(conn, sql, args))
    finally:
        _close(conn)


def get_lead(tenant_id: int, lead_pk: int) -> Optional[dict]:
    conn = _connect()
    try:
        return _fetchone(_execute(conn,
            "SELECT * FROM leads WHERE id = ? AND tenant_id = ?", (lead_pk, tenant_id)))
    finally:
        _close(conn)


def update_lead_status(tenant_id: int, lead_pk: int, status: str) -> bool:
    if status not in ALL_STATUSES:
        return False
    now = datetime.now().isoformat()
    conn = _connect()
    try:
        cur = _execute(conn,
            "UPDATE leads SET status = ?, last_contact_at = ? WHERE id = ? AND tenant_id = ?",
            (status, now, lead_pk, tenant_id))
        _commit(conn)
        return (cur.rowcount > 0) if hasattr(cur, "rowcount") else True
    finally:
        _close(conn)


def count_by_status(tenant_id: int) -> dict:
    conn = _connect()
    try:
        rows = _fetchall(_execute(conn,
            "SELECT status, COUNT(*) c FROM leads WHERE tenant_id = ? GROUP BY status", (tenant_id,)))
        counts = {s: 0 for s in ALL_STATUSES}
        for r in rows:
            counts[r["status"]] = r["c"]
        counts["TOTAL"] = sum(counts.values())
        return counts
    finally:
        _close(conn)


def count_today(tenant_id: int) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _connect()
    try:
        if _USE_PG:
            row = _fetchone(_execute(conn,
                "SELECT COUNT(*) c FROM leads WHERE tenant_id = ? AND substr(created_at,1,10) = ?",
                (tenant_id, today)))
        else:
            row = _fetchone(_execute(conn,
                "SELECT COUNT(*) c FROM leads WHERE tenant_id = ? AND substr(created_at,1,10) = ?",
                (tenant_id, today)))
        return row["c"] if row else 0
    finally:
        _close(conn)


# ─────────────────────────────────────────────
# NOTES
# ─────────────────────────────────────────────

def add_note(tenant_id: int, lead_pk: int, body: str) -> int:
    now = datetime.now().isoformat()
    conn = _connect()
    try:
        return _insert(conn,
            "INSERT INTO lead_notes (tenant_id, lead_id, body, created_at) VALUES (?,?,?,?)",
            (tenant_id, lead_pk, body, now))
    finally:
        _close(conn)


def list_notes(tenant_id: int, lead_pk: int) -> list:
    conn = _connect()
    try:
        return _fetchall(_execute(conn,
            "SELECT * FROM lead_notes WHERE tenant_id = ? AND lead_id = ? ORDER BY id DESC",
            (tenant_id, lead_pk)))
    finally:
        _close(conn)


# ─────────────────────────────────────────────
# REMINDERS
# ─────────────────────────────────────────────

def add_reminder(tenant_id: int, lead_pk: int, remind_at: str, body: str = "") -> int:
    now = datetime.now().isoformat()
    conn = _connect()
    try:
        return _insert(conn,
            "INSERT INTO lead_reminders (tenant_id, lead_id, remind_at, body, created_at) VALUES (?,?,?,?,?)",
            (tenant_id, lead_pk, remind_at, body, now))
    finally:
        _close(conn)


def list_reminders(tenant_id: int, lead_pk: Optional[int] = None,
                   only_pending: bool = False) -> list:
    sql = "SELECT * FROM lead_reminders WHERE tenant_id = ?"
    args = [tenant_id]
    if lead_pk is not None:
        sql += " AND lead_id = ?"
        args.append(lead_pk)
    if only_pending:
        sql += " AND done = 0"
    sql += " ORDER BY remind_at ASC"
    conn = _connect()
    try:
        return _fetchall(_execute(conn, sql, args))
    finally:
        _close(conn)


def mark_reminder_done(tenant_id: int, reminder_id: int) -> bool:
    conn = _connect()
    try:
        cur = _execute(conn,
            "UPDATE lead_reminders SET done = 1 WHERE id = ? AND tenant_id = ?",
            (reminder_id, tenant_id))
        _commit(conn)
        return (cur.rowcount > 0) if hasattr(cur, "rowcount") else True
    finally:
        _close(conn)


# ─────────────────────────────────────────────
# CONVERSATIONS
# ─────────────────────────────────────────────

def append_message(tenant_id: int, phone: str, role: str, content: str):
    now = datetime.now().isoformat()
    conn = _connect()
    try:
        _insert(conn,
            "INSERT INTO conversations (tenant_id, phone, role, content, created_at) VALUES (?,?,?,?,?)",
            (tenant_id, phone, role, content, now))
    finally:
        _close(conn)


def get_recent_messages(tenant_id: int, phone: str, limit: int = 20) -> list:
    conn = _connect()
    try:
        rows = _fetchall(_execute(conn,
            "SELECT role, content FROM conversations WHERE tenant_id = ? AND phone = ? ORDER BY id DESC LIMIT ?",
            (tenant_id, phone, limit)))
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        _close(conn)
