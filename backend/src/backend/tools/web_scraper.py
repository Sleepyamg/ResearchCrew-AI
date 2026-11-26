
import json

from crewai.tools import tool
from backend.services.scrape_service import scrape_url


@tool("Web Scraper")
def web_scraper(url: str) -> str:
    """
    Read and extract the main content of a webpage.

    Use this tool after Web Search to investigate
    relevant sources and retrieve supporting evidence.

    Accepts a valid public HTML webpage URL.
    Returns the page title, content and extraction method.
    """

    try:
        result = scrape_url(url, max_chars=4000)

        return json.dumps(
            result,
            ensure_ascii=False
        )

    except Exception as error:
        return json.dumps({
            "status": "error",
            "url": url,
            "message": str(error)
        })
