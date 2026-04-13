"""
duckduckgo_scraper.py — DuckDuckGo PDF Scraper (via ddgs package).

Uses the modern `ddgs` package (successor to `duckduckgo_search`) to
search DuckDuckGo. NO CAPTCHA, NO bot detection. Searches the entire
internet for PDF documents.

Improved strategy:
  1. Search with PDF-related keywords (not filetype: operator)
  2. Filter results by URL patterns (.pdf, /download/, /pdf/)
  3. Accept results from known academic domains
  4. Broader fallback pass with journal/jurnal keywords
"""

import re
import logging
from urllib.parse import urlparse
from typing import List

from .base_scraper import BaseScraper, ScraperConfig, PaperResult

logger = logging.getLogger(__name__)

# Lazy import
_DDGS = None


def _get_ddgs():
    """Import DDGS from the correct package."""
    global _DDGS
    if _DDGS is None:
        try:
            from ddgs import DDGS
            _DDGS = DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
                _DDGS = DDGS
            except ImportError:
                raise ImportError(
                    "Neither 'ddgs' nor 'duckduckgo-search' is installed. "
                    "Run: pip install ddgs"
                )
    return _DDGS


# Academic domains that commonly host PDFs
_ACADEMIC_DOMAINS = {
    "ac.id", "edu", "ac.uk", "edu.au", "ac.jp", "edu.cn",
    "researchgate.net", "academia.edu", "arxiv.org",
    "scielo.br", "doaj.org", "core.ac.uk",
}


class DuckDuckGoScraper(BaseScraper):
    """
    Searches DuckDuckGo for PDF files across the entire internet.
    Uses the ddgs package for reliable search without CAPTCHA.
    """

    SOURCE_NAME = "DuckDuckGo"

    def __init__(self, config: ScraperConfig):
        super().__init__(config)

    @property
    def name(self) -> str:
        return self.SOURCE_NAME

    def _build_search_url(self, query: str, start: int = 0) -> str:
        return f"https://duckduckgo.com/?q={query}+PDF"

    # ── Helpers ──────────────────────────────────────────────────
    @staticmethod
    def _is_pdf_url(url: str) -> bool:
        """Check if URL likely points to a PDF."""
        lower = url.lower()
        if lower.endswith(".pdf"):
            return True
        if "/pdf/" in lower or "/download/" in lower:
            return True
        if "format=pdf" in lower or "type=pdf" in lower:
            return True
        # Academic repository patterns
        if "/article/download/" in lower or "/bitstream/" in lower:
            return True
        return False

    @staticmethod
    def _is_academic_domain(url: str) -> bool:
        """Check if URL belongs to an academic domain."""
        domain = urlparse(url).netloc.lower()
        for pattern in _ACADEMIC_DOMAINS:
            if domain.endswith(pattern) or f".{pattern}" in domain:
                return True
        # Common Indonesian journal hosts
        if any(kw in domain for kw in [
            "jurnal", "journal", "ejournal", "neliti",
            "garuda", "sinta", "repository",
        ]):
            return True
        return False

    @staticmethod
    def _clean_title(title: str) -> str:
        title = re.sub(r'\[PDF\]\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()
        return title or "Untitled PDF"

    @staticmethod
    def _extract_year(text: str) -> str:
        match = re.search(r'\b(19|20)\d{2}\b', text)
        return match.group(0) if match else ""

    # ── Main Search ──────────────────────────────────────────────
    def search(
        self,
        query: str,
        max_results: int = 10,
        callback=None,
    ) -> List[PaperResult]:
        """
        Search DuckDuckGo for PDFs matching the query.
        Uses multiple search passes with progressively relaxed filters.
        """
        DDGS = _get_ddgs()
        lang = getattr(self.config, "language", "en")
        region = "id-id" if lang == "id" else "wt-wt"

        if callback:
            callback(f"Searching DuckDuckGo: \"{query[:55]}...\"")
            callback(f"Region: {region} | No CAPTCHA 🚀")

        try:
            ddgs = DDGS()
            results = []
            seen_urls = set()

            # ── Build year suffix ────────────────────────────────
            year_from = getattr(self.config, "year_from", 0)
            year_to = getattr(self.config, "year_to", 0)
            year_suffix = ""
            if year_from and year_to:
                year_suffix = f" {year_from}-{year_to}"
            elif year_from:
                year_suffix = f" {year_from}"
            elif year_to:
                year_suffix = f" {year_to}"

            # ── Repository suffix ────────────────────────────────
            repo = getattr(self.config, "repository", "")
            repo_suffix = ""
            if repo == "scopus":
                repo_suffix = " Scopus indexed"
            elif repo == "sinta":
                repo_suffix = " SINTA terakreditasi"
            elif repo == "doaj":
                repo_suffix = " DOAJ open access"
            elif repo == "wos":
                repo_suffix = " Web of Science"

            # ── Pass 1: Direct PDF search ────────────────────────
            if lang == "id":
                search_q = f"{query} PDF jurnal{year_suffix}{repo_suffix}"
            else:
                search_q = f"{query} PDF journal article{year_suffix}{repo_suffix}"

            if callback:
                callback(f"Pass 1: \"{search_q[:70]}\"")

            raw = list(ddgs.text(
                search_q,
                region=region,
                max_results=max_results * 3,
            ))

            if callback:
                callback(f"Got {len(raw)} results, filtering...")

            for item in raw:
                if len(results) >= max_results:
                    break

                url = item.get("href", "") or item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("body", "") or item.get("snippet", "")

                if not url or url in seen_urls:
                    continue

                # Accept if: PDF URL OR academic domain
                is_valid = (
                    self._is_pdf_url(url)
                    or self._is_academic_domain(url)
                )

                if not is_valid:
                    # Check if title/snippet mentions PDF
                    combined = f"{title} {snippet}".lower()
                    if any(kw in combined for kw in [
                        "pdf", ".pdf", "download", "unduh",
                        "jurnal", "journal", "full text",
                    ]):
                        is_valid = True

                if not is_valid:
                    continue

                seen_urls.add(url)
                clean = self._clean_title(title)
                domain = urlparse(url).netloc.replace("www.", "")
                year = self._extract_year(f"{title} {snippet}")

                paper = PaperResult(
                    title=clean,
                    pdf_url=url,
                    source=self.SOURCE_NAME,
                    authors=domain,
                    year=year,
                    abstract=snippet[:300] if snippet else "",
                )
                results.append(paper)

                if callback:
                    tag = "📄" if self._is_pdf_url(url) else "🔗"
                    callback(f"  {tag} {clean[:55]}... [{domain}]")

            # ── Pass 2: Fallback with keyword variations ─────────
            if len(results) < max_results:
                if callback:
                    callback("Pass 2: Broader search...")

                try:
                    if lang == "id":
                        fallback_q = f"{query} artikel ilmiah download PDF{year_suffix}"
                    else:
                        fallback_q = f"{query} research paper download PDF{year_suffix}"

                    raw2 = list(ddgs.text(
                        fallback_q,
                        region=region,
                        max_results=max_results * 2,
                    ))

                    for item in raw2:
                        if len(results) >= max_results:
                            break

                        url = item.get("href", "") or item.get("link", "")
                        if not url or url in seen_urls:
                            continue

                        if not (self._is_pdf_url(url) or self._is_academic_domain(url)):
                            continue

                        seen_urls.add(url)
                        title = item.get("title", "")
                        snippet = item.get("body", "") or item.get("snippet", "")
                        clean = self._clean_title(title)
                        domain = urlparse(url).netloc.replace("www.", "")
                        year = self._extract_year(f"{title} {snippet}")

                        paper = PaperResult(
                            title=clean,
                            pdf_url=url,
                            source=self.SOURCE_NAME,
                            authors=domain,
                            year=year,
                            abstract=snippet[:300] if snippet else "",
                        )
                        results.append(paper)

                        if callback:
                            callback(f"  📄 {clean[:55]}... [{domain}]")

                except Exception as e:
                    logger.debug(f"Fallback search failed: {e}")

            if callback:
                emoji = "✅" if results else "⚠️"
                callback(f"{emoji} DuckDuckGo found {len(results)} PDF(s)")

            return results

        except ImportError:
            if callback:
                callback("❌ ddgs library not installed!")
                callback("   Run: pip install ddgs")
            return []

        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")
            if callback:
                callback(f"❌ DuckDuckGo error: {str(e)}")
            return []

    def needs_browser(self) -> bool:
        return False

    def close(self):
        pass
