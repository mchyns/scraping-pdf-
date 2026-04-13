"""
base_scraper.py — Abstract Base Class for all site-specific scrapers.

This module defines the contract that every scraper must implement.
To add a new target (e.g., PubMed, IEEE), create a new class that
inherits from BaseScraper and implement all abstract methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PaperResult:
    """Represents a single paper found in search results."""
    title: str
    pdf_url: Optional[str] = None
    abstract_url: Optional[str] = None
    authors: str = ""
    year: str = ""
    source: str = ""  # e.g., "arXiv", "PubMed"
    abstract: str = ""  # snippet/description text


@dataclass
class ScraperConfig:
    """Configuration for a scraper instance."""
    headless: bool = True
    request_delay: float = 2.0          # seconds between requests
    page_load_timeout: int = 30         # seconds to wait for page load
    max_retries: int = 3                # retries on transient failures
    download_dir: str = "downloads"     # where to save PDFs
    language: str = "en"                # "en" for English, "id" for Indonesian
    year_from: int = 0                  # start year (0 = no filter)
    year_to: int = 0                    # end year (0 = no filter)
    repository: str = ""                # e.g., "scopus", "sinta", "doaj", "" = all


class BaseScraper(ABC):
    """
    Abstract base class for all journal scrapers.

    Subclasses must implement:
        - name (property): Human-readable name of the target site.
        - search(query, max_results): Search and return PaperResult list.
        - _build_search_url(query): Construct the search URL.
        - close(): Clean up browser/driver resources.
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self._driver = None

    # ── Abstract Interface ───────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the scraper target (e.g., 'arXiv')."""
        ...

    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> List[PaperResult]:
        """
        Search the target site and return a list of PaperResults.

        Args:
            query: The search topic/title.
            max_results: Maximum number of results to collect.

        Returns:
            A list of PaperResult objects (may include entries without pdf_url).
        """
        ...

    @abstractmethod
    def _build_search_url(self, query: str, start: int = 0) -> str:
        """Build the search URL for the given query and pagination offset."""
        ...

    @abstractmethod
    def close(self):
        """Release browser/driver resources."""
        ...

    # ── Context Manager Support ──────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
