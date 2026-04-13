"""
crossref_scraper.py — CrossRef Academic API Scraper.

CrossRef is a free metadata API for 150M+ scholarly works.
It provides:
  - NO API key required (polite pool with email)
  - NO rate limiting for polite users
  - NO CAPTCHA or bot detection
  - Links to full-text PDFs via publisher TDM agreements
  - Excellent DOI-based metadata

Limitations:
  - PDF links go through publisher APIs (may require institutional access)
  - Better for English-language papers
  - Focus on journal articles (fewer conference papers)

API Docs: https://api.crossref.org
"""

import re
import logging
import requests
from typing import List
from urllib.parse import urlparse
from html import unescape

from .base_scraper import BaseScraper, ScraperConfig, PaperResult

logger = logging.getLogger(__name__)

_MAILTO = "scholarscrape@academic-tool.com"


class CrossRefScraper(BaseScraper):
    """
    Searches CrossRef for academic papers with full-text PDF links.

    CrossRef is one of the largest scholarly metadata APIs, indexing
    150M+ DOIs. It provides reliable links to publisher-hosted PDFs.
    """

    SOURCE_NAME = "CrossRef"
    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"ScholarScrape/1.0 (mailto:{_MAILTO})",
            "Accept": "application/json",
        })

    # ── Required Abstract Implementations ────────────────────────
    @property
    def name(self) -> str:
        return self.SOURCE_NAME

    def _build_search_url(self, query: str, start: int = 0) -> str:
        return f"{self.BASE_URL}?query={query}&rows=25&offset={start}"

    # ── Helpers ──────────────────────────────────────────────────
    @staticmethod
    def _extract_authors(item: dict) -> str:
        """Extract author names from CrossRef item."""
        authors = item.get("author", [])
        names = []
        for a in authors[:5]:
            given = a.get("given", "")
            family = a.get("family", "")
            if given and family:
                names.append(f"{given} {family}")
            elif family:
                names.append(family)
        result = ", ".join(names)
        if len(authors) > 5:
            result += f" (+{len(authors) - 5} more)"
        return result

    @staticmethod
    def _extract_year(item: dict) -> str:
        """Extract publication year from date-parts."""
        published = item.get("published") or item.get("published-online") or item.get("published-print")
        if published:
            parts = published.get("date-parts", [[]])
            if parts and parts[0]:
                return str(parts[0][0])
        return ""

    @staticmethod
    def _extract_pdf_url(item: dict) -> str:
        """
        Extract PDF URL from CrossRef links.

        Priority:
        1. link[] with content-type application/pdf
        2. link[] with content-type containing 'unspecified'
        3. DOI URL as fallback
        """
        links = item.get("link", [])

        # Look for explicit PDF link
        for link in links:
            content_type = link.get("content-type", "").lower()
            url = link.get("URL", "")
            if "pdf" in content_type and url:
                return url

        # Fallback: any TDM link
        for link in links:
            url = link.get("URL", "")
            intended = link.get("intended-application", "").lower()
            if intended == "text-mining" and url:
                return url

        # Last resort: use DOI link directly (may redirect to PDF)
        doi = item.get("DOI", "")
        if doi:
            return f"https://doi.org/{doi}"

        return ""

    @staticmethod
    def _clean_title(title_list: list) -> str:
        """Clean title from CrossRef format."""
        if not title_list:
            return ""
        raw = title_list[0]
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', raw)
        # Unescape HTML entities
        clean = unescape(clean)
        return clean.strip()

    @staticmethod
    def _extract_abstract(item: dict) -> str:
        """Extract and clean abstract text."""
        abstract = item.get("abstract", "")
        if abstract:
            # Remove JATS XML tags
            abstract = re.sub(r'<[^>]+>', '', abstract)
            abstract = unescape(abstract).strip()
            return abstract[:400]
        return ""

    # ── Main Search ──────────────────────────────────────────────
    def search(
        self,
        query: str,
        max_results: int = 10,
        callback=None,
    ) -> List[PaperResult]:
        """
        Search CrossRef for papers with downloadable content.
        """
        lang = getattr(self.config, "language", "en")

        if callback:
            callback(f"Searching CrossRef (150M+ DOIs): \"{query[:55]}...\"")
            callback("Using REST API (no browser needed)...")

        try:
            # Build filter parts
            filter_parts = ["has-full-text:true"]

            # ── Year filter ──────────────────────────────────────
            year_from = getattr(self.config, "year_from", 0)
            year_to = getattr(self.config, "year_to", 0)

            if year_from:
                filter_parts.append(f"from-pub-date:{year_from}")
                if callback:
                    callback(f"📅 Year from: {year_from}")
            if year_to:
                filter_parts.append(f"until-pub-date:{year_to}")
                if callback:
                    callback(f"📅 Year to: {year_to}")

            # ── Repository filter ────────────────────────────────
            repo = getattr(self.config, "repository", "")
            search_query = query

            if repo in ("scopus", "sinta", "wos"):
                search_query = f"{query} {repo.upper()} indexed"
                if callback:
                    callback(f"📋 Repository: {repo.upper()}")

            params = {
                "query": search_query,
                "rows": min(max_results * 2, 50),
                "filter": ",".join(filter_parts),
                "sort": "relevance",
                "order": "desc",
                "mailto": _MAILTO,
            }

            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.config.page_load_timeout,
            )
            response.raise_for_status()

            data = response.json()
            items = data.get("message", {}).get("items", [])
            total = data.get("message", {}).get("total-results", 0)

            if callback:
                callback(f"CrossRef returned {total} total matches, processing top {len(items)}...")

            results = []

            for item in items:
                if len(results) >= max_results:
                    break

                title = self._clean_title(item.get("title", []))
                if not title:
                    continue

                pdf_url = self._extract_pdf_url(item)
                if not pdf_url:
                    continue

                authors = self._extract_authors(item)
                year = self._extract_year(item)
                abstract = self._extract_abstract(item)

                # Get journal name
                journal = ""
                container = item.get("container-title", [])
                if container:
                    journal = container[0]

                paper = PaperResult(
                    title=title,
                    pdf_url=pdf_url,
                    source=self.SOURCE_NAME,
                    authors=authors,
                    year=year,
                    abstract=abstract,
                )
                results.append(paper)

                if callback:
                    journal_tag = f" [{journal[:25]}]" if journal else ""
                    year_tag = f" ({year})" if year else ""
                    callback(
                        f"  📄 {title[:50]}...{year_tag}{journal_tag}"
                    )

            if callback:
                emoji = "✅" if results else "⚠️"
                callback(f"{emoji} CrossRef found {len(results)} downloadable PDF(s)")

            return results

        except requests.exceptions.HTTPError as e:
            logger.error(f"CrossRef HTTP error: {e}")
            if callback:
                callback(f"❌ HTTP Error: {e}")
            return []
        except Exception as e:
            logger.error(f"CrossRef error: {e}")
            if callback:
                callback(f"❌ Error: {str(e)}")
            return []

    # ── Interface ────────────────────────────────────────────────
    def needs_browser(self) -> bool:
        return False

    def close(self):
        self.session.close()
