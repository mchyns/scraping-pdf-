"""
pubmed_scraper.py — PubMed Central (PMC) scraper implementation.

Uses the NCBI E-utilities API to search PubMed and extract open-access
PDF links from PubMed Central. No browser needed for the search phase.

API Docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/
Rate Limit: 3 requests/second without API key, 10 with key.

PMC open-access papers have direct PDF links.
"""

import time
import logging
import re
from typing import List, Optional
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, PaperResult, ScraperConfig

logger = logging.getLogger(__name__)


class PubMedScraper(BaseScraper):
    """
    Scraper for PubMed / PubMed Central — the largest biomedical
    literature database maintained by the NIH/NLM.

    Strategy:
        1. Use NCBI E-utilities esearch to find PMIDs.
        2. Use efetch to get paper metadata (title, authors, etc.).
        3. Check if PMC full text is available for open-access PDF.
        4. Construct PDF download links from PMC IDs.
    """

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    PMC_PDF_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles"

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "ScholarScrape/1.0 (Academic Research Tool)",
        })

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "PubMed"

    # ── Public API ───────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[PaperResult]:
        """
        Search PubMed for papers and find open-access PDFs.

        Args:
            query: Search topic or title keywords.
            max_results: Maximum number of PaperResults to return.

        Returns:
            List of PaperResult with title, pdf_url, authors, etc.
        """
        logger.info(
            f"[PubMed] Searching for: '{query}' "
            f"(max {max_results} results)"
        )

        # Step 1: Search for PMIDs
        # Request more than needed since not all will have open-access PDFs
        search_limit = min(max_results * 3, 100)
        pmids = self._search_pmids(query, max_results=search_limit)

        if not pmids:
            logger.warning("[PubMed] No results found.")
            return []

        logger.info(f"[PubMed] Found {len(pmids)} PMIDs. Fetching metadata...")

        # Step 2: Fetch metadata in batches
        results: List[PaperResult] = []

        batch_size = 20
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i + batch_size]
            papers = self._fetch_metadata(batch)
            results.extend(papers)

            logger.info(
                f"[PubMed] Fetched metadata: {len(results)} papers so far"
            )

            time.sleep(self.config.request_delay)

        return results[:max_results]

    def close(self):
        """Close the requests session."""
        if self._session:
            self._session.close()

    # ── Private Methods ──────────────────────────────────────────────

    def _build_search_url(self, query: str, start: int = 0) -> str:
        """Build PubMed E-Search URL."""
        return (
            f"{self.ESEARCH_URL}?db=pubmed&term={query}"
            f"&retstart={start}&retmax=50&retmode=json"
        )

    def _search_pmids(self, query: str, max_results: int = 50) -> List[str]:
        """
        Search PubMed and return a list of PMIDs.

        Uses the E-Search API to find papers. We filter for
        open-access papers when possible.
        """
        params = {
            "db": "pubmed",
            "term": f"({query}) AND free full text[filter]",
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }

        try:
            response = self._session.get(
                self.ESEARCH_URL, params=params,
                timeout=self.config.page_load_timeout
            )
            response.raise_for_status()
            data = response.json()

            result = data.get("esearchresult", {})
            pmids = result.get("idlist", [])
            total = result.get("count", "0")

            logger.info(
                f"[PubMed] E-Search returned {len(pmids)} PMIDs "
                f"(total: {total})"
            )
            return pmids

        except Exception as e:
            logger.error(f"[PubMed] E-Search failed: {e}")
            return []

    def _fetch_metadata(self, pmids: List[str]) -> List[PaperResult]:
        """
        Fetch paper metadata for a batch of PMIDs using E-Fetch.

        Returns a list of PaperResult objects.
        """
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }

        try:
            response = self._session.get(
                self.EFETCH_URL, params=params,
                timeout=self.config.page_load_timeout
            )
            response.raise_for_status()

            return self._parse_efetch_xml(response.text)

        except Exception as e:
            logger.error(f"[PubMed] E-Fetch failed: {e}")
            return []

    def _parse_efetch_xml(self, xml_text: str) -> List[PaperResult]:
        """Parse PubMed E-Fetch XML response into PaperResults."""
        results = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.error(f"[PubMed] XML parse error: {e}")
            return results

        for article in root.findall(".//PubmedArticle"):
            try:
                paper = self._parse_article_xml(article)
                if paper:
                    results.append(paper)
            except Exception as e:
                logger.warning(f"[PubMed] Error parsing article: {e}")
                continue

        return results

    def _parse_article_xml(self, article) -> Optional[PaperResult]:
        """Parse a single PubmedArticle XML element."""

        medline = article.find(".//MedlineCitation")
        if medline is None:
            return None

        # ── Title ────────────────────────────────────────────────
        title_elem = medline.find(".//ArticleTitle")
        if title_elem is None or not title_elem.text:
            return None
        title = title_elem.text.strip()

        # ── Authors ──────────────────────────────────────────────
        author_list = medline.findall(".//Author")
        authors_parts = []
        for author in author_list[:5]:
            last = author.findtext("LastName", "")
            first = author.findtext("Initials", "")
            if last:
                authors_parts.append(f"{last} {first}".strip())
        authors = ", ".join(authors_parts)
        if len(author_list) > 5:
            authors += f" et al. (+{len(author_list) - 5})"

        # ── Year ─────────────────────────────────────────────────
        year = ""
        pub_date = medline.find(".//PubDate")
        if pub_date is not None:
            year = pub_date.findtext("Year", "")

        # ── PMID ─────────────────────────────────────────────────
        pmid_elem = medline.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        # ── PMC ID  → PDF URL ────────────────────────────────────
        pdf_url = None
        abstract_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        # Check for PMC ID in article IDs
        article_data = article.find(".//PubmedData")
        if article_data is not None:
            for art_id in article_data.findall(".//ArticleId"):
                id_type = art_id.get("IdType", "")
                if id_type == "pmc" and art_id.text:
                    pmc_id = art_id.text
                    # PMC open-access PDF URL
                    pdf_url = (
                        f"{self.PMC_PDF_BASE}/{pmc_id}/pdf/"
                    )
                    break

        # Fallback: Check DOI for potential open access
        if not pdf_url and article_data is not None:
            for art_id in article_data.findall(".//ArticleId"):
                if art_id.get("IdType") == "doi" and art_id.text:
                    doi = art_id.text
                    # Try Unpaywall / DOI redirect (some DOIs resolve to PDFs)
                    pdf_url = f"https://doi.org/{doi}"
                    break

        return PaperResult(
            title=title,
            pdf_url=pdf_url,
            abstract_url=abstract_url,
            authors=authors,
            year=year,
            source="PubMed",
        )
