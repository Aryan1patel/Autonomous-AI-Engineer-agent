from langchain.tools import tool 
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient
import os 
from dotenv import load_dotenv
from rich import print
load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Realistic browser headers to reduce bot-detection blocks
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

@tool
def web_search(query: str) -> str:
    """Search the web for recent and reliable information on a topic. Returns Titles, URLs and snippets."""
    results = tavily.search(query=query, max_results=5)

    out = []
    for r in results['results']:
        out.append(
            f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['content'][:300]}\n"
        )
    
    return "\n----\n".join(out)

@tool
def scrape_url(url: str) -> str:
    """Scrape and return clean text content from a given URL for deeper reading.
    Automatically falls back to Tavily extract if the site blocks direct requests (e.g. Cloudflare)."""

    # --- Primary: direct HTTP scrape ---
    try:
        resp = requests.get(url, timeout=10, headers=_HEADERS)
        # Cloudflare / bot-wall detection: status 403/429/503 or challenge page
        if resp.status_code in (403, 429, 503) or "cf-mitigated" in resp.headers:
            raise ValueError(f"Blocked with status {resp.status_code}")
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Check for Cloudflare challenge in body
        if "cf-browser-verification" in resp.text or "Just a moment" in resp.text[:500]:
            raise ValueError("Cloudflare challenge detected")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        if len(text) > 200:          # valid page
            return text[:4000]
        raise ValueError("Page returned too little content")

    except Exception as primary_err:
        # --- Fallback: Tavily extract (handles JS/Cloudflare sites) ---
        try:
            extracted = tavily.extract(urls=[url])
            results = extracted.get("results", [])
            if results:
                content = results[0].get("raw_content", "")
                return content[:4000] if content else f"Tavily extracted empty content from {url}"
            return f"Tavily could not extract content from {url}"
        except Exception as fallback_err:
            return (
                f"Could not scrape URL: {url}\n"
                f"Direct error: {primary_err}\n"
                f"Tavily fallback error: {fallback_err}"
            )
