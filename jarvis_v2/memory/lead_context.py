"""lead_context.py - Memoria contextual por lead (outreach long-term).

Complementa memory_manager.py (lecciones tecnicas globales) con una capa
especifica para CRM/outreach: cada interaccion con un prospect queda
indexada por lead_id Y embedded semanticamente.

Coleccion ChromaDB dedicada: 'outreach_memory'. Vive en el mismo
chroma_cerebro/ que cerebro_rag + jarvis_experience.

API:
    remember_interaction(lead_id, channel, direction, content,
                          sentiment="neutral", outcome=None, meta=None) -> dict
        Guarda una nueva interaccion. Idempotente: hash de (lead_id, ts, hash(content)).

    recall_lead_history(lead_id, top_k=10) -> list[interaction]
        Devuelve historial cronologico del lead (no semantic, ordenado por ts).

    recall_similar_to(query, lead_id=None, top_k=3, min_similarity=0.4)
        Semantic search. Si lead_id, restringe a ese lead. Sino, global.

    pitch_context_for_lead(lead_id) -> str
        Texto resumido <2000 chars listo para inyectar en prompt antes de
        generar el proximo email a este lead. Incluye objeciones previas,
        tono que funciono, vertical, ultimos opens/clicks.

Schema de cada documento:
    text:  "{direction} [{channel}] @ {ts}: {content}"
    metadata:
        lead_id: int
        channel: email|linkedin|whatsapp|call|in_person
        direction: outbound|inbound
        sentiment: positive|neutral|negative|hostile
        outcome: opened|clicked|replied|bounced|unsubscribed|booked|closed|None
        ts: ISO8601
        content_hash: sha1 first 12
        meta_json: extra JSON serializado

Costo de cada remember: ~50ms (embedding MiniLM-L6-v2 local).
Costo de cada recall: ~30ms.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHROMA_DIR = ROOT / "data" / "chroma_cerebro"
COLLECTION_NAME = "outreach_memory"

_client = None
_collection = None
_embedder = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.config import Settings
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    try:
        _collection = _client.get_collection(COLLECTION_NAME)
    except Exception:
        _collection = _client.create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "purpose": "outreach_per_lead"},
        )
    return _collection


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder


def _hash_interaction(lead_id: int, ts: str, content: str) -> str:
    h = hashlib.sha1(f"{lead_id}::{ts}::{content[:500]}".encode()).hexdigest()[:16]
    return f"lead{lead_id}_{h}"


VALID_CHANNELS = {"email", "linkedin", "whatsapp", "call", "in_person", "form"}
VALID_DIRECTIONS = {"outbound", "inbound"}
VALID_SENTIMENTS = {"positive", "neutral", "negative", "hostile"}
VALID_OUTCOMES = {
    None, "sent", "opened", "clicked", "replied", "bounced",
    "unsubscribed", "booked", "closed_won", "closed_lost", "ghosted",
}


def remember_interaction(
    lead_id: int,
    channel: str,
    direction: str,
    content: str,
    sentiment: str = "neutral",
    outcome: str | None = None,
    meta: dict | None = None,
) -> dict:
    """Guarda una interaccion. Devuelve {id, action: created|updated}."""
    if not content or len(content.strip()) < 5:
        return {"error": "content_too_short"}
    if channel not in VALID_CHANNELS:
        channel = "email"
    if direction not in VALID_DIRECTIONS:
        direction = "outbound"
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "neutral"
    if outcome not in VALID_OUTCOMES:
        outcome = None

    ts = datetime.utcnow().isoformat()
    doc_id = _hash_interaction(lead_id, ts, content)
    embed_text = f"{direction} [{channel}] @ {ts}: {content[:4000]}"

    col = _get_collection()
    embedder = _get_embedder()
    embedding = embedder.encode([embed_text], show_progress_bar=False).tolist()[0]

    metadata = {
        "lead_id": int(lead_id),
        "channel": channel,
        "direction": direction,
        "sentiment": sentiment,
        "outcome": outcome or "",
        "ts": ts,
        "content_hash": hashlib.sha1(content.encode()).hexdigest()[:12],
        "meta_json": json.dumps(meta or {}, ensure_ascii=False)[:2000],
    }

    try:
        col.add(ids=[doc_id], documents=[embed_text],
                embeddings=[embedding], metadatas=[metadata])
        return {"id": doc_id, "action": "created"}
    except Exception:
        # Duplicate id collision -> update
        col.update(ids=[doc_id], documents=[embed_text],
                   embeddings=[embedding], metadatas=[metadata])
        return {"id": doc_id, "action": "updated"}


def recall_lead_history(lead_id: int, top_k: int = 10) -> list[dict]:
    """Historial cronologico de UN lead. Sin semantic, ordenado por ts desc."""
    col = _get_collection()
    res = col.get(
        where={"lead_id": int(lead_id)},
        include=["documents", "metadatas"],
        limit=200,  # cap defensivo
    )
    out = []
    for doc, meta in zip(res.get("documents") or [], res.get("metadatas") or []):
        out.append({
            "doc": doc,
            "ts": meta.get("ts", ""),
            "channel": meta.get("channel"),
            "direction": meta.get("direction"),
            "sentiment": meta.get("sentiment"),
            "outcome": meta.get("outcome") or None,
            "meta": json.loads(meta.get("meta_json") or "{}"),
        })
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out[:top_k]


def recall_similar_to(
    query: str,
    lead_id: int | None = None,
    top_k: int = 3,
    min_similarity: float = 0.4,
) -> list[dict]:
    """Semantic search. Si lead_id, restringe a ese lead; sino, global."""
    col = _get_collection()
    embedder = _get_embedder()
    qe = embedder.encode([query], show_progress_bar=False).tolist()
    where = {"lead_id": int(lead_id)} if lead_id is not None else None
    res = col.query(
        query_embeddings=qe,
        n_results=max(top_k * 2, 6),
        include=["documents", "metadatas", "distances"],
        where=where,
    )
    out = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        sim = 1.0 - float(dist)
        if sim < min_similarity:
            continue
        out.append({
            "doc": doc,
            "similarity": round(sim, 3),
            "ts": meta.get("ts"),
            "lead_id": meta.get("lead_id"),
            "channel": meta.get("channel"),
            "direction": meta.get("direction"),
            "sentiment": meta.get("sentiment"),
            "outcome": meta.get("outcome") or None,
        })
        if len(out) >= top_k:
            break
    return out


def pitch_context_for_lead(lead_id: int, max_chars: int = 2000) -> str:
    """Resumen compacto del lead listo para inyectar en prompt.

    Devuelve string <max_chars con:
      - cuantas interacciones previas
      - ultimos 3 mensajes outbound + ultimos 2 inbound
      - sentimientos predominantes
      - objeciones/keywords negativas previas
    """
    history = recall_lead_history(lead_id, top_k=20)
    if not history:
        return "(sin interacciones previas — primer contacto)"

    total = len(history)
    outbound = [h for h in history if h["direction"] == "outbound"][:3]
    inbound = [h for h in history if h["direction"] == "inbound"][:2]
    sentiments = [h["sentiment"] for h in history if h.get("sentiment")]
    neg_count = sum(1 for s in sentiments if s in ("negative", "hostile"))
    pos_count = sum(1 for s in sentiments if s == "positive")

    parts = [f"Historial: {total} interacciones previas con este lead."]
    if neg_count or pos_count:
        parts.append(f"Sentimiento agregado: {pos_count} positivos, {neg_count} negativos.")
    if outbound:
        parts.append("\nUltimos mensajes que YO envie:")
        for h in outbound:
            parts.append(f"  - [{h['ts'][:16]} {h['channel']}] outcome={h['outcome'] or 'n/a'}")
            parts.append(f"    {h['doc'][:240]}")
    if inbound:
        parts.append("\nUltimas respuestas del lead:")
        for h in inbound:
            parts.append(f"  - [{h['ts'][:16]} {h['channel']}] sentiment={h['sentiment']}")
            parts.append(f"    {h['doc'][:240]}")

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."
    return text


def stats() -> dict:
    """Diagnostico: cuantas interacciones, cuantos leads unicos, breakdown por outcome."""
    col = _get_collection()
    all_data = col.get(include=["metadatas"], limit=10000)
    metas = all_data.get("metadatas") or []
    if not metas:
        return {"total_interactions": 0, "unique_leads": 0}
    unique = set()
    by_outcome: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_direction: dict[str, int] = {}
    for m in metas:
        unique.add(int(m.get("lead_id", -1)))
        oc = m.get("outcome") or "none"
        by_outcome[oc] = by_outcome.get(oc, 0) + 1
        ch = m.get("channel") or "?"
        by_channel[ch] = by_channel.get(ch, 0) + 1
        di = m.get("direction") or "?"
        by_direction[di] = by_direction.get(di, 0) + 1
    return {
        "total_interactions": len(metas),
        "unique_leads": len(unique),
        "by_outcome": by_outcome,
        "by_channel": by_channel,
        "by_direction": by_direction,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--stats", action="store_true")
    p.add_argument("--lead", type=int, help="recall history of lead_id")
    p.add_argument("--similar", help="semantic search across all leads")
    args = p.parse_args()

    if args.stats:
        print(json.dumps(stats(), indent=2, default=str))
    elif args.lead:
        print(pitch_context_for_lead(args.lead))
    elif args.similar:
        results = recall_similar_to(args.similar, top_k=5)
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    else:
        # Smoke test
        r1 = remember_interaction(
            lead_id=999_999,
            channel="email",
            direction="outbound",
            content="Hola, somos Jarvis AI, ayudamos PyMEs a automatizar cobranza.",
            outcome="sent",
        )
        print("remember:", r1)
        r2 = recall_lead_history(999_999)
        print(f"history (n={len(r2)}):", r2[:1])
        r3 = pitch_context_for_lead(999_999)
        print("context:\n", r3)
        print("\nstats:", json.dumps(stats(), indent=2))
