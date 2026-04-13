# scrapers package
# Modular scraper system for academic journal PDF downloading.
# Each target site has its own scraper class that inherits from BaseScraper.

from .arxiv_scraper import ArxivScraper
from .semantic_scholar_scraper import SemanticScholarScraper
from .google_scholar_scraper import GoogleScholarScraper
from .pubmed_scraper import PubMedScraper
from .garuda_scraper import GarudaScraper
from .google_search_scraper import GoogleSearchScraper
from .duckduckgo_scraper import DuckDuckGoScraper
from .openalex_scraper import OpenAlexScraper
from .crossref_scraper import CrossRefScraper

__all__ = [
    "ArxivScraper",
    "SemanticScholarScraper",
    "GoogleScholarScraper",
    "PubMedScraper",
    "GarudaScraper",
    "GoogleSearchScraper",
    "DuckDuckGoScraper",
    "OpenAlexScraper",
    "CrossRefScraper",
]
