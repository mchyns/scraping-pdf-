"""
garuda_scraper.py — Garuda Kemdikbud scraper for Indonesian journals.

Garuda (Garba Rujukan Digital) is the Indonesian national journal
database maintained by Kemendikbud. It indexes thousands of
Indonesian academic journals with open-access PDFs.

URL: https://garuda.kemdikbud.go.id
"""

import time
import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, PaperResult, ScraperConfig

logger = logging.getLogger(__name__)


class GarudaScraper(BaseScraper):
    """
    Scraper for Garuda Kemdikbud — Indonesia's national journal index.

    Strategy:
        1. Use the Garuda search page with requests (no browser needed).
        2. Parse HTML results with BeautifulSoup.
        3. Extract article page links and find PDF download links.
        4. Most Garuda-indexed journals are open-access.

    Perfect for finding Indonesian-language academic papers.
    """

    BASE_URL = "https://garuda.kemdikbud.go.id"
    SEARCH_URL = "https://garuda.kemdikbud.go.id/documents"

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Garuda"

    # ── Public API ───────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[PaperResult]:
        """
        Search Garuda Kemdikbud for Indonesian journal articles.

        Args:
            query: Search topic or title keywords (Indonesian or English).
            max_results: Maximum number of PaperResults to return.

        Returns:
            List of PaperResult with title, pdf_url, authors, etc.
        """
        results: List[PaperResult] = []
        page = 1

        logger.info(
            f"[Garuda] Searching for: '{query}' "
            f"(max {max_results} results)"
        )

        while len(results) < max_results:
            url = self._build_search_url(query, start=page)
            logger.info(f"[Garuda] Fetching page {page}: {url}")

            try:
                response = self._session.get(
                    url, timeout=self.config.page_load_timeout
                )
                response.raise_for_status()

                page_results = self._parse_results_page(response.text)

                if not page_results:
                    logger.info("[Garuda] No more results found.")
                    break

                results.extend(page_results)
                logger.info(
                    f"[Garuda] Collected {len(results)} results "
                    f"(this page: {len(page_results)})"
                )

                # Check if we got fewer than expected (last page)
                if len(page_results) < 10:
                    break

                page += 1
                time.sleep(self.config.request_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"[Garuda] Request error: {e}")
                break
            except Exception as e:
                logger.error(f"[Garuda] Unexpected error: {e}")
                break

        return results[:max_results]

    def close(self):
        """Close the requests session."""
        if self._session:
            self._session.close()

    # ── Private Methods ──────────────────────────────────────────────

    def _build_search_url(self, query: str, start: int = 1) -> str:
        """
        Build a Garuda search URL.

        Args:
            query: The search query string.
            start: Page number (1-indexed).

        Returns:
            Garuda search URL.
        """
        encoded_query = quote_plus(query)
        return f"{self.SEARCH_URL}?q={encoded_query}&page={start}"

    def _parse_results_page(self, html: str) -> List[PaperResult]:
        """Parse Garuda search results page."""
        soup = BeautifulSoup(html, "lxml")
        results: List[PaperResult] = []

        # Garuda uses article cards in the search results
        # Look for result items - Garuda's structure may vary
        # Try multiple selectors
        items = soup.find_all("div", class_="article-item")

        if not items:
            items = soup.find_all("div", class_="result-item")

        if not items:
            # Fallback: look for links with article pattern
            items = soup.find_all("div", class_="col-md-12")

        if not items:
            # Try finding any structured result containers
            # Garuda wraps results in a list
            list_items = soup.find_all("li", class_="list-group-item")
            if list_items:
                items = list_items

        for item in items:
            try:
                paper = self._parse_single_result(item)
                if paper:
                    results.append(paper)
            except Exception as e:
                logger.warning(f"[Garuda] Error parsing result: {e}")
                continue

        return results

    def _parse_single_result(self, item) -> Optional[PaperResult]:
        """Parse a single Garuda search result."""

        # ── Title ────────────────────────────────────────────────
        title_tag = item.find("a", class_="title-article")
        if not title_tag:
            # Try alternate selectors
            title_tag = item.find("h3")
            if title_tag:
                title_tag = title_tag.find("a") or title_tag

        if not title_tag:
            title_tag = item.find("a", href=re.compile(r"/documents/detail/"))

        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        if not title or len(title) < 5:
            return None

        # ── Article URL ──────────────────────────────────────────
        abstract_url = ""
        href = title_tag.get("href", "")
        if href:
            abstract_url = urljoin(self.BASE_URL, href)

        # ── Authors ──────────────────────────────────────────────
        authors = ""
        authors_tag = item.find("span", class_="author")
        if not authors_tag:
            authors_tag = item.find("p", class_="author")
        if not authors_tag:
            # Try finding by content pattern
            for tag in item.find_all(["span", "p", "div"]):
                text = tag.get_text(strip=True)
                if text and not text.startswith("http") and len(text) < 200:
                    if "," in text and not any(
                        kw in text.lower()
                        for kw in ["vol", "no.", "hal.", "issn", "doi", "http"]
                    ):
                        authors = text
                        break

        if authors_tag and not authors:
            authors = authors_tag.get_text(strip=True)

        # ── Year ─────────────────────────────────────────────────
        year = ""
        year_match = re.search(r"\b(20[0-2]\d|19\d{2})\b", item.get_text())
        if year_match:
            year = year_match.group(0)

        # ── PDF URL ──────────────────────────────────────────────
        pdf_url = None

        # Method 1: Direct PDF link in the result
        for link in item.find_all("a", href=True):
            href = link["href"]
            if ".pdf" in href.lower():
                pdf_url = urljoin(self.BASE_URL, href)
                break

        # Method 2: If we have the article detail URL, try to
        # construct a PDF link or fetch it from the detail page
        if not pdf_url and abstract_url:
            pdf_url = self._try_extract_pdf_from_detail(abstract_url)

        return PaperResult(
            title=title,
            pdf_url=pdf_url,
            abstract_url=abstract_url,
            authors=authors,
            year=year,
            source="Garuda",
        )

    def _try_extract_pdf_from_detail(self, detail_url: str) -> Optional[str]:
        """
        Visit the article detail page and try to find a PDF link.

        Many Garuda articles link to the original journal site which
        usually has a PDF download button.
        """
        try:
            response = self._session.get(detail_url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Look for PDF download links
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True).lower()

                # Check for explicit PDF links
                if ".pdf" in href.lower():
                    return urljoin(detail_url, href)

                # Check for "download" or "unduh" (Indonesian for download) buttons
                if any(kw in text for kw in ["download pdf", "unduh pdf", "full text", "fulltext"]):
                    return urljoin(detail_url, href)

                # Check for DOI links (may redirect to PDF)
                if "doi.org" in href:
                    return href

            # Look for meta tags with PDF URLs
            meta_pdf = soup.find("meta", {"name": "citation_pdf_url"})
            if meta_pdf:
                return meta_pdf.get("content", "")

            time.sleep(0.5)  # Be nice to the server

        except Exception as e:
            logger.debug(f"[Garuda] Could not extract PDF from detail page: {e}")

        return None
