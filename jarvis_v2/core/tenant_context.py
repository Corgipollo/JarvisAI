"""tenant_context.py - Aislamiento multi-tenant via contextvars + state dual.

Arquitectura híbrida:
  - contextvars: source of truth runtime, thread-safe + asyncio-aware.
    Helpers (memory_manager, brain proxy, closed_loop telemetry) leen
    current_tenant.get() sin necesidad de pasar el tenant_id por
    parámetros en cada signature.
  - JarvisState.tenant_id: copia explícita que viaja con el state de
    LangGraph para que los checkpoints persistan en disco con tenant
    correcto y el trace sea auditable.

Uso típico:

    from jarvis_v2.core.tenant_context import tenant_session, get_tenant

    with tenant_session("acme-corp"):
        # Aquí cualquier helper que llame get_tenant() ve 'acme-corp'.
        # Las queries SQL filtran por tenant. La memoria se escribe a
        # data/tenants/acme-corp/memory.db.
        result = run_objective("Mi tienda Shopify roto", tenant_id="acme-corp")
    # Al salir del with, contextvar vuelve a su valor previo (default).

API publica:
    tenant_session(tenant_id) -> context manager
    get_tenant() -> str ("default" si no hay session activa)
    get_industry() -> str  (cacheado desde la última route())
    get_mask() -> dict     (cacheado desde la última route())
    tenant_db_path() -> Path
    tenant_logs_dir() -> Path
    tenant_secrets_path() -> Path
    bootstrap_tenant(tenant_id, legal_name, industry, ...) -> Path
        Crea data/tenants/{id}/ con schema multi_tenant aplicado.

Diseño defensivo:
    - get_tenant() jamás retorna None: 'default' es fallback seguro.
    - tenant_db_path() crea el dir + applica schema si falta.
    - Si tenant_session se anida, solo el más interno aplica.
"""
from __future__ import annotations

import contextvars
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TENANTS_ROOT = ROOT / "data" / "tenants"
SCHEMA_PATH = ROOT / "jarvis_v2" / "core" / "multi_tenant.sql"

_current_tenant: contextvars.ContextVar[str] = contextvars.ContextVar(
    "jarvis_current_tenant", default="default"
)
_current_industry: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "jarvis_current_industry", default=None
)
_current_mask: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "jarvis_current_mask", default=None
)


def get_tenant() -> str:
    """Tenant activo. 'default' si no hay session abierta."""
    return _current_tenant.get()


def get_industry() -> str | None:
    return _current_industry.get()


def get_mask() -> dict | None:
    return _current_mask.get()


def tenant_db_path(tenant_id: str | None = None) -> Path:
    """Path al SQLite del tenant. Auto-crea dir + schema si falta."""
    tid = tenant_id or get_tenant()
    db = TENANTS_ROOT / tid / "memory.db"
    if not db.exists():
        _bootstrap_db(db, tid)
    return db


def tenant_logs_dir(tenant_id: str | None = None) -> Path:
    tid = tenant_id or get_tenant()
    d = TENANTS_ROOT / tid / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tenant_secrets_path(tenant_id: str | None = None) -> Path:
    tid = tenant_id or get_tenant()
    return TENANTS_ROOT / tid / "secrets.enc"


def _bootstrap_db(db: Path, tenant_id: str) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # Reemplaza el seed 'default' por el tenant actual si distinto
    conn = sqlite3.connect(str(db), timeout=10)
    conn.executescript(sql)
    if tenant_id != "default":
        conn.execute(
            "INSERT OR IGNORE INTO tenant_meta(tenant_id, legal_name, industry) "
            "VALUES (?, ?, ?)",
            (tenant_id, tenant_id, "generic"),
        )
    conn.commit()
    conn.close()


def bootstrap_tenant(tenant_id: str, legal_name: str,
                      industry: str = "generic", plan: str = "standard",
                      contact_email: str | None = None) -> Path:
    """Provisiona un tenant nuevo: dir + schema + row en tenant_meta.

    Idempotente: si ya existe, solo actualiza metadata.
    """
    db = TENANTS_ROOT / tenant_id / "memory.db"
    _bootstrap_db(db, tenant_id)
    conn = sqlite3.connect(str(db), timeout=10)
    conn.execute(
        "INSERT INTO tenant_meta(tenant_id, legal_name, industry, plan, "
        "contact_email) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(tenant_id) DO UPDATE SET legal_name=excluded.legal_name, "
        "industry=excluded.industry, plan=excluded.plan, "
        "contact_email=excluded.contact_email",
        (tenant_id, legal_name, industry, plan, contact_email),
    )
    conn.commit()
    conn.close()
    return db


@contextmanager
def tenant_session(tenant_id: str,
                    industry: str | None = None,
                    mask: dict | None = None) -> Iterator[dict]:
    """Context manager: set contextvars para tenant + industry + mask.

    Si industry/mask no se pasan, intenta cargarlos via industry_router
    cuando route() haya sido llamado antes; sino dejan en None.

    Devuelve la mask (puede ser None) para uso opcional.

    Pattern de uso normal:

        from jarvis_v2.core.industry_router import route
        m = route(user_input, tenant_id="acme")
        with tenant_session("acme", industry=m["industry"], mask=m):
            result = run_objective(user_input, tenant_id="acme")
    """
    tok_t = _current_tenant.set(tenant_id)
    tok_i = _current_industry.set(industry)
    tok_m = _current_mask.set(mask)
    try:
        # Asegurar que la DB del tenant existe (importante para concurrencia)
        tenant_db_path(tenant_id)
        yield mask or {}
    finally:
        _current_tenant.reset(tok_t)
        _current_industry.reset(tok_i)
        _current_mask.reset(tok_m)


def log_action(action_type: str, target_or_command: str = "",
                success: int = 1, cost_usd: float = 0.0,
                elapsed_ms: int | None = None, error: str | None = None,
                objective_summary: str = "",
                initiated_by: str = "agent") -> None:
    """Helper rapido: escribe a action_log del tenant actual.

    Llamable desde cualquier nodo del graph o skill sin pasar tenant_id.
    Fails-soft: si la DB no se puede escribir, log a stderr y continua.
    """
    tid = get_tenant()
    db = tenant_db_path(tid)
    try:
        conn = sqlite3.connect(str(db), timeout=5)
        conn.execute(
            "INSERT INTO action_log(tenant_id, industry, action_type, "
            "objective_summary, target_or_command, cost_usd, success, "
            "elapsed_ms, error, initiated_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tid, get_industry(), action_type, objective_summary[:500],
             target_or_command[:500], cost_usd, success, elapsed_ms,
             (error or "")[:500], initiated_by),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[tenant_context] log_action fail: {e}", file=sys.stderr)


def log_spend(provider: str, model: str, tokens_in: int, tokens_out: int,
              cost_usd: float, objective_id: str = "") -> None:
    """Helper: escribe a spend_ledger del tenant actual."""
    tid = get_tenant()
    db = tenant_db_path(tid)
    try:
        conn = sqlite3.connect(str(db), timeout=5)
        conn.execute(
            "INSERT INTO spend_ledger(tenant_id, provider, model, tokens_in, "
            "tokens_out, cost_usd, objective_id) VALUES (?,?,?,?,?,?,?)",
            (tid, provider, model, tokens_in, tokens_out, cost_usd, objective_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[tenant_context] log_spend fail: {e}", file=sys.stderr)


if __name__ == "__main__":
    import json
    # Smoke test: 2 sessions concurrentes via threading, verificar
    # aislamiento.
    import threading
    import time

    bootstrap_tenant("acme-corp", "ACME Corp E-commerce", "ecommerce")
    bootstrap_tenant("granos-sa", "Granos del Norte SA", "agri_logistics")

    seen = {"acme-corp": [], "granos-sa": []}

    def worker(tid):
        with tenant_session(tid):
            for _ in range(5):
                seen[tid].append(get_tenant())
                time.sleep(0.01)
                log_action(
                    "test", target_or_command=f"smoke_{tid}",
                    success=1, elapsed_ms=10,
                )

    t1 = threading.Thread(target=worker, args=("acme-corp",))
    t2 = threading.Thread(target=worker, args=("granos-sa",))
    t1.start(); t2.start(); t1.join(); t2.join()

    print("seen acme-corp:", seen["acme-corp"])
    print("seen granos-sa:", seen["granos-sa"])

    # Verify aislamiento: cada DB solo tiene rows de su tenant
    for tid in ("acme-corp", "granos-sa"):
        db = tenant_db_path(tid)
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        cur.execute(
            "SELECT tenant_id, COUNT(*) FROM action_log GROUP BY tenant_id"
        )
        rows = cur.fetchall()
        print(f"  {tid} db rows: {rows}")
        conn.close()
