import requests
import os
from bs4 import BeautifulSoup
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
import urllib3
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _ssl_verify_enabled() -> bool:
    """
    Secure-by-default TLS behavior.

    Set SEARCH_VERIFY_SSL=false only when running in constrained local environments
    with known certificate/toolchain issues.
    """
    value = os.getenv("SEARCH_VERIFY_SSL", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


if not _ssl_verify_enabled():
    # Only silence warnings when user explicitly disables cert verification.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BLOCK_PRONE_DOMAINS = {
    "www.sciencedirect.com",
    "sciencedirect.com",
    "www.mdpi.com",
    "mdpi.com",
    "link.springer.com",
    "onlinelibrary.wiley.com",
    "nature.com",
    "www.nature.com",
}


def _build_session():
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.7,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def _fallback_context_from_result(res: dict, reason: str) -> str:
    title = res.get("title", "Untitled")
    url = res.get("link", "")
    snippet = res.get("snippet", "No snippet available.")
    return (
        f"[Fallback metadata only: {reason}] "
        f"TITLE: {title}. URL: {url}. SNIPPET: {snippet}"
    )


def _looks_like_binary_response(url: str, response: requests.Response) -> bool:
    content_type = response.headers.get("Content-Type", "").lower()
    parsed_path = urlparse(url).path.lower()
    if "application/pdf" in content_type or parsed_path.endswith(".pdf"):
        return True
    if content_type.startswith("image/") or content_type.startswith("video/"):
        return True
    if "application/octet-stream" in content_type:
        return True
    return False

def search_internet(query: str):
    """
    IEEE-Grade Search: Pro-Grade Scraper with expanded headers and 
    SSL resilience to bypass bot-detection and character limits.
    """
    try:
        # 1. Initialize the wrapper
        wrapper = DuckDuckGoSearchAPIWrapper(max_results=3)
        session = _build_session()
        print(f"🌐 [Deep Reader] Initiating search for: '{query}'")
        
        deep_context = ""
        
        # 3. PRO-GRADE HEADERS
        # Modern sites check for more than just User-Agent.
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1", # Do Not Track
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/"
        }

        # 2. Get metadata (URLs and titles)
        try:
            search_results = wrapper.results(query, max_results=3)
        except Exception as wrapper_error:
            print(f"   ⚠️ Wrapper search failed: {wrapper_error}")
            print("   🔁 Falling back to DuckDuckGo HTML scraping...")
            search_results = _fallback_ddg_html_search(query, session)

        if not search_results:
            return "No results found."

        for i, res in enumerate(search_results, 1):
            url = res['link']
            title = res['title']
            print(f"   📖 Reading Source {i}: {url}...")
            
            try:
                domain = _domain_of(url)
                if domain in BLOCK_PRONE_DOMAINS:
                    print(f"      ⚠️  {domain} often blocks bots. Using metadata fallback.")
                    page_content = _fallback_context_from_result(
                        res, "domain frequently blocks automated requests"
                    )
                    deep_context += (
                        f"\n--- SOURCE {i}: {title} (Domain-aware fallback) ---\n"
                        f"URL: {url}\nCONTENT:\n{page_content}\n"
                    )
                    continue

                # 4. RESILIENT REQUEST
                # verify=False is used here to bypass the LibreSSL/OpenSSL mismatch on your Mac
                response = session.get(
                    url,
                    headers=headers,
                    timeout=18,
                    verify=_ssl_verify_enabled(),
                )
                response.raise_for_status()

                if _looks_like_binary_response(url, response):
                    print(
                        f"      ⚠️  Source {i} is a binary/PDF response. Using metadata fallback."
                    )
                    page_content = _fallback_context_from_result(
                        res, "binary or PDF response not parseable as HTML"
                    )
                    deep_context += (
                        f"\n--- SOURCE {i}: {title} (Binary-aware fallback) ---\n"
                        f"URL: {url}\nCONTENT:\n{page_content}\n"
                    )
                    continue
                
                # Check for bot-detection pages (often much smaller than real pages)
                if "CAPTCHA" in response.text.upper() or "ACCESS DENIED" in response.text.upper():
                    raise Exception("Bot detection triggered.")

                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Clean the HTML
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()

                # --- UNIVERSAL SCRAPER PATCH (EXPANDED) ---
                raw_text = soup.get_text(separator=' ', strip=True)
                
                # We expanded the slice to 8000 for deep technical analysis
                page_content = raw_text[:8000] 
                
                # Validation: If we didn't get enough "real" text, fall back to snippet
                if len(page_content) < 300: 
                    print(f"      ⚠️  Source {i} scrape too thin, falling back to metadata.")
                    page_content = _fallback_context_from_result(
                        res, "scraped body too thin"
                    )
                else:
                    print(f"      ✅ Successfully pulled {len(page_content)} characters.")

                deep_context += f"\n--- SOURCE {i}: {title} ---\nURL: {url}\nCONTENT:\n{page_content}\n"

            except Exception as scrape_error:
                print(f"   ⚠️ Could not read {url}: {str(scrape_error)}")
                page_content = _fallback_context_from_result(
                    res, f"read failure: {str(scrape_error)}"
                )
                deep_context += (
                    f"\n--- SOURCE {i}: {title} (Robust fallback) ---\n"
                    f"URL: {url}\nCONTENT:\n{page_content}\n"
                )

        return deep_context

    except Exception as e:
        return f"Search engine error: {str(e)}"


def summarize_context_quality(context: str) -> dict:
    """
    Return basic retrieval quality metrics.

    - total_chars: full payload size
    - fallback_chars: characters coming from fallback metadata blocks
    - usable_chars: best-effort estimate of real extracted body text
    """
    text = str(context or "")
    fallback_tag = "[Fallback metadata only:"
    fallback_chars = 0
    scan_idx = 0

    while True:
        start = text.find(fallback_tag, scan_idx)
        if start == -1:
            break
        end = text.find("\n", start)
        if end == -1:
            end = len(text)
        fallback_chars += (end - start)
        scan_idx = end

    total_chars = len(text)
    usable_chars = max(0, total_chars - fallback_chars)
    return {
        "total_chars": total_chars,
        "fallback_chars": fallback_chars,
        "usable_chars": usable_chars,
    }


def _fallback_ddg_html_search(query: str, session: requests.Session):
    """
    Fallback path for environments where the ddgs/httpx client fails due to TLS/runtime issues.
    Scrapes DuckDuckGo's HTML endpoint and returns a list shaped like wrapper.results().
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    response = session.get(
        url,
        headers=headers,
        timeout=20,
        verify=_ssl_verify_enabled(),
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    parsed = []
    for result in soup.select(".result"):
        link_el = result.select_one(".result__a")
        snippet_el = result.select_one(".result__snippet")
        if not link_el:
            continue

        raw_href = link_el.get("href", "")
        parsed_href = urlparse(raw_href)
        if parsed_href.path == "/l/":
            redirect_qs = parse_qs(parsed_href.query)
            target = unquote(redirect_qs.get("uddg", [""])[0])
            href = target or raw_href
        else:
            href = raw_href

        parsed.append(
            {
                "title": link_el.get_text(strip=True) or "Untitled",
                "link": href,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            }
        )

        if len(parsed) >= 3:
            break

    return parsed