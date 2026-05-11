"""semantic_memory.py — Memoria semántica con embeddings + búsqueda por similitud.

Backend: sentence-transformers (gratis, local) + FAISS para búsqueda rápida.
NO usa OpenAI ni Pinecone (todo local).

Indexa:
  - Skills aprendidas (skill_library/*.json)
  - Roles aprendidos (role_library/*.json)
  - Tareas completadas (jarvis_learnings.jsonl)

Permite buscar:
  - "que sabes de edicion de video"
  - "que has aprendido sobre Excel"
  - "alguna skill relacionada a redes sociales"

API:
    from jarvis_bridge.semantic_memory import index_all, search
    index_all()  # reindexa todo (idempotente)
    results = search("editar video tiktok", top_k=5)
    # [{"text": "skill X", "score": 0.87, "source": "skill_library/..."}]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INDEX_DIR = DATA_DIR / "semantic_index"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # bilingüe ES/EN

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _load_model():
    """Carga el modelo (lazy, primera vez ~80 MB descarga)."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(MODEL_NAME)
    except ImportError:
        print("[semantic_memory] falta: pip install sentence-transformers faiss-cpu")
        return None


def _gather_documents() -> list[dict]:
    """Recolecta TODO lo indexable en formato {id, text, source}."""
    docs = []

    # Skills
    skill_idx = DATA_DIR / "skill_library" / "_index.jsonl"
    if skill_idx.exists():
        for line in skill_idx.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                full_path = DATA_DIR / "skill_library" / entry["file"]
                if full_path.exists():
                    skill_data = json.loads(full_path.read_text(encoding="utf-8"))
                    text_parts = [
                        f"SKILL: {skill_data.get('name','')}",
                        f"domain: {skill_data.get('domain','')}",
                        "steps: " + "; ".join(
                            s.get("action", "") for s in skill_data.get("steps", [])
                        ),
                        f"notes: {skill_data.get('notes','')}",
                    ]
                    docs.append({
                        "id": f"skill:{entry['id']}",
                        "text": " | ".join(text_parts)[:1000],
                        "source": str(full_path),
                        "type": "skill",
                        "name": skill_data.get("name", ""),
                    })
            except Exception:
                continue

    # Roles
    role_idx = DATA_DIR / "role_library" / "_index.jsonl"
    if role_idx.exists():
        for line in role_idx.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                full_path = DATA_DIR / "role_library" / entry["file"]
                if full_path.exists():
                    role_data = json.loads(full_path.read_text(encoding="utf-8"))
                    text_parts = [
                        f"ROL: {role_data.get('role','')}",
                        f"summary: {role_data.get('summary','')}",
                        "tools: " + ", ".join(t.get("name", "") for t in role_data.get("tools", [])),
                        "tasks: " + "; ".join(t.get("task", "") for t in role_data.get("daily_tasks", [])),
                    ]
                    docs.append({
                        "id": f"role:{entry['id']}",
                        "text": " | ".join(text_parts)[:1000],
                        "source": str(full_path),
                        "type": "role",
                        "name": role_data.get("role", ""),
                    })
            except Exception:
                continue

    return docs


def index_all() -> dict:
    """Reindexa TODO. Idempotente. Devuelve stats."""
    try:
        import numpy as np
        import faiss
    except ImportError:
        return {"error": "pip install faiss-cpu numpy sentence-transformers"}

    model = _load_model()
    if model is None:
        return {"error": "modelo no disponible"}

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    docs = _gather_documents()
    if not docs:
        return {"docs": 0, "indexed": 0}

    print(f"[semantic_memory] indexando {len(docs)} documentos...", flush=True)
    texts = [d["text"] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

    # FAISS L2 index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings.astype("float32"))

    # Save
    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
    (INDEX_DIR / "docs.jsonl").write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in docs),
        encoding="utf-8",
    )
    print(f"[semantic_memory] OK {len(docs)} docs indexados en {INDEX_DIR}", flush=True)
    return {"docs": len(docs), "indexed": len(docs), "dim": int(dim)}


def search(query: str, top_k: int = 5) -> list[dict]:
    """Búsqueda semántica."""
    try:
        import numpy as np
        import faiss
    except ImportError:
        return [{"error": "faiss no instalado"}]

    if not (INDEX_DIR / "faiss.index").exists():
        return [{"error": "indice no existe, ejecuta index_all() primero"}]

    model = _load_model()
    if model is None:
        return [{"error": "modelo no disponible"}]

    index = faiss.read_index(str(INDEX_DIR / "faiss.index"))
    docs = [json.loads(l) for l in (INDEX_DIR / "docs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(q_emb, min(top_k, len(docs)))

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(docs):
            continue
        d = docs[idx]
        results.append({
            "id": d["id"],
            "name": d.get("name", ""),
            "type": d["type"],
            "text": d["text"][:200],
            "source": d["source"],
            "score": round(1.0 / (1.0 + float(dist)), 3),  # convert L2 dist a similarity
        })
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usos:")
        print("  python semantic_memory.py index")
        print("  python semantic_memory.py search 'editar video'")
        sys.exit(0)

    if sys.argv[1] == "index":
        print(json.dumps(index_all(), indent=2, ensure_ascii=False))
    elif sys.argv[1] == "search":
        q = " ".join(sys.argv[2:])
        for r in search(q, top_k=5):
            print(f"[{r.get('score','?')}] {r.get('type','?')}: {r.get('name','?')}")
            print(f"  {r.get('text','')[:160]}")
            print()
