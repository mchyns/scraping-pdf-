"""
google_scholar_scraper.py — Google Scholar scraper (requests-based).

Uses pure HTTP requests with BeautifulSoup for parsing — NO Selenium,
NO WebDriver. This approach is significantly stealthier because:
  1. No WebDriver fingerprint at all.
  2. Proper session/cookie handling mimics a real browser.
  3. Rotating User-Agent headers reduce detection risk.

Google Scholar shows [PDF] links on the right side of results when
a free version is available.

Supports language filtering:
  - English: &lr=lang_en
  - Indonesian: &lr=lang_id (finds Indonesian-language papers)
"""

import time
import random
import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, PaperResult, ScraperConfig

logger = logging.getLogger(__name__)

# Pool of real browser User-Agents to rotate through
_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]


class GoogleScholarScraper(BaseScraper):
    """
    Scraper for Google Scholar — the largest academic search engine.

    Strategy (requests-based, no Selenium):
        1. Create a requests.Session with realistic browser headers.
        2. First visit the Google Scholar homepage to get cookies.
        3. Then perform search queries with proper Referer headers.
        4. Parse results with BeautifulSoup.
        5. Use random delays between requests.

    Language Support:
        - English (en): &lr=lang_en&hl=en
        - Indonesian (id): &lr=lang_id&hl=id (finds Indonesian papers)
    """

    BASE_URL = "https://scholar.google.com"
    RESULTS_PER_PAGE = 10  # Google Scholar default

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self._session = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Google Scholar"

    # ── Public API ───────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[PaperResult]:
        """
        Search Google Scholar for papers matching the query.

        Args:
            query: Search topic or title keywords.
            max_results: Maximum number of PaperResults to return.

        Returns:
            List of PaperResult with title, pdf_url, authors, etc.
        """
        results: List[PaperResult] = []
        start = 0

        logger.info(
            f"[Google Scholar] Searching for: '{query}' "
            f"(max {max_results} results, lang={self.config.language})"
        )

        # Initialize session with cookies
        self._init_session()

        while len(results) < max_results:
            url = self._build_search_url(query, start=start)
            logger.info(f"[Google Scholar] Fetching page: {url}")

            try:
                # Random delay to mimic human behavior
                jitter = random.uniform(1.0, 3.0)
                delay = self.config.request_delay + jitter
                logger.info(f"[Google Scholar] Waiting {delay:.1f}s...")
                time.sleep(delay)

                response = self._session.get(
                    url,
                    timeout=self.config.page_load_timeout,
                )
                response.raise_for_status()

                html = response.text

                # Check for CAPTCHA / bot detection
                if self._is_blocked(html):
                    logger.warning(
                        "[Google Scholar] Bot detection triggered! "
                        "Trying to recover with new session..."
                    )
                    # Try once with a new session
                    time.sleep(random.uniform(5, 10))
                    self._init_session()

                    response = self._session.get(
                        url,
                        timeout=self.config.page_load_timeout,
                    )
                    html = response.text

                    if self._is_blocked(html):
                        logger.error(
                            "[Google Scholar] Still blocked after retry. "
                            "Try again later or increase request delay."
                        )
                        break

                page_results = self._parse_results_page(html)

                if not page_results:
                    logger.info("[Google Scholar] No results on this page.")
                    break

                results.extend(page_results)
                logger.info(
                    f"[Google Scholar] Collected {len(results)} results "
                    f"(this page: {len(page_results)})"
                )

                if len(page_results) < self.RESULTS_PER_PAGE:
                    break

                start += self.RESULTS_PER_PAGE

            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    logger.warning(
                        "[Google Scholar] Rate limited (429). Waiting 30s..."
                    )
                    time.sleep(30)
                    continue
                logger.error(f"[Google Scholar] HTTP error: {e}")
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"[Google Scholar] Request error: {e}")
                break
            except Exception as e:
                logger.error(f"[Google Scholar] Unexpected error: {e}")
                break

        return results[:max_results]

    def close(self):
        """Close the requests session."""
        if self._session:
            self._session.close()
            self._session = None

    # ── Private Methods ──────────────────────────────────────────────

    def _init_session(self):
        """
        Create a new requests session with realistic browser headers.
        Visits Google Scholar homepage first to collect cookies.
        """
        if self._session:
            self._session.close()

        self._session = requests.Session()
        ua = random.choice(_USER_AGENTS)

        # Set headers that mimic a real browser
        self._session.headers.update({
            "User-Agent": ua,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": (
                "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
                if self.config.language == "id"
                else "en-US,en;q=0.9"
            ),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })

        # Visit homepage to get cookies (like a real user would)
        try:
            logger.info("[Google Scholar] Initializing session (getting cookies)...")
            homepage = self._session.get(
                self.BASE_URL,
                timeout=15,
            )
            logger.info(
                f"[Google Scholar] Session ready "
                f"(cookies: {len(self._session.cookies)})"
            )

            # Now update headers for subsequent requests
            self._session.headers.update({
                "Referer": self.BASE_URL + "/",
                "Sec-Fetch-Site": "same-origin",
            })

        except Exception as e:
            logger.warning(f"[Google Scholar] Cookie init failed: {e}")

    def _build_search_url(self, query: str, start: int = 0) -> str:
        """
        Build a Google Scholar search URL with language support.

        Language filtering:
            - &lr=lang_en → English papers
            - &lr=lang_id → Indonesian papers
            - &hl=id → Indonesian UI (helps get local results)
        """
        encoded_query = quote_plus(query)

        lang = self.config.language
        hl = "id" if lang == "id" else "en"
        lr = f"lang_{lang}" if lang in ("en", "id") else ""

        url = f"{self.BASE_URL}/scholar?q={encoded_query}&hl={hl}"

        if lr:
            url += f"&lr={lr}"

        url += f"&start={start}"

        return url

    def _is_blocked(self, html: str) -> bool:
        """Check if Google Scholar returned a CAPTCHA or block page."""
        blocked_signals = [
            "unusual traffic",
            "captcha",
            "sorry/index",
            "automated requests",
            "please show you're not a robot",
            "systems have detected unusual traffic",
        ]
        html_lower = html.lower()
        return any(signal in html_lower for signal in blocked_signals)

    def _parse_results_page(self, html: str) -> List[PaperResult]:
        """Parse Google Scholar search results page."""
        soup = BeautifulSoup(html, "lxml")
        results: List[PaperResult] = []

        items = soup.find_all("div", class_="gs_r")

        if not items:
            # Try alternate selector
            items = soup.find_all("div", {"data-cid": True})

        for item in items:
            try:
                paper = self._parse_single_result(item)
                if paper:
                    results.append(paper)
            except Exception as e:
                logger.warning(f"[Google Scholar] Error parsing result: {e}")
                continue

        return results

    def _parse_single_result(self, item) -> Optional[PaperResult]:
        """Parse a single Google Scholar result into a PaperResult."""

        # ── Title & Abstract URL ─────────────────────────────────
        title_container = item.find("h3", class_="gs_rt")
        if not title_container:
            return None

        title_link = title_container.find("a")
        if title_link:
            title = title_link.get_text(strip=True)
            abstract_url = title_link.get("href", "")
        else:
            title = title_container.get_text(strip=True)
            abstract_url = ""

        # Remove "[PDF]", "[HTML]" prefixes
        title = re.sub(r"^\[(PDF|HTML|BOOK|CITATION)\]\s*", "", title).strip()

        if not title:
            return None

        # ── Authors & Year ───────────────────────────────────────
        authors = ""
        year = ""
        meta_div = item.find("div", class_="gs_a")
        if meta_div:
            meta_text = meta_div.get_text(strip=True)
            parts = meta_text.split(" - ")
            if parts:
                authors = parts[0].strip()
            year_match = re.search(r"\b(19|20)\d{2}\b", meta_text)
            if year_match:
                year = year_match.group(0)

        # ── PDF URL ──────────────────────────────────────────────
        pdf_url = None

        # Check for [PDF] link on the right side
        pdf_container = item.find("div", class_="gs_ggs")
        if pdf_container:
            pdf_link = pdf_container.find("a", href=True)
            if pdf_link:
                pdf_url = pdf_link["href"]

        # Also check gs_or_ggsm (mobile/alternate layout)
        if not pdf_url:
            alt_pdf = item.find("div", class_="gs_or_ggsm")
            if alt_pdf:
                pdf_link = alt_pdf.find("a", href=True)
                if pdf_link:
                    href = pdf_link["href"]
                    if href.endswith(".pdf") or "/pdf/" in href:
                        pdf_url = href

        # Fallback: check if the main link is a PDF
        if not pdf_url and abstract_url:
            if abstract_url.lower().endswith(".pdf"):
                pdf_url = abstract_url

        return PaperResult(
            title=title,
            pdf_url=pdf_url,
            abstract_url=abstract_url,
            authors=authors,
            year=year,
            source="Google Scholar",
        )
