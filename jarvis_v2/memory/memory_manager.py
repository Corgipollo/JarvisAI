"""memory_manager.py - Memoria episodica de Jarvis (lecciones aprendidas).

Equivalente a Mem0 pero reusa ChromaDB ya instalado. Coleccion separada
'jarvis_experience' para no contaminar el RAG del vault.

Cada leccion tiene:
  - id (hash determinista de insight+tags)
  - tags: list[str] (action_type, error_class, domain, etc.)
  - insight: texto natural ("Al hacer X falla Y porque Z, fix: W")
  - context: situacion donde se aprendio
  - severity: critical|high|medium|low
  - hit_count: cuantas veces se recordo y aplico
  - last_hit_at: ultima vez recordada
  - confidence: 0-1 (decay con tiempo si no se hit)
  - created_at

API:
  save_lesson(insight, tags, context="", severity="medium") -> id
  recall_lessons(query, top_k=3, tag_filter=None) -> list[lesson]
  mark_lesson_helpful(lesson_id) -> incrementa hit_count
  decay_old_lessons() -> reduce confidence de lecciones viejas no-hit
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "chroma_cerebro"  # mismo dir que cerebro_rag
COLLECTION_NAME = "jarvis_experience"

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
            metadata={"hnsw:space": "cosine", "purpose": "jarvis_lessons"},
        )
    return _collection


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder


def _hash_lesson(insight: str, tags: list[str]) -> str:
    payload = f"{insight}::{'|'.join(sorted(tags))}"
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def save_lesson(
    insight: str,
    tags: list[str],
    context: str = "",
    severity: str = "medium",
) -> dict:
    """Guarda una leccion. Idempotente (mismo insight+tags = update no duplicate).

    Returns:
        {"id": hash, "action": "created|updated", "embed_chars": n}
    """
    if not insight or len(insight.strip()) < 5:
        return {"error": "insight_too_short"}
    if severity not in ("critical", "high", "medium", "low"):
        severity = "medium"

    col = _get_collection()
    embedder = _get_embedder()

    lesson_id = _hash_lesson(insight, tags)
    embed_text = f"{insight}\nCONTEXT: {context}\nTAGS: {' '.join(tags)}"
    embedding = embedder.encode([embed_text], show_progress_bar=False).tolist()[0]

    metadata = {
        "tags": "|".join(tags),  # ChromaDB no soporta lists nativos en metadata
        "context": context[:500],
        "severity": severity,
        "created_at": datetime.utcnow().isoformat(),
        "hit_count": 0,
        "last_hit_at": "",
        "confidence": 1.0,
    }

    # Idempotency: si existe, update; sino, add
    try:
        existing = col.get(ids=[lesson_id], include=["metadatas"])
        if existing.get("ids"):
            # Update: preserve hit_count, refresh confidence
            old_meta = existing["metadatas"][0]
            metadata["hit_count"] = int(old_meta.get("hit_count", 0))
            metadata["last_hit_at"] = old_meta.get("last_hit_at", "")
            metadata["created_at"] = old_meta.get("created_at", metadata["created_at"])
            metadata["confidence"] = 1.0  # reset to fresh
            col.update(ids=[lesson_id], documents=[embed_text],
                       embeddings=[embedding], metadatas=[metadata])
            return {"id": lesson_id, "action": "updated", "embed_chars": len(embed_text)}
    except Exception:
        pass

    col.add(ids=[lesson_id], documents=[embed_text],
            embeddings=[embedding], metadatas=[metadata])
    return {"id": lesson_id, "action": "created", "embed_chars": len(embed_text)}


def recall_lessons(
    query: str,
    top_k: int = 3,
    tag_filter: list[str] | None = None,
    min_confidence: float = 0.3,
) -> list[dict]:
    """Recupera lecciones relevantes para el contexto actual.

    Args:
        query: texto de la situacion ("voy a hacer ffmpeg concat")
        top_k: maximo de lecciones
        tag_filter: si se pasa, solo lecciones con AL MENOS uno de estos tags
        min_confidence: filtra lecciones con confianza menor

    Returns:
        [{id, insight, tags, severity, confidence, hit_count}, ...]
    """
    col = _get_collection()
    embedder = _get_embedder()
    qe = embedder.encode([query], show_progress_bar=False).tolist()

    # Pedimos mas para filtrar despues
    n_request = max(top_k * 3, 10)
    res = col.query(
        query_embeddings=qe,
        n_results=n_request,
        include=["documents", "metadatas", "distances"],
    )

    out = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    ids = (res.get("ids") or [[]])[0]

    for doc, meta, dist, lid in zip(docs, metas, dists, ids):
        conf = float(meta.get("confidence", 1.0))
        if conf < min_confidence:
            continue
        tags = (meta.get("tags") or "").split("|")
        if tag_filter and not any(t in tags for t in tag_filter):
            continue
        # Extract just the insight (before CONTEXT)
        insight = doc.split("\nCONTEXT:")[0] if "\nCONTEXT:" in doc else doc
        out.append({
            "id": lid,
            "insight": insight,
            "tags": [t for t in tags if t],
            "severity": meta.get("severity", "medium"),
            "context": meta.get("context", ""),
            "confidence": conf,
            "hit_count": int(meta.get("hit_count", 0)),
            "similarity": 1 - float(dist),
            "created_at": meta.get("created_at", ""),
        })
        if len(out) >= top_k:
            break
    return out


def mark_lesson_helpful(lesson_id: str):
    """Cuando una leccion se inyecta al planner y se aplica, incrementar hit_count."""
    col = _get_collection()
    res = col.get(ids=[lesson_id], include=["metadatas", "documents", "embeddings"])
    if not res.get("ids"):
        return {"error": "not_found"}
    meta = dict(res["metadatas"][0])
    meta["hit_count"] = int(meta.get("hit_count", 0)) + 1
    meta["last_hit_at"] = datetime.utcnow().isoformat()
    meta["confidence"] = min(1.0, float(meta.get("confidence", 1.0)) + 0.1)
    col.update(
        ids=[lesson_id],
        documents=res["documents"],
        embeddings=res["embeddings"],
        metadatas=[meta],
    )
    return {"ok": True, "hit_count": meta["hit_count"]}


def decay_old_lessons(decay_factor: float = 0.95, age_days: int = 30):
    """Reduce confidence de lecciones viejas y poco usadas."""
    col = _get_collection()
    all_data = col.get(include=["metadatas", "documents", "embeddings"])
    if not all_data.get("ids"):
        return {"checked": 0, "decayed": 0}

    now = datetime.utcnow()
    decayed = 0
    for i, lid in enumerate(all_data["ids"]):
        meta = dict(all_data["metadatas"][i])
        try:
            created = datetime.fromisoformat(meta.get("created_at", "1970-01-01"))
            age = (now - created).days
        except Exception:
            age = 0
        last_hit = meta.get("last_hit_at", "")
        no_recent_hit = (not last_hit) or (
            datetime.fromisoformat(last_hit) < now.fromisoformat(
                meta.get("created_at", now.isoformat()))
        )
        if age > age_days and no_recent_hit:
            meta["confidence"] = float(meta.get("confidence", 1.0)) * decay_factor
            col.update(
                ids=[lid],
                documents=[all_data["documents"][i]],
                embeddings=[all_data["embeddings"][i]],
                metadatas=[meta],
            )
            decayed += 1
    return {"checked": len(all_data["ids"]), "decayed": decayed}


def stats() -> dict:
    """Cuenta total + breakdown por severity."""
    col = _get_collection()
    try:
        all_data = col.get(include=["metadatas"])
    except Exception:
        return {"total": 0}
    metas = all_data.get("metadatas", [])
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_hits = 0
    for m in metas:
        s = m.get("severity", "medium")
        sev_counts[s] = sev_counts.get(s, 0) + 1
        total_hits += int(m.get("hit_count", 0))
    return {
        "total": len(metas),
        "by_severity": sev_counts,
        "total_hits_lifetime": total_hits,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        # Test save
        r = save_lesson(
            "Al hacer ffmpeg concat, primero hay que normalizar codecs con -c:v libx264 sino concat falla con 'Non-monotonic DTS'",
            tags=["ffmpeg", "concat", "video"],
            context="Mientras intentaba juntar 3 mp4 con diferentes fps",
            severity="high",
        )
        print(json.dumps(r, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "recall":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "ffmpeg video editing"
        lessons = recall_lessons(q, top_k=3)
        for l in lessons:
            print(f"\n- [{l['severity']}] {l['insight'][:200]}")
            print(f"  tags={l['tags']} sim={l['similarity']:.2f} hits={l['hit_count']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(stats(), indent=2))
    else:
        print("Usage: memory_manager.py {save|recall <query>|stats}")
