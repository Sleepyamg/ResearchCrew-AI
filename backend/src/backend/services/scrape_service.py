
import httpx
import trafilatura
import re
from bs4 import BeautifulSoup


def fetch_html(url: str) -> str:

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL")

    headers = {
        "User-Agent": "ResearchCrewBot/0.1",
        "Accept": "text/html"
    }

    response = httpx.get(
        url,
        headers=headers,
        timeout=15,
        follow_redirects=True
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type", ""
    ).lower()

    if "text/html" not in content_type:
        raise ValueError("URL does not contain HTML")

    return response.text


def extract_content(html: str) -> dict:

    soup = BeautifulSoup(html, "html.parser")

    title = (
        soup.title.get_text(strip=True)
        if soup.title else "Untitled"
    )

    content = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True
    )

    method = "trafilatura"

    # Fallback extraction
    if not content or len(content.strip()) < 200:

        for tag in soup([
            "script", "style", "nav",
            "footer", "header", "aside",
            "noscript", "head"
        ]):
            tag.decompose()

        main = (
            soup.find("article")
            or soup.find("main")
            or soup.body
            or soup
        )

        content = main.get_text(
            separator=" ",
            strip=True
        )

        method = "beautifulsoup"

    return {
        "title": title,
        "content": content,
        "method": method
    }


def clean_content(text: str) -> str:

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def scrape_url(
    url: str,
    max_chars: int = 6000
) -> dict:

    if not 1 <= max_chars <= 12000:
        raise ValueError("Invalid content length")

    html = fetch_html(url)

    result = extract_content(html)

    content = clean_content(result["content"])

    if len(content) < 200:
        raise ValueError("Insufficient page content")

    truncated = len(content) > max_chars

    return {
        "url": url,
        "title": result["title"],
        "content": content[:max_chars],
        "method": result["method"],
        "truncated": truncated
    }
