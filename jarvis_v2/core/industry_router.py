"""industry_router.py - Enrutador dinamico de contextos (multi-vertical).

Permite vender el mismo core de Jarvis a N industrias sin tocar el codigo.
Cada vertical define:
  - system_prompt: voz/persona/vocabulario del experto del nicho
  - allowed_actions: subset del enum de schemas.py.PlanStep.action
  - relevant_skills: lista de skills/agents que pueden invocarse
  - kpi_vocabulary: terminos que el clasificador debe reconocer

API publica:
    classify(text, tenant_id=None) -> str (industry slug)
    mask(industry, tenant_id) -> dict {system_prompt, allowed_actions,
                                        relevant_skills, tenant_id, db_path}
    route(text, tenant_id) -> mask completa con classify ya aplicado

El router NO carga modelos pesados. Si las keywords son ambiguas, hace
1 call al brain Haiku con prompt minimo. Costo tipico: $0 (regex hit).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TENANTS_DIR = ROOT / "data" / "tenants"


# ============================================================================
# VERTICALES (industrias) - extensible: agregar entrada para vender nuevo nicho
# ============================================================================
INDUSTRIES: dict[str, dict[str, Any]] = {
    "ecommerce": {
        "keywords": ["shopify", "tienda", "producto", "carrito", "checkout",
                      "autods", "judge.me", "dropshipping", "buybox", "amazon",
                      "wallapop", "ebay", "ventas", "conversion", "abandono",
                      "stock", "inventario", "sku", "variante"],
        "system_prompt": (
            "Eres experto e-commerce. Stack dominante: Shopify, AutoDS, "
            "Judge.me reviews, Meta/Google Ads, Klaviyo email, Vitals. "
            "Vocabulario: GMV, AOV, CAC, LTV, ROAS, conversion rate, "
            "abandoned cart. Tu prioridad es flujo de caja directo: "
            "fix tracking primero, despues optimizar conversion, despues "
            "escalar ads. JAMAS sugieras refactorizar codigo si la tienda "
            "no esta tomando pedidos hoy."
        ),
        "allowed_actions": ["shell", "api", "file_write", "browser_interact",
                             "web_scrape", "marketing_campaign", "custom_skill"],
        "relevant_skills": ["shopify-expert", "ad-creative",
                             "revenue-operations", "grop-ecommerce"],
    },
    "agri_logistics": {
        "keywords": ["granos", "maiz", "trigo", "soja", "cosecha", "silo",
                      "tonelada", "flete", "transporte", "report cobranza",
                      "neurograin", "sap", "erp", "trazabilidad", "calidad",
                      "humedad", "kg", "remision", "factura granos", "campo"],
        "system_prompt": (
            "Eres consultor ERP de logistica agricola. Stack tipico: SAP, "
            "FastAPI custom, Excel con macros, hojas de calculo de toneladas "
            "y fletes. Vocabulario: humedad, impureza, merma, FOB, CIF, "
            "remision electronica, CFDI carta porte. Tu prioridad es la "
            "trazabilidad de lotes y la conciliacion contable. JAMAS uses "
            "ejemplos de Shopify ni terminos de e-commerce."
        ),
        "allowed_actions": ["shell", "api", "file_write", "custom_skill"],
        "relevant_skills": ["neurograin-sap", "fastapi-expert",
                             "docker-development", "pandas-pro"],
    },
    "marketing": {
        "keywords": ["ads", "facebook", "tiktok", "instagram", "google ads",
                      "campaign", "creative", "copy", "lead", "funnel",
                      "atribucion", "pixel", "utm", "audiencia", "lookalike",
                      "ugc", "ctr", "cpc", "cpm", "roas"],
        "system_prompt": (
            "Eres growth marketer senior. Stack: Meta Ads Manager, Google "
            "Ads, TikTok Ads, Klaviyo, Segment, GA4, GTM, Triple Whale. "
            "Vocabulario: CAC, payback period, AOV, frequency, fatigue, "
            "first-click vs last-click, holdout testing. Tu prioridad es "
            "ROI medible por canal con incrementality."
        ),
        "allowed_actions": ["shell", "api", "file_write", "browser_interact",
                             "web_scrape", "marketing_campaign", "custom_skill"],
        "relevant_skills": ["ad-creative", "campaign-analytics",
                             "growth-hacker", "meta-ads-skill"],
    },
    "dev": {
        "keywords": ["python", "react", "typescript", "next.js", "fastapi",
                      "docker", "kubernetes", "ci", "cd", "tests", "pytest",
                      "refactor", "deploy", "git", "pull request",
                      "build", "compile", "lint", "type check"],
        "system_prompt": (
            "Eres senior dev. Lenguajes principales: Python 3.11+, TypeScript, "
            "Go. Stack ops: Docker, GitHub Actions, Postgres. Cumples PEP-8, "
            "tipas estrictamente con mypy, escribes tests primero. JAMAS "
            "sugieras cambios de arquitectura sin entender el contexto "
            "actual del codigo via reading."
        ),
        "allowed_actions": ["shell", "api", "file_write", "custom_skill",
                             "browser_interact"],
        "relevant_skills": ["python-pro", "typescript-specialist",
                             "react-expert", "code-reviewer",
                             "debugging-wizard"],
    },
    "video_pipeline": {
        "keywords": ["manhwa", "manhua", "video", "render", "ffmpeg",
                      "tts", "voice clone", "edge tts", "f5-tts", "whisper",
                      "narracion", "panel", "ocr", "subtitulos", "remotion",
                      "youtube upload", "shorts"],
        "system_prompt": (
            "Eres editor de video especializado en pipelines automatizados. "
            "Stack: ffmpeg, Whisper, F5-TTS, Edge TTS, Remotion, Pillow para "
            "panels. Vocabulario: keyframe, gop, bitrate, loudnorm, sidechain "
            "ducking, NVENC, Ken Burns. Tu prioridad es throughput por hora "
            "de GPU y calidad consistente en exports 1080p."
        ),
        "allowed_actions": ["shell", "file_write", "custom_skill",
                             "ffmpeg_render", "remotion_render",
                             "youtube_upload"],
        "relevant_skills": ["manhwa-pipeline", "remotion-expert",
                             "python-pro"],
    },
    "trading": {
        "keywords": ["forex", "binance", "futures", "spot", "mt5",
                      "scalper", "swing", "indicator", "rsi", "ema",
                      "backtest", "drawdown", "winrate", "spread",
                      "leverage", "stop loss", "take profit", "candle",
                      "orderflow", "funding rate"],
        "system_prompt": (
            "Eres quant trader. Mercados: forex (MT5 + Tickmill), crypto "
            "(Binance Futures). Vocabulario: edge, expectancy, kelly, "
            "sortino, max DD, slippage real vs modelado, regime detection. "
            "JAMAS recomiendas trade real sin backtest >=1000 trades en "
            "varias regimes. Tu prioridad es supervivencia del capital "
            "primero, retorno despues."
        ),
        "allowed_actions": ["shell", "api", "file_write",
                             "binance_market_order", "binance_limit_order",
                             "custom_skill"],
        "relevant_skills": ["bot-forex-analyst", "python-pro",
                             "pandas-pro"],
    },
    "generic": {
        "keywords": [],  # catch-all
        "system_prompt": (
            "Eres Jarvis, asistente autonomo de Emmanuel. Trabajas en modo "
            "general sin verticalizacion. Identifica primero la industria "
            "del problema antes de proponer solucion."
        ),
        "allowed_actions": ["shell", "api", "file_write", "click_som",
                             "type", "hotkey", "wait", "custom_skill",
                             "browser_interact"],
        "relevant_skills": ["general-purpose"],
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def classify(text: str, fallback_to_llm: bool = True) -> str:
    """Clasifica texto a industria slug. Regex first, LLM fallback.

    Devuelve 'generic' si no hay match claro y fallback_to_llm=False.
    """
    if not text:
        return "generic"
    norm = _normalize(text)
    scores: dict[str, int] = {}
    for slug, conf in INDUSTRIES.items():
        if slug == "generic":
            continue
        hits = sum(1 for kw in conf["keywords"]
                    if re.search(rf"\b{re.escape(kw)}\b", norm))
        if hits:
            scores[slug] = hits

    if not scores:
        if not fallback_to_llm:
            return "generic"
        return _classify_via_llm(text)

    # Hit claro: el slug con mas matches gana
    top = max(scores.items(), key=lambda x: x[1])
    # Anti-ambiguedad: si top y segundo estan empatados, va a generic
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] == sorted_scores[1]:
        if fallback_to_llm:
            return _classify_via_llm(text)
        return "generic"
    return top[0]


def _classify_via_llm(text: str) -> str:
    """Fallback Haiku. 1 call, ~100 tokens."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
    except ImportError:
        return "generic"
    industries_list = [s for s in INDUSTRIES if s != "generic"]
    prompt = (
        f"Clasifica este texto en UNA industria de esta lista exacta: "
        f"{industries_list}. Si no aplica claramente ninguna, responde "
        f"'generic'.\n\nTEXTO: {text[:500]}\n\n"
        f'Responde JSON: {{"industry": "slug_exacto"}}'
    )
    r = ask_claude_json(
        prompt,
        system="Clasificador conciso. JSON puro.",
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
    )
    if not r:
        return "generic"
    pick = (r.get("industry") or "").strip().lower()
    return pick if pick in INDUSTRIES else "generic"


def mask(industry: str, tenant_id: str) -> dict[str, Any]:
    """Devuelve la mascara completa para correr el grafo con esta vertical.

    tenant_id define el aislamiento de memoria/tokens/logs.
    """
    if industry not in INDUSTRIES:
        industry = "generic"
    conf = INDUSTRIES[industry]
    tenant_dir = TENANTS_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return {
        "industry": industry,
        "tenant_id": tenant_id,
        "system_prompt": conf["system_prompt"],
        "allowed_actions": conf["allowed_actions"],
        "relevant_skills": conf["relevant_skills"],
        "tenant_db": str(tenant_dir / "memory.db"),
        "tenant_logs": str(tenant_dir / "logs"),
        "tenant_secrets": str(tenant_dir / "secrets.enc"),
    }


def route(text: str, tenant_id: str = "default") -> dict[str, Any]:
    """Pipeline completo: classify + mask. Punto de entrada para el graph."""
    industry = classify(text)
    return mask(industry, tenant_id)


def list_industries() -> list[dict]:
    """Resumen de verticales soportadas (para dashboards/sales)."""
    return [
        {
            "slug": slug,
            "keyword_count": len(conf["keywords"]),
            "action_count": len(conf["allowed_actions"]),
            "skill_count": len(conf["relevant_skills"]),
        }
        for slug, conf in INDUSTRIES.items()
    ]


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--text", help="Texto a clasificar")
    p.add_argument("--tenant", default="default")
    p.add_argument("--list", action="store_true",
                   help="Lista verticales soportadas")
    args = p.parse_args()

    if args.list:
        print(json.dumps(list_industries(), indent=2, ensure_ascii=False))
    elif args.text:
        result = route(args.text, args.tenant)
        # Trim system_prompt para output legible
        result["system_prompt_preview"] = result.pop("system_prompt")[:200] + "..."
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Smoke test
        cases = [
            ("Mi tienda de Shopify no esta cobrando, falta el token de Admin API", "ecommerce"),
            ("Necesito conciliar 3000 toneladas de maiz del silo norte", "agri_logistics"),
            ("Configurar Pixel de Meta y lanzar 3 creatives UGC", "marketing"),
            ("Refactorizar este FastAPI endpoint y agregar tests", "dev"),
            ("Renderizar cap 31 de manhwa con voz clonada F5", "video_pipeline"),
            ("Backtest del bot Forex en USDJPY con RSI", "trading"),
            ("Hola que tal", "generic"),
        ]
        ok = 0
        for text, expected in cases:
            got = classify(text, fallback_to_llm=False)
            status = "OK" if got == expected else "FAIL"
            if got == expected:
                ok += 1
            print(f"  [{status}] expected={expected:20s} got={got:20s} | {text[:60]}")
        print(f"\n{ok}/{len(cases)} pass")
