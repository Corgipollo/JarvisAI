"""Busqueda web via DuckDuckGo — funcional."""
import warnings
warnings.filterwarnings("ignore", message=".*Impersonate.*")


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Busca en internet."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as d:
            results = list(d.text(query, max_results=max_results))
            return [
                {"title": r.get("title", ""), "body": r.get("body", ""), "url": r.get("href", "")}
                for r in results
            ]
    except Exception as e:
        print(f"[Search] Error: {e}")
        return [{"title": "", "body": f"Error buscando: {e}", "url": ""}]


async def search_news(query: str, max_results: int = 5) -> list[dict]:
    """Busca noticias."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as d:
            results = list(d.news(query, max_results=max_results))
            return [
                {"title": r.get("title", ""), "body": r.get("body", ""), "url": r.get("url", "")}
                for r in results
            ]
    except Exception as e:
        return [{"title": "", "body": f"Error: {e}", "url": ""}]
