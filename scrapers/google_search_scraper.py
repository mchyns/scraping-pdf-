"""
google_search_scraper.py — Google Search PDF Scraper.

Searches the ENTIRE internet via Google Search using the `filetype:pdf`
operator. Unlike Google Scholar (which is heavily bot-protected), regular
Google Search is more accessible and finds PDFs from ANY website:
universities, journals, government sites, repositories, etc.

Strategy:
  1. Cookie warm-up by visiting google.com first
  2. Search with `query filetype:pdf` + language filters
  3. Parse result HTML to extract PDF URLs from /url?q= redirects
  4. Rotating User-Agents + realistic headers for stealth
  5. Random delays between requests
"""

import re
import time
import random
import logging
import requests
from urllib.parse import unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from typing import List

from .base_scraper import BaseScraper, ScraperConfig, PaperResult

logger = logging.getLogger(__name__)

# ── Rotating User-Agent Pool ─────────────────────────────────────────
_USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) "
    "Gecko/20100101 Firefox/128.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


class GoogleSearchScraper(BaseScraper):
    """
    Scrapes Google Search for PDF files across the entire internet.

    Uses `filetype:pdf` operator to target PDF documents from any website.
    Supports both English and Indonesian language searches.
    """

    SOURCE_NAME = "Google Search"

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.session = requests.Session()
        self._setup_session()

    # ── Required Abstract Implementations ────────────────────────
    @property
    def name(self) -> str:
        return self.SOURCE_NAME

    def _build_search_url(self, query: str, start: int = 0) -> str:
        lang = getattr(self.config, "language", "en")
        base = "https://www.google.com/search"
        q = f"{query} filetype:pdf"
        return f"{base}?q={q}&num=20&hl={lang}&start={start}"

    # ── Session Setup ────────────────────────────────────────────
    def _setup_session(self):
        """Configure session with realistic browser headers."""
        ua = random.choice(_USER_AGENTS)
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-CH-UA-Platform": '"Windows"',
        })

    # ── Cookie Warm-up ───────────────────────────────────────────
    def _warmup(self):
        """Visit Google homepage to get cookies (looks like a real browser)."""
        try:
            self.session.get("https://www.google.com/", timeout=10)
            time.sleep(random.uniform(0.5, 1.5))
        except Exception:
            pass  # Non-fatal warm-up failure

    # ── URL Extraction ───────────────────────────────────────────
    @staticmethod
    def _extract_url_from_redirect(href: str) -> str:
        """Extract actual URL from Google's /url?q=REAL_URL redirect."""
        if href.startswith("/url?"):
            parsed = parse_qs(urlparse(href).query)
            return parsed.get("q", [""])[0]
        return ""

    @staticmethod
    def _is_pdf_url(url: str) -> bool:
        """Check if URL points to a PDF file."""
        lower = url.lower()
        # Direct .pdf extension or common PDF hosting patterns
        if lower.endswith(".pdf"):
            return True
        if "/pdf/" in lower or "/download/" in lower:
            return True
        return False

    @staticmethod
    def _clean_title(raw: str, fallback_url: str = "") -> str:
        """Clean and generate a readable title."""
        title = re.sub(r'\s+', ' ', raw).strip()
        if not title and fallback_url:
            # Generate title from filename in URL
            filename = fallback_url.rstrip("/").split("/")[-1]
            title = (
                filename
                .replace(".pdf", "")
                .replace("-", " ")
                .replace("_", " ")
                .strip()
            )
        return title or "Untitled PDF"

    # ── Main Search ──────────────────────────────────────────────
    def search(
        self,
        query: str,
        max_results: int = 10,
        callback=None,
    ) -> List[PaperResult]:
        """
        Search Google for PDFs matching the query.

        Args:
            query: Search keywords
            max_results: Maximum number of results to return
            callback: Optional status callback function

        Returns:
            List of PaperResult objects with PDF URLs
        """
        lang = getattr(self.config, "language", "en")

        # Build search query with filetype:pdf
        search_query = f"{query} filetype:pdf"

        # Add year range to query
        year_from = getattr(self.config, "year_from", 0)
        year_to = getattr(self.config, "year_to", 0)
        if year_from and year_to:
            search_query += f" {year_from}..{year_to}"
        elif year_from:
            search_query += f" after:{year_from}"
        elif year_to:
            search_query += f" before:{year_to}"

        # Add repository keywords
        repo = getattr(self.config, "repository", "")
        if repo == "scopus":
            search_query += " Scopus indexed"
        elif repo == "sinta":
            search_query += " SINTA terakreditasi"
        elif repo == "doaj":
            search_query += " DOAJ open access"
        elif repo == "wos":
            search_query += " Web of Science"

        params = {
            "q": search_query,
            "num": min(max_results * 3, 50),
            "hl": lang,
            "gl": "id" if lang == "id" else "us",
        }

        # Add Indonesian language filter
        if lang == "id":
            params["lr"] = "lang_id"

        if callback:
            callback(f"Searching Google for PDFs: \"{query[:60]}...\"")

        try:
            # Cookie warm-up
            self._warmup()

            if callback:
                callback("Fetching search results from Google...")

            response = self.session.get(
                "https://www.google.com/search",
                params=params,
                timeout=self.config.page_load_timeout,
            )
            response.raise_for_status()

            # Check for CAPTCHA
            if "captcha" in response.text.lower() or "unusual traffic" in response.text.lower():
                if callback:
                    callback("⚠️ Google CAPTCHA detected — try DuckDuckGo instead")
                logger.warning("Google Search returned CAPTCHA page")
                return []

            soup = BeautifulSoup(response.text, "lxml")
            results = []
            seen_urls = set()

            # ── Strategy 1: Parse Google result links ────────────
            for a_tag in soup.find_all("a", href=True):
                if len(results) >= max_results:
                    break

                href = a_tag["href"]
                actual_url = self._extract_url_from_redirect(href)

                if not actual_url:
                    continue

                # Skip Google's own domains
                parsed_domain = urlparse(actual_url).netloc.lower()
                if any(g in parsed_domain for g in [
                    "google.com", "google.co", "gstatic.com",
                    "googleapis.com", "youtube.com",
                ]):
                    continue

                # Check if PDF
                if not self._is_pdf_url(actual_url):
                    continue

                # Deduplicate
                if actual_url in seen_urls:
                    continue
                seen_urls.add(actual_url)

                # Extract title
                title_text = ""
                h3 = a_tag.find("h3")
                if h3:
                    title_text = h3.get_text(strip=True)
                else:
                    # Search parent for h3
                    parent = a_tag.parent
                    while parent and parent.name != "body":
                        h3 = parent.find("h3")
                        if h3:
                            title_text = h3.get_text(strip=True)
                            break
                        parent = parent.parent

                title = self._clean_title(title_text, actual_url)

                # Extract snippet/abstract if available
                abstract = ""
                result_div = a_tag.find_parent("div", {"class": True})
                if result_div:
                    spans = result_div.find_all("span")
                    for span in spans:
                        text = span.get_text(strip=True)
                        if len(text) > 50 and text != title_text:
                            abstract = text[:300]
                            break

                # Try to extract domain as "author"
                source_domain = parsed_domain.replace("www.", "")

                paper = PaperResult(
                    title=title,
                    pdf_url=actual_url,
                    source=self.SOURCE_NAME,
                    authors=source_domain,
                    year="",
                    abstract=abstract,
                )
                results.append(paper)

                if callback:
                    callback(f"  📄 {title[:55]}... [{source_domain}]")

            # ── Strategy 2: Fallback — find any direct PDF links ─
            if len(results) < max_results:
                for a_tag in soup.find_all("a", href=True):
                    if len(results) >= max_results:
                        break

                    href = a_tag.get("href", "")
                    if not href.startswith("http"):
                        continue
                    if not href.lower().endswith(".pdf"):
                        continue

                    parsed_domain = urlparse(href).netloc.lower()
                    if "google" in parsed_domain:
                        continue
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    title_text = a_tag.get_text(strip=True)
                    title = self._clean_title(title_text, href)
                    source_domain = parsed_domain.replace("www.", "")

                    paper = PaperResult(
                        title=title,
                        pdf_url=href,
                        source=self.SOURCE_NAME,
                        authors=source_domain,
                        year="",
                        abstract="",
                    )
                    results.append(paper)

                    if callback:
                        callback(f"  📄 {title[:55]}... [{source_domain}]")

            # ── Page 2 if needed ─────────────────────────────────
            if len(results) < max_results:
                time.sleep(random.uniform(2, 4))
                params["start"] = params["num"]
                try:
                    response2 = self.session.get(
                        "https://www.google.com/search",
                        params=params,
                        timeout=self.config.page_load_timeout,
                    )
                    if response2.ok:
                        soup2 = BeautifulSoup(response2.text, "lxml")
                        for a_tag in soup2.find_all("a", href=True):
                            if len(results) >= max_results:
                                break
                            href = a_tag["href"]
                            actual_url = self._extract_url_from_redirect(href)
                            if not actual_url or not self._is_pdf_url(actual_url):
                                continue
                            if actual_url in seen_urls:
                                continue
                            seen_urls.add(actual_url)
                            parsed_domain = urlparse(actual_url).netloc.lower()
                            if "google" in parsed_domain:
                                continue
                            h3 = a_tag.find("h3")
                            title_text = h3.get_text(strip=True) if h3 else ""
                            title = self._clean_title(title_text, actual_url)
                            source_domain = parsed_domain.replace("www.", "")
                            paper = PaperResult(
                                title=title,
                                pdf_url=actual_url,
                                source=self.SOURCE_NAME,
                                authors=source_domain,
                                year="",
                                abstract="",
                            )
                            results.append(paper)
                            if callback:
                                callback(f"  📄 {title[:55]}... [{source_domain}]")
                except Exception:
                    pass  # Page 2 is optional

            if callback:
                n = len(results)
                callback(f"✅ Google Search found {n} PDF(s)")

            return results

        except requests.exceptions.HTTPError as e:
            logger.error(f"Google Search HTTP error: {e}")
            if callback:
                callback(f"❌ HTTP Error: {e}")
            return []
        except Exception as e:
            logger.error(f"Google Search error: {e}")
            if callback:
                callback(f"❌ Error: {str(e)}")
            return []

    # ── Interface ────────────────────────────────────────────────
    def needs_browser(self) -> bool:
        return False

    def close(self):
        self.session.close()
