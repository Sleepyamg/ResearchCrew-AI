
from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if not 1 <= max_results <= 10:
        raise ValueError("max_results must be between 1 and 10.")

    raw_results = DDGS().text(
        query,
        max_results=max_results
    )

    results = []

    for item in raw_results:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", "")
        })

    return results
