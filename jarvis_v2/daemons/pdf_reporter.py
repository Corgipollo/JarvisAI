"""pdf_reporter.py - Genera PDF resumen 1 pagina cada 30 min.

Output: C:\\reportes\\jarvis_YYYYMMDD_HHMM.pdf

Contenido (breve, conciso, leible en 30 segundos):
  - Estado del negocio (KPIs)
  - Que hizo en los ultimos 30 min (tasks done/failed/tipo)
  - Alertas si las hay
  - Proximo paso recomendado

Registrado como schtask Jarvis_PDF_Report cada 30 min.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REPORTS_DIR = Path(r"C:\reportes")
TENANT_DB = ROOT / "data" / "tenants" / "default" / "memory.db"
TASK_QUEUE = ROOT / "data" / "task_queue.json"
URL_FILE = ROOT / "data" / "public_url.txt"


def _ensure_reportlab():
    try:
        import reportlab
        return True
    except ImportError:
        import subprocess
        print("[pdf_reporter] installing reportlab...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "reportlab"])
        return True


def gather_business_state() -> dict:
    s = {
        "leads_total": 0, "leads_sent": 0, "leads_replied": 0,
        "tenants_total": 0, "tenants_paid": 0,
        "revenue_30d_usd": 0.0,
        "queue_pending": 0, "queue_done_30min": 0, "queue_failed_30min": 0,
        "daemons_up": [],
    }
    # CRM + spend
    try:
        if TENANT_DB.exists():
            conn = sqlite3.connect(str(TENANT_DB), timeout=5)
            cur = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END) FROM outreach_leads")
            row = cur.fetchone()
            if row:
                s["leads_total"], s["leads_sent"], s["leads_replied"] = (
                    row[0] or 0, row[1] or 0, row[2] or 0)
            try:
                cur = conn.execute(
                    "SELECT ROUND(SUM(cost_usd), 4) FROM spend_ledger "
                    "WHERE ts > datetime('now', '-30 days')")
                s["revenue_30d_usd"] = cur.fetchone()[0] or 0.0
            except Exception:
                pass
            conn.close()
    except Exception:
        pass
    # Tenants count
    td = ROOT / "data" / "tenants"
    if td.exists():
        ts = [d for d in td.iterdir() if d.is_dir()]
        s["tenants_total"] = len(ts)
        for t in ts:
            db = t / "memory.db"
            if not db.exists():
                continue
            try:
                c = sqlite3.connect(str(db), timeout=3)
                cur = c.execute(
                    "SELECT COUNT(*) FROM tenant_meta "
                    "WHERE stripe_subscription_status = 'active'")
                if cur.fetchone()[0] > 0:
                    s["tenants_paid"] += 1
                c.close()
            except Exception:
                pass
    # Queue stats
    try:
        import json as _json
        q = _json.loads(TASK_QUEUE.read_text(encoding="utf-8"))
        s["queue_pending"] = len(q.get("pending", []))
        cutoff_iso = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        done30 = [d for d in q.get("done", [])
                  if d.get("completed_at", "") > cutoff_iso]
        failed30 = [f for f in q.get("failed", [])
                    if f.get("failed_at", "") > cutoff_iso]
        s["queue_done_30min"] = len(done30)
        s["queue_failed_30min"] = len(failed30)
        # Breakdown por status del done
        s["done_sample"] = [d.get("result", {}).get("status", "?")
                            for d in done30[:5]]
    except Exception:
        s["done_sample"] = []
    # Daemons up (fix v2: extraer modulo via regex -m, no split por espacios
    # que rompia con paths con espacios)
    try:
        import subprocess
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -match 'jarvis_v2|jarvis_bridge' } | "
             "ForEach-Object { "
             "  if ($_.CommandLine -match '-m\\s+(\\S+)') { $matches[1] } "
             "  else { 'unknown_python_proc' } "
             "}"],
            timeout=10, text=True)
        s["daemons_up"] = [line.strip() for line in out.splitlines() if line.strip()]
        # Tambien cuenta cloudflared + localtunnel via node
        try:
            out2 = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "@(Get-Process cloudflared, node -ErrorAction SilentlyContinue) | "
                 "Where-Object { $_ } | ForEach-Object { $_.Name }"],
                timeout=5, text=True)
            for line in out2.splitlines():
                if line.strip():
                    s["daemons_up"].append(line.strip())
        except Exception:
            pass
    except Exception:
        pass
    return s


def gather_recent_actions(state: dict) -> list[str]:
    """Lista corta de las 5 acciones mas relevantes de los ultimos 30 min."""
    out = []
    if state["queue_done_30min"]:
        out.append(f"✓ {state['queue_done_30min']} tareas completadas")
    if state["queue_failed_30min"]:
        out.append(f"✗ {state['queue_failed_30min']} tareas fallidas")
    if state["done_sample"]:
        types = {}
        for st in state["done_sample"]:
            types[st] = types.get(st, 0) + 1
        for t, n in types.items():
            out.append(f"  - {n}x status={t}")
    if not out:
        out.append("Sin actividad en ventana 30 min (sistema idle)")
    return out


def gather_alerts(state: dict) -> list[str]:
    alerts = []
    if state["queue_failed_30min"] >= 3:
        alerts.append(f"WARN: {state['queue_failed_30min']} tasks fallidas en 30 min")
    if state["leads_total"] > 0 and state["leads_sent"] == 0:
        alerts.append(f"INFO: {state['leads_total']} leads en CRM, 0 enviados aun")
    if not state["daemons_up"] or len(state["daemons_up"]) < 2:
        alerts.append("CRITICAL: <2 daemons activos. Watchdog deberia reanimarlos.")
    if state["revenue_30d_usd"] == 0 and state["tenants_total"] > 1:
        alerts.append(f"INFO: {state['tenants_total']} tenants, 0 USD revenue aun")
    return alerts


def next_step_recommendation(state: dict) -> str:
    if state["tenants_paid"] > 0:
        return "Verificar dashboard y replicar lo que funciono"
    if state["leads_total"] > 0 and state["leads_sent"] == 0:
        return "Pre-requisitos outreach: SMTP creds + URL profesional + emails reales"
    if state["tenants_total"] == 0:
        return "Difundir URL publica (Show HN o LinkedIn) para primeros signups"
    return "Sistema operando 24/7, revisar bitacora full en data/reports/"


def build_pdf(state: dict, actions: list[str], alerts: list[str],
              next_step: str, out_path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=letter)
    w, h = letter
    margin = 50
    y = h - margin

    # HEADER
    c.setFillColor(HexColor("#0A0A0A"))
    c.rect(0, h - 70, w, 70, fill=1, stroke=0)
    c.setFillColor(HexColor("#10b981"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, h - 40, "Jarvis V2")
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica", 10)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.drawString(margin + 110, h - 38, f"reporte {ts}")
    public_url = ""
    if URL_FILE.exists():
        public_url = URL_FILE.read_text(encoding="utf-8").strip()
    if public_url:
        c.setFont("Helvetica", 9)
        c.drawRightString(w - margin, h - 38, public_url)
    y = h - 100

    # ESTADO
    c.setFillColor(HexColor("#0A0A0A"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y, "Estado del negocio")
    y -= 18
    c.setFont("Helvetica", 10)
    kpis = [
        ("Leads CRM", f"{state['leads_total']} (enviados {state['leads_sent']}, respondidos {state['leads_replied']})"),
        ("Tenants", f"{state['tenants_total']} ({state['tenants_paid']} pagados)"),
        ("Revenue 30d", f"${state['revenue_30d_usd']:.2f} USD"),
        ("Queue pending", str(state["queue_pending"])),
        ("Daemons activos", str(len(state["daemons_up"]))),
    ]
    for k, v in kpis:
        c.setFillColor(HexColor("#71717a"))
        c.drawString(margin + 5, y, f"{k}:")
        c.setFillColor(HexColor("#0A0A0A"))
        c.drawString(margin + 130, y, v)
        y -= 15

    # ULTIMOS 30 MIN
    y -= 10
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y, "Ultimos 30 minutos")
    y -= 18
    c.setFont("Helvetica", 10)
    for line in actions[:8]:
        c.drawString(margin + 5, y, line[:90])
        y -= 14

    # ALERTAS
    if alerts:
        y -= 10
        c.setFillColor(HexColor("#dc2626"))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, y, "Alertas")
        y -= 18
        c.setFont("Helvetica", 10)
        for a in alerts[:5]:
            c.drawString(margin + 5, y, a[:90])
            y -= 14

    # NEXT STEP
    y -= 15
    c.setFillColor(HexColor("#10b981"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y, "Proximo paso")
    y -= 18
    c.setFillColor(HexColor("#0A0A0A"))
    c.setFont("Helvetica", 10)
    # Wrap simple
    words = next_step.split()
    line_buf = ""
    for word in words:
        if len(line_buf + " " + word) > 75:
            c.drawString(margin + 5, y, line_buf.strip())
            y -= 14
            line_buf = word
        else:
            line_buf += " " + word
    if line_buf.strip():
        c.drawString(margin + 5, y, line_buf.strip())
        y -= 14

    # FOOTER
    c.setFillColor(HexColor("#a1a1aa"))
    c.setFont("Helvetica", 8)
    c.drawString(margin, 30, f"Auto-generado por pdf_reporter.py cada 30 min")
    c.drawRightString(w - margin, 30, f"jarvis_v2 / multi-tenant agentic")
    c.save()


def main() -> Path:
    _ensure_reportlab()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    state = gather_business_state()
    actions = gather_recent_actions(state)
    alerts = gather_alerts(state)
    next_step = next_step_recommendation(state)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = REPORTS_DIR / f"jarvis_{ts}.pdf"
    build_pdf(state, actions, alerts, next_step, out)
    print(f"OK report: {out}")
    print(f"  state: leads={state['leads_total']} "
          f"tenants={state['tenants_total']} "
          f"done30={state['queue_done_30min']} "
          f"failed30={state['queue_failed_30min']}")
    return out


if __name__ == "__main__":
    main()
