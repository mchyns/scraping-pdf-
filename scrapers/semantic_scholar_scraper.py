"""
semantic_scholar_scraper.py — Semantic Scholar API scraper.

Uses the free Semantic Scholar Academic Graph API to search papers.
No browser needed — pure HTTP requests. Very reliable and fast.

API Docs: https://api.semanticscholar.org/
Rate Limit: 100 requests per 5 minutes (unauthenticated)

Open Access PDF links are provided directly by the API when available.
"""

import time
import logging
from typing import List, Optional

import requests

from .base_scraper import BaseScraper, PaperResult, ScraperConfig

logger = logging.getLogger(__name__)


class SemanticScholarScraper(BaseScraper):
    """
    Scraper for Semantic Scholar — AI-powered academic search engine by
    Allen Institute for AI. Covers 200M+ papers across all fields.

    Strategy:
        1. Use the free REST API (no auth required).
        2. Parse JSON responses directly — no browser needed.
        3. Extract open-access PDF URLs from the response.
    """

    API_BASE = "https://api.semanticscholar.org/graph/v1"
    SEARCH_ENDPOINT = f"{API_BASE}/paper/search"
    RESULTS_PER_PAGE = 100  # API max

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "ScholarScrape/1.0 "
                "(Academic PDF Downloader; contact: research@example.com)"
            ),
        })

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Semantic Scholar"

    # ── Public API ───────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[PaperResult]:
        """
        Search Semantic Scholar for papers matching the query.

        Args:
            query: Search topic or title keywords.
            max_results: Maximum number of PaperResults to return.

        Returns:
            List of PaperResult with title, pdf_url, authors, etc.
        """
        results: List[PaperResult] = []
        offset = 0

        logger.info(
            f"[Semantic Scholar] Searching for: '{query}' "
            f"(max {max_results} results)"
        )

        while len(results) < max_results:
            limit = min(self.RESULTS_PER_PAGE, max_results - len(results) + 20)

            params = {
                "query": query,
                "offset": offset,
                "limit": limit,
                "fields": (
                    "title,authors,year,externalIds,"
                    "openAccessPdf,url,isOpenAccess"
                ),
            }

            try:
                logger.info(
                    f"[Semantic Scholar] API request: offset={offset}, limit={limit}"
                )
                response = self._session.get(
                    self.SEARCH_ENDPOINT,
                    params=params,
                    timeout=self.config.page_load_timeout,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning(
                        "[Semantic Scholar] Rate limited. Waiting 30s..."
                    )
                    time.sleep(30)
                    continue

                response.raise_for_status()
                data = response.json()

                papers = data.get("data", [])
                total_available = data.get("total", 0)

                if not papers:
                    logger.info("[Semantic Scholar] No more results available.")
                    break

                for paper_data in papers:
                    paper = self._parse_paper(paper_data)
                    if paper:
                        results.append(paper)

                logger.info(
                    f"[Semantic Scholar] Collected {len(results)} results "
                    f"(total available: {total_available})"
                )

                # Check if there are more pages
                if offset + limit >= total_available:
                    break

                offset += limit
                time.sleep(self.config.request_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"[Semantic Scholar] API error: {e}")
                break
            except Exception as e:
                logger.error(f"[Semantic Scholar] Unexpected error: {e}")
                break

        return results[:max_results]

    def close(self):
        """Close the requests session."""
        if self._session:
            self._session.close()

    # ── Private Methods ──────────────────────────────────────────────

    def _build_search_url(self, query: str, start: int = 0) -> str:
        """Build API URL (for reference/logging only)."""
        return f"{self.SEARCH_ENDPOINT}?query={query}&offset={start}"

    def _parse_paper(self, data: dict) -> Optional[PaperResult]:
        """
        Parse a single paper from API response JSON.

        Args:
            data: Dict from the API response's 'data' array.

        Returns:
            PaperResult if valid, None otherwise.
        """
        title = data.get("title", "").strip()
        if not title:
            return None

        # ── Authors ──────────────────────────────────────────────
        authors_list = data.get("authors", [])
        authors = ", ".join(
            a.get("name", "") for a in authors_list[:5]
        )
        if len(authors_list) > 5:
            authors += f" et al. (+{len(authors_list) - 5})"

        # ── Year ─────────────────────────────────────────────────
        year = str(data.get("year", "")) if data.get("year") else ""

        # ── PDF URL ──────────────────────────────────────────────
        pdf_url = None
        open_access_pdf = data.get("openAccessPdf")
        if open_access_pdf and isinstance(open_access_pdf, dict):
            pdf_url = open_access_pdf.get("url")

        # Fallback: try arXiv ID
        if not pdf_url:
            external_ids = data.get("externalIds", {})
            if external_ids:
                arxiv_id = external_ids.get("ArXiv")
                if arxiv_id:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # ── Abstract URL ─────────────────────────────────────────
        abstract_url = data.get("url", "")

        return PaperResult(
            title=title,
            pdf_url=pdf_url,
            abstract_url=abstract_url,
            authors=authors,
            year=year,
            source="Semantic Scholar",
        )
