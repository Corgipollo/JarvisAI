"""cerebro_rag.py - Indexa y consulta el vault CerebroEmmanuel via ChromaDB.

Embeddings local con sentence-transformers/all-MiniLM-L6-v2 (CPU, 100MB).
ChromaDB persistente en data/chroma_cerebro/.

Tools expuestas:
  - index_vault(vault_path) -> indexa Markdown del vault
  - search_cerebro(query, top_k=5) -> retrieves relevant chunks como texto
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "chroma_cerebro"
COLLECTION_NAME = "cerebro_emmanuel"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_client = None
_collection = None
_embedder = None


def _get_collection():
    global _client, _collection, _embedder
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.config import Settings
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _client = chromadb.PersistentClient(path=str(CHROMA_DIR),
                                         settings=Settings(anonymized_telemetry=False))
    try:
        _collection = _client.get_collection(COLLECTION_NAME)
    except Exception:
        _collection = _client.create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    return _collection


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _chunk_markdown(text: str, max_chars: int = 1500) -> list[str]:
    """Chunk por headers H1/H2/H3, con tamano max."""
    sections = re.split(r"\n(?=#{1,3}\s)", text)
    chunks = []
    for s in sections:
        s = s.strip()
        if not s:
            continue
        if len(s) <= max_chars:
            chunks.append(s)
        else:
            # Sub-split by paragraphs
            paras = s.split("\n\n")
            cur = ""
            for p in paras:
                if len(cur) + len(p) + 2 > max_chars:
                    if cur:
                        chunks.append(cur)
                    cur = p
                else:
                    cur = (cur + "\n\n" + p) if cur else p
            if cur:
                chunks.append(cur)
    return chunks


def index_vault(vault_path: str, file_pattern: str = "**/*.md",
                max_files: int | None = None) -> dict:
    """Indexa todos los .md del vault. Idempotente (skip si id ya existe)."""
    col = _get_collection()
    embedder = _get_embedder()
    vault = Path(vault_path)
    files = list(vault.glob(file_pattern))
    if max_files:
        files = files[:max_files]
    print(f"[cerebro_rag] indexando {len(files)} files de {vault}", flush=True)

    added = 0
    skipped = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not text.strip():
            continue
        chunks = _chunk_markdown(text)
        rel = str(f.relative_to(vault)).replace("\\", "/")
        ids = [f"{rel}#chunk{i}" for i in range(len(chunks))]
        # Skip existing
        try:
            existing = col.get(ids=ids, include=[])
            ex_ids = set(existing.get("ids") or [])
        except Exception:
            ex_ids = set()
        new_ids, new_chunks, new_metas = [], [], []
        for cid, chunk in zip(ids, chunks):
            if cid in ex_ids:
                skipped += 1
                continue
            new_ids.append(cid)
            new_chunks.append(chunk)
            new_metas.append({"file": rel, "chunk_chars": len(chunk)})
        if new_ids:
            embeddings = embedder.encode(new_chunks, show_progress_bar=False).tolist()
            col.add(ids=new_ids, documents=new_chunks, embeddings=embeddings,
                    metadatas=new_metas)
            added += len(new_ids)
        if (added + skipped) % 100 == 0:
            print(f"  progreso: +{added} skip={skipped}", flush=True)
    print(f"[cerebro_rag] DONE +{added} chunks (skip {skipped})", flush=True)
    return {"added": added, "skipped": skipped, "total_files": len(files)}


def search_cerebro(query: str, top_k: int = 5) -> str:
    """Query semantica al vault. Retorna texto concatenado de chunks relevantes."""
    col = _get_collection()
    embedder = _get_embedder()
    qe = embedder.encode([query], show_progress_bar=False).tolist()
    res = col.query(query_embeddings=qe, n_results=top_k,
                    include=["documents", "metadatas", "distances"])
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    parts = []
    for doc, meta, dist in zip(docs, metas, dists):
        score = 1 - dist if isinstance(dist, (int, float)) else 0
        file = meta.get("file", "?")
        parts.append(f"--- {file} (sim {score:.2f}) ---\n{doc}")
    return "\n\n".join(parts) if parts else "(no relevant chunks)"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "index":
        vault = sys.argv[2] if len(sys.argv) > 2 else "C:/Users/Emmanuel/Documents/CerebroEmmanuel"
        stats = index_vault(vault)
        print(stats)
    else:
        q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Bot Forex V8 spike catcher"
        result = search_cerebro(q, top_k=3)
        print(result[:3000])
