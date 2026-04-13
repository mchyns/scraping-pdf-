"""
arxiv_scraper.py — arXiv.org scraper implementation.

Uses Selenium with undetected-chromedriver for browser automation,
and BeautifulSoup for fast DOM parsing of search results. arXiv is 
open-access, so every paper has a freely available PDF link.

PDF URL Pattern:
    Abstract page: https://arxiv.org/abs/2301.12345
    PDF page:      https://arxiv.org/pdf/2301.12345.pdf
"""

import time
import logging
from typing import List, Optional
from urllib.parse import quote_plus

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, PaperResult, ScraperConfig

logger = logging.getLogger(__name__)


class ArxivScraper(BaseScraper):
    """
    Scraper for arXiv.org — the largest open-access preprint repository.

    Strategy:
        1. Use arXiv's search API/URL to query papers.
        2. Parse the results page with BeautifulSoup for speed.
        3. Extract PDF URLs by converting /abs/ links to /pdf/ links.
        4. Paginate if needed to collect enough results.
    """

    BASE_URL = "https://arxiv.org"
    SEARCH_URL = "https://arxiv.org/search/"
    RESULTS_PER_PAGE = 25  # arXiv default

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self._driver = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "arXiv"

    # ── Public API ───────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[PaperResult]:
        """
        Search arXiv for papers matching the query.

        Args:
            query: Search topic or title keywords.
            max_results: Maximum number of PaperResults to return.

        Returns:
            List of PaperResult with title, pdf_url, authors, etc.
        """
        results: List[PaperResult] = []
        start = 0

        logger.info(f"[arXiv] Searching for: '{query}' (max {max_results} results)")

        # Initialize the browser
        self._init_driver()

        while len(results) < max_results:
            url = self._build_search_url(query, start=start)
            logger.info(f"[arXiv] Fetching page: {url}")

            try:
                self._driver.get(url)

                # Wait for results to load
                WebDriverWait(self._driver, self.config.page_load_timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )

                # Small delay to let dynamic content settle
                time.sleep(self.config.request_delay)

                # Parse the page with BeautifulSoup for speed
                page_source = self._driver.page_source
                page_results = self._parse_results_page(page_source)

                if not page_results:
                    logger.warning("[arXiv] No results found on this page. Stopping.")
                    break

                results.extend(page_results)
                logger.info(
                    f"[arXiv] Collected {len(results)} results so far "
                    f"(this page: {len(page_results)})"
                )

                # Check if we've reached the last page
                if len(page_results) < self.RESULTS_PER_PAGE:
                    logger.info("[arXiv] Reached last page of results.")
                    break

                # Move to next page
                start += self.RESULTS_PER_PAGE

                # Polite delay between page fetches
                time.sleep(self.config.request_delay)

            except TimeoutException:
                logger.error("[arXiv] Page load timed out.")
                break
            except WebDriverException as e:
                logger.error(f"[arXiv] WebDriver error: {e}")
                break

        # Trim to the requested max
        return results[:max_results]

    def close(self):
        """Quit the browser and release resources."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception as e:
                logger.warning(f"[arXiv] Error closing driver: {e}")
            finally:
                self._driver = None

    # ── Private Methods ──────────────────────────────────────────────

    def _init_driver(self):
        """Initialize undetected Chrome in headless mode."""
        if self._driver is not None:
            return

        logger.info("[arXiv] Initializing undetected Chrome browser...")

        options = uc.ChromeOptions()

        if self.config.headless:
            options.add_argument("--headless=new")

        # Stability & stealth options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            self._driver = uc.Chrome(options=options)
            self._driver.set_page_load_timeout(self.config.page_load_timeout)
            logger.info("[arXiv] Browser initialized successfully.")
        except Exception as e:
            logger.error(f"[arXiv] Failed to initialize browser: {e}")
            raise RuntimeError(
                "Failed to initialize Chrome browser. "
                "Make sure Google Chrome is installed.\n"
                f"Error: {e}"
            )

    def _build_search_url(self, query: str, start: int = 0) -> str:
        """
        Build an arXiv search URL.

        Args:
            query: The search query string.
            start: Pagination offset (0-indexed).

        Returns:
            Fully-formed arXiv search URL.
        """
        encoded_query = quote_plus(query)
        url = (
            f"{self.SEARCH_URL}?query={encoded_query}"
            f"&searchtype=all"
            f"&start={start}"
        )
        return url

    def _parse_results_page(self, html: str) -> List[PaperResult]:
        """
        Parse an arXiv search results page using BeautifulSoup.

        arXiv search results structure (as of 2024):
            <li class="arxiv-result">
                <p class="title is-5 mathjax">Paper Title</p>
                <p class="authors">Author1, Author2</p>
                <p class="abstract mathjax">...</p>
                <p class="list-title">
                    <a href="https://arxiv.org/abs/2301.12345">arXiv:2301.12345</a>
                </p>
            </li>

        Returns:
            List of PaperResult objects parsed from the page.
        """
        soup = BeautifulSoup(html, "lxml")
        results: List[PaperResult] = []

        # Find all result entries
        result_items = soup.find_all("li", class_="arxiv-result")

        if not result_items:
            # Check if there's a "no results" message
            no_results = soup.find("p", class_="is-size-5")
            if no_results and "Sorry" in no_results.get_text():
                logger.info("[arXiv] Search returned no results.")
            return results

        for item in result_items:
            try:
                paper = self._parse_single_result(item)
                if paper:
                    results.append(paper)
            except Exception as e:
                logger.warning(f"[arXiv] Error parsing a result: {e}")
                continue

        return results

    def _parse_single_result(self, item) -> Optional[PaperResult]:
        """
        Parse a single <li class="arxiv-result"> element into a PaperResult.

        Args:
            item: A BeautifulSoup Tag for one search result.

        Returns:
            PaperResult if successfully parsed, None otherwise.
        """
        # ── Title ────────────────────────────────────────────────────
        title_tag = item.find("p", class_="title")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)

        # ── Authors ──────────────────────────────────────────────────
        authors_tag = item.find("p", class_="authors")
        authors = ""
        if authors_tag:
            # Remove the "Authors:" label
            authors_text = authors_tag.get_text(strip=True)
            authors = authors_text.replace("Authors:", "").strip()

        # ── Abstract URL & PDF URL ───────────────────────────────────
        # Find the arXiv ID link (e.g., arxiv.org/abs/2301.12345)
        pdf_url = None
        abstract_url = None

        # Look for the abstract link
        list_title = item.find("p", class_="list-title")
        if list_title:
            abs_link = list_title.find("a", href=True)
            if abs_link:
                abstract_url = abs_link["href"]
                # Convert abstract URL to PDF URL
                # https://arxiv.org/abs/2301.12345 → https://arxiv.org/pdf/2301.12345.pdf
                if "/abs/" in abstract_url:
                    pdf_url = abstract_url.replace("/abs/", "/pdf/") + ".pdf"

        # Fallback: look for any PDF link in the item
        if not pdf_url:
            all_links = item.find_all("a", href=True)
            for link in all_links:
                href = link["href"]
                if "/pdf/" in href:
                    pdf_url = href
                    if not pdf_url.startswith("http"):
                        pdf_url = f"{self.BASE_URL}{pdf_url}"
                    break

        # ── Submitted Date / Year ────────────────────────────────────
        year = ""
        submitted_tag = item.find("p", class_="is-size-7")
        if submitted_tag:
            text = submitted_tag.get_text()
            # Try to extract year from "Submitted 15 January, 2024"
            import re
            year_match = re.search(r"(\d{4})", text)
            if year_match:
                year = year_match.group(1)

        return PaperResult(
            title=title,
            pdf_url=pdf_url,
            abstract_url=abstract_url,
            authors=authors,
            year=year,
            source="arXiv",
        )
