
import json

from crewai.tools import tool
from backend.services.search_service import search_web


@tool("Web Search")
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the internet for relevant information.

    Returns website titles, URLs, and short descriptions.
    Use this tool when you need current information
    or credible sources about a research topic.
    """

    try:
        results = search_web(query, max_results)

        return json.dumps(
            results,
            indent=2,
            ensure_ascii=False
        )

    except Exception as error:
        return json.dumps({
            "status": "error",
            "message": str(error)
        })
