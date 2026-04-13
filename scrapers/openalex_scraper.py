"""
openalex_scraper.py — OpenAlex Academic API Scraper.

OpenAlex is a FREE, open-source catalog of 250M+ academic works.
It provides:
  - NO API key required
  - NO rate limiting (polite use)
  - NO CAPTCHA or bot detection
  - Direct PDF download URLs via open-access links
  - Full Indonesian AND English language support
  - Filtering by full-text availability, language, year, etc.

This is the MOST RELIABLE scraper for finding downloadable academic PDFs.
Homepage: https://openalex.org
API Docs: https://docs.openalex.org
"""

import re
import logging
import requests
from typing import List
from urllib.parse import urlparse

from .base_scraper import BaseScraper, ScraperConfig, PaperResult

logger = logging.getLogger(__name__)

# Polite email for API (optional but recommended by OpenAlex)
_MAILTO = "scholarscrape@academic-tool.com"


class OpenAlexScraper(BaseScraper):
    """
    Searches OpenAlex for academic papers with open-access PDF links.

    OpenAlex indexes 250M+ works from journals, conferences, preprints,
    repositories, and more worldwide. It supports multilingual queries.
    """

    SOURCE_NAME = "OpenAlex"
    BASE_URL = "https://api.openalex.org/works"

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
        return f"{self.BASE_URL}?search={query}&per_page=25&page={start // 25 + 1}"

    # ── Helpers ──────────────────────────────────────────────────
    @staticmethod
    def _extract_authors(authorships: list) -> str:
        """Extract author names from OpenAlex authorship data."""
        names = []
        for a in authorships[:5]:  # Max 5 authors
            author = a.get("author", {})
            display_name = author.get("display_name", "")
            if display_name:
                names.append(display_name)
        result = ", ".join(names)
        if len(authorships) > 5:
            result += f" (+{len(authorships) - 5} more)"
        return result

    @staticmethod
    def _extract_year(work: dict) -> str:
        """Extract publication year."""
        year = work.get("publication_year")
        return str(year) if year else ""

    @staticmethod
    def _extract_pdf_url(work: dict) -> str:
        """
        Extract the best available PDF URL from OpenAlex work data.

        Priority:
        1. primary_location.pdf_url (direct PDF)
        2. open_access.oa_url (OA page, often PDF)
        3. best_oa_location.pdf_url
        4. Any location with a pdf_url
        """
        # Priority 1: Primary location PDF
        primary = work.get("primary_location") or {}
        pdf_url = primary.get("pdf_url", "")
        if pdf_url:
            return pdf_url

        # Priority 2: Open access URL
        oa = work.get("open_access") or {}
        oa_url = oa.get("oa_url", "")
        if oa_url:
            return oa_url

        # Priority 3: Best OA location
        best_oa = work.get("best_oa_location") or {}
        pdf_url = best_oa.get("pdf_url", "")
        if pdf_url:
            return pdf_url

        # Priority 4: Any location with PDF
        for loc in work.get("locations", []):
            pdf_url = loc.get("pdf_url", "")
            if pdf_url:
                return pdf_url

        return ""

    @staticmethod
    def _extract_abstract(work: dict) -> str:
        """Extract abstract from inverted index format."""
        abstract_inv = work.get("abstract_inverted_index")
        if not abstract_inv:
            return ""

        # OpenAlex stores abstracts as inverted indices
        # Reconstruct the text
        try:
            word_positions = []
            for word, positions in abstract_inv.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            abstract = " ".join(w for _, w in word_positions)
            return abstract[:400] if abstract else ""
        except Exception:
            return ""

    # ── Main Search ──────────────────────────────────────────────
    def search(
        self,
        query: str,
        max_results: int = 10,
        callback=None,
    ) -> List[PaperResult]:
        """
        Search OpenAlex for papers with downloadable PDFs.
        """
        lang = getattr(self.config, "language", "en")

        if callback:
            callback(f"Searching OpenAlex (250M+ works): \"{query[:55]}...\"")
            callback("Using REST API (no browser needed)...")

        try:
            # Build filter parts
            filter_parts = ["has_fulltext:true", "is_oa:true"]

            # ── Year filter ──────────────────────────────────────
            year_from = getattr(self.config, "year_from", 0)
            year_to = getattr(self.config, "year_to", 0)

            if year_from and year_to:
                filter_parts.append(f"publication_year:{year_from}-{year_to}")
                if callback:
                    callback(f"📅 Year filter: {year_from}–{year_to}")
            elif year_from:
                filter_parts.append(f"publication_year:{year_from}-2099")
                if callback:
                    callback(f"📅 Year filter: {year_from}+")
            elif year_to:
                filter_parts.append(f"publication_year:1900-{year_to}")
                if callback:
                    callback(f"📅 Year filter: ≤{year_to}")

            # ── Repository filter ────────────────────────────────
            repo = getattr(self.config, "repository", "")
            search_query = query

            if repo == "doaj":
                filter_parts.append("primary_location.source.is_in_doaj:true")
                if callback:
                    callback("📋 Repository: DOAJ (Open Access journals)")
            elif repo == "scopus":
                # OpenAlex doesn't have direct Scopus filter,
                # but we filter to journal-type sources and add keyword
                filter_parts.append("primary_location.source.type:journal")
                search_query = f"{query} Scopus indexed"
                if callback:
                    callback("📋 Repository: Scopus-indexed journals")
            elif repo == "sinta":
                # SINTA = Indonesian journal index
                search_query = f"{query} SINTA terakreditasi"
                if callback:
                    callback("📋 Repository: SINTA (Indonesia)")
            elif repo == "wos":
                filter_parts.append("primary_location.source.type:journal")
                search_query = f"{query} Web of Science"
                if callback:
                    callback("📋 Repository: Web of Science")
            elif repo == "journal_only":
                filter_parts.append("primary_location.source.type:journal")
                if callback:
                    callback("📋 Filter: Journal articles only")

            # Build API params
            params = {
                "search": search_query,
                "filter": ",".join(filter_parts),
                "sort": "relevance_score:desc",
                "per_page": min(max_results * 2, 50),
                "mailto": _MAILTO,
            }

            # Add language filter if Indonesian
            if lang == "id":
                # Don't filter by language for ID since many Indonesian
                # papers are classified as English in metadata
                pass

            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.config.page_load_timeout,
            )
            response.raise_for_status()

            data = response.json()
            works = data.get("results", [])
            total_count = data.get("meta", {}).get("count", 0)

            if callback:
                callback(f"OpenAlex returned {total_count} total matches, processing top {len(works)}...")

            results = []

            for work in works:
                if len(results) >= max_results:
                    break

                title = work.get("title", "")
                if not title:
                    continue

                # Get PDF URL
                pdf_url = self._extract_pdf_url(work)
                if not pdf_url:
                    continue  # Skip if no downloadable PDF

                # Extract metadata
                authors = self._extract_authors(work.get("authorships", []))
                year = self._extract_year(work)
                abstract = self._extract_abstract(work)

                # Get source journal/venue
                primary_loc = work.get("primary_location") or {}
                source_info = primary_loc.get("source") or {}
                venue = source_info.get("display_name", "")

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
                    venue_tag = f" [{venue[:30]}]" if venue else ""
                    year_tag = f" ({year})" if year else ""
                    callback(
                        f"  📄 {title[:50]}...{year_tag}{venue_tag}"
                    )

            # ── Page 2 if needed ─────────────────────────────────
            if len(results) < max_results and total_count > len(works):
                if callback:
                    callback("Fetching more results (page 2)...")

                params["page"] = 2
                try:
                    resp2 = self.session.get(
                        self.BASE_URL,
                        params=params,
                        timeout=self.config.page_load_timeout,
                    )
                    if resp2.ok:
                        works2 = resp2.json().get("results", [])
                        for work in works2:
                            if len(results) >= max_results:
                                break
                            title = work.get("title", "")
                            pdf_url = self._extract_pdf_url(work)
                            if not title or not pdf_url:
                                continue
                            authors = self._extract_authors(work.get("authorships", []))
                            year = self._extract_year(work)
                            abstract = self._extract_abstract(work)
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
                                callback(f"  📄 {title[:50]}... ({year})")
                except Exception:
                    pass

            if callback:
                emoji = "✅" if results else "⚠️"
                callback(f"{emoji} OpenAlex found {len(results)} downloadable PDF(s)")

            return results

        except requests.exceptions.HTTPError as e:
            logger.error(f"OpenAlex HTTP error: {e}")
            if callback:
                callback(f"❌ HTTP Error: {e}")
            return []
        except Exception as e:
            logger.error(f"OpenAlex error: {e}")
            if callback:
                callback(f"❌ Error: {str(e)}")
            return []

    # ── Interface ────────────────────────────────────────────────
    def needs_browser(self) -> bool:
        return False

    def close(self):
        self.session.close()
