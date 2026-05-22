"""report_daemon.py - Reporte horario en PDF de todo lo que hizo Jarvis.

Cada hora:
  1. Lee task_queue done (ultima hora)
  2. Lee logs (api, worker, heartbeat, governor)
  3. Cuenta archivos creados en data/reports/, data/ideas/
  4. Genera PDF con reportlab
  5. Manda PDF via telegram_notify.notify_file()
  6. Lo guarda en data/reports/hourly/

Dependencia: reportlab (auto-install).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPORTS_DIR = ROOT / "data" / "reports" / "hourly"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_INTERVAL_SEC = int(os.environ.get("REPORT_INTERVAL_SEC", "3600"))


def _ensure_reportlab():
    try:
        import reportlab  # noqa
    except ImportError:
        print("[report] installing reportlab...", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                         "reportlab"], check=False)


def _gather_stats(window_hours: float = 1.0) -> dict:
    """Junta datos del ultimo intervalo."""
    from jarvis_v2 import task_queue as Q
    q_state = Q._read()
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    done_recent = []
    for d in q_state.get("done", []):
        try:
            ts = datetime.fromisoformat(d.get("completed_at", "").replace("Z", ""))
            if ts >= cutoff:
                done_recent.append(d)
        except Exception:
            pass

    failed_recent = []
    for f in q_state.get("failed", []):
        try:
            ts = datetime.fromisoformat(f.get("failed_at", "").replace("Z", ""))
            if ts >= cutoff:
                failed_recent.append(f)
        except Exception:
            pass

    # Files generated recently in data/reports + data/ideas
    new_files = []
    for sub in ("reports", "ideas"):
        d = ROOT / "data" / sub
        if d.exists():
            for f in d.rglob("*"):
                if not f.is_file() or "hourly" in str(f):
                    continue
                try:
                    mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
                    if mtime >= cutoff:
                        new_files.append({
                            "path": str(f.relative_to(ROOT)),
                            "size": f.stat().st_size,
                            "mtime": mtime.isoformat(),
                        })
                except Exception:
                    pass

    return {
        "window_hours": window_hours,
        "generated_at": datetime.utcnow().isoformat(),
        "done_count": len(done_recent),
        "failed_count": len(failed_recent),
        "pending_now": len(q_state.get("pending", [])),
        "done_recent": done_recent[-15:],
        "failed_recent": failed_recent[-10:],
        "new_files": new_files[:20],
    }


def _render_pdf(stats: dict, out_path: Path):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                      Table, TableStyle)

    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                              leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                              topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]; h1.textColor = HexColor("#0A0A0A")
    h2 = styles["Heading2"]; h2.textColor = HexColor("#444")
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10,
                            textColor=HexColor("#555"))

    story = []
    ts = stats["generated_at"]
    story.append(Paragraph(f"Jarvis V2 — Reporte horario", h1))
    story.append(Paragraph(f"Generado: {ts}", small))
    story.append(Spacer(1, 0.2 * inch))

    # Summary table
    summary = [
        ["Metric", "Valor"],
        ["Ventana", f"{stats['window_hours']} h"],
        ["Tasks completadas", str(stats["done_count"])],
        ["Tasks fallidas", str(stats["failed_count"])],
        ["Pending ahora", str(stats["pending_now"])],
        ["Archivos nuevos", str(len(stats["new_files"]))],
    ]
    t = Table(summary, colWidths=[2.5 * inch, 2.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#C5A882")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#0A0A0A")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#999")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    # Done recientes
    story.append(Paragraph("Tareas completadas (sample)", h2))
    if stats["done_recent"]:
        for d in stats["done_recent"]:
            line = (f"<b>{d.get('qid','?')[:8]}</b> — "
                    f"task_id <i>{(d.get('task_id') or 'na')[:10]}</i> — "
                    f"{d.get('completed_at','')[:19]}")
            story.append(Paragraph(line, small))
    else:
        story.append(Paragraph("Sin tareas en esta ventana.", body))

    story.append(Spacer(1, 0.2 * inch))

    # Failed
    story.append(Paragraph("Tareas con error", h2))
    if stats["failed_recent"]:
        for f in stats["failed_recent"]:
            err = (f.get("error") or "")[:200].replace("<", "&lt;")
            line = f"<b>{f.get('qid','?')[:8]}</b>: {err}"
            story.append(Paragraph(line, small))
    else:
        story.append(Paragraph("Sin fallos.", body))

    story.append(Spacer(1, 0.2 * inch))

    # Archivos nuevos
    story.append(Paragraph("Archivos creados", h2))
    if stats["new_files"]:
        for f in stats["new_files"]:
            line = (f"<b>{f['path']}</b> — {f['size']} bytes — "
                    f"{f['mtime'][:19]}")
            story.append(Paragraph(line, small))
    else:
        story.append(Paragraph("Sin archivos nuevos.", body))

    doc.build(story)


def run_one_report() -> dict:
    """Genera un PDF + lo manda por Telegram. Devuelve dict con path + ok."""
    _ensure_reportlab()
    stats = _gather_stats(window_hours=1.0)
    ts_tag = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pdf_path = REPORTS_DIR / f"jarvis_report_{ts_tag}.pdf"
    try:
        _render_pdf(stats, pdf_path)
    except Exception as e:
        return {"ok": False, "error": f"render_fail: {e}"}

    sent = False
    try:
        from jarvis_v2.bridges.telegram_notify import notify_file, configured
        if configured():
            caption = (f"Jarvis report {ts_tag}: "
                       f"{stats['done_count']} done, "
                       f"{stats['failed_count']} fail, "
                       f"{stats['pending_now']} pending, "
                       f"{len(stats['new_files'])} archivos.")
            sent = notify_file(caption, pdf_path)
    except Exception as e:
        print(f"[report] tg notify fail: {e}", file=sys.stderr)

    return {"ok": True, "pdf": str(pdf_path), "telegram_sent": sent,
            "stats": stats}


def main_loop():
    print(f"[report_daemon] arranca, interval={REPORT_INTERVAL_SEC}s "
          f"({REPORT_INTERVAL_SEC/60:.0f} min)", flush=True)
    while True:
        try:
            r = run_one_report()
            print(f"[report_daemon] {r.get('pdf')} tg_sent={r.get('telegram_sent')}",
                  flush=True)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[report_daemon] loop error: {e}", file=sys.stderr)
        time.sleep(REPORT_INTERVAL_SEC)


if __name__ == "__main__":
    if "--once" in sys.argv:
        r = run_one_report()
        print(json.dumps(r, ensure_ascii=False, default=str, indent=2)[:1500])
    else:
        main_loop()
