"""Integracion con Obsidian vault - lee y busca en el cerebro."""
import os
import re
from pathlib import Path
from typing import Optional
from config import settings


class ObsidianBrain:
    def __init__(self):
        self.vault_path = Path(settings.OBSIDIAN_VAULT)

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Busca en todas las notas del vault."""
        results = []
        query_lower = query.lower()
        keywords = query_lower.split()

        for md_file in self.vault_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                content_lower = content.lower()
                name_lower = md_file.stem.lower()

                # Score: matches in filename worth more
                score = sum(2 for kw in keywords if kw in name_lower)
                score += sum(1 for kw in keywords if kw in content_lower)

                if score > 0:
                    # Extract relevant snippet
                    snippet = self._extract_snippet(content, keywords)
                    results.append(
                        {
                            "file": str(md_file.relative_to(self.vault_path)),
                            "title": md_file.stem,
                            "score": score,
                            "snippet": snippet,
                        }
                    )
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def read_note(self, relative_path: str) -> Optional[str]:
        """Lee una nota completa."""
        full_path = self.vault_path / relative_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8", errors="ignore")
        return None

    def list_projects(self) -> list[str]:
        """Lista los proyectos activos."""
        projects_dir = self.vault_path / "01-Proyectos"
        if projects_dir.exists():
            return [d.name for d in projects_dir.iterdir() if d.is_dir()]
        return []

    def get_moc(self, project: str) -> Optional[str]:
        """Lee el MOC de un proyecto."""
        projects_dir = self.vault_path / "01-Proyectos"
        for d in projects_dir.iterdir():
            if d.is_dir() and project.lower() in d.name.lower():
                for f in d.iterdir():
                    if f.name.startswith("MOC"):
                        return f.read_text(encoding="utf-8", errors="ignore")
        return None

    def get_recent_notes(self, limit: int = 10) -> list[dict]:
        """Notas modificadas recientemente."""
        notes = []
        for md_file in self.vault_path.rglob("*.md"):
            try:
                stat = md_file.stat()
                notes.append(
                    {
                        "file": str(md_file.relative_to(self.vault_path)),
                        "title": md_file.stem,
                        "modified": stat.st_mtime,
                    }
                )
            except Exception:
                continue
        notes.sort(key=lambda x: x["modified"], reverse=True)
        return notes[:limit]

    def _extract_snippet(self, content: str, keywords: list[str], context: int = 150) -> str:
        content_lower = content.lower()
        for kw in keywords:
            idx = content_lower.find(kw)
            if idx >= 0:
                start = max(0, idx - context // 2)
                end = min(len(content), idx + context)
                snippet = content[start:end].replace("\n", " ").strip()
                return f"...{snippet}..."
        lines = content.split("\n")
        return " ".join(lines[:3])[:context]


brain = ObsidianBrain()
