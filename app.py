"""
app.py — Streamlit Web UI for Academic Journal PDF Scraper.

A premium, modern interface for searching and downloading academic
papers from multiple sources: arXiv, Google Scholar, Semantic Scholar,
and PubMed. Features live terminal-style logging, multi-source scraping,
and real-time progress tracking.

Run with:
    streamlit run app.py
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Tuple

import streamlit as st

# ── Ensure project root is in sys.path ───────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scrapers import (
    ArxivScraper,
    SemanticScholarScraper,
    GoogleScholarScraper,
    PubMedScraper,
    GarudaScraper,
    GoogleSearchScraper,
    DuckDuckGoScraper,
    OpenAlexScraper,
    CrossRefScraper,
)
from scrapers.base_scraper import ScraperConfig, PaperResult
from utils import (
    sanitize_filename,
    ensure_download_dir,
    download_pdf,
    create_zip_archive,
    format_file_size,
)

# ── Logging Configuration ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
#  PAGE CONFIG & CUSTOM STYLING
# ═════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ScholarScrape — Multi-Source PDF Downloader",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_custom_css():
    """Inject custom CSS for a premium, modern look."""
    st.markdown(
        """
        <style>
        /* ── Google Font ─────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        /* ── Root Variables ──────────────────────────────────────── */
        :root {
            --primary: #6C63FF;
            --primary-light: #8B83FF;
            --primary-dark: #4F46E5;
            --accent: #06D6A0;
            --accent-dark: #05B384;
            --cyan: #22D3EE;
            --orange: #F97316;
            --pink: #EC4899;
            --bg-dark: #0F0F1A;
            --bg-card: #1A1A2E;
            --bg-card-hover: #222240;
            --bg-terminal: #0D1117;
            --text-primary: #F0F0F5;
            --text-secondary: #9CA3AF;
            --text-terminal: #C9D1D9;
            --border: #2D2D44;
            --success: #10B981;
            --warning: #F59E0B;
            --error: #EF4444;
            --gradient-1: linear-gradient(135deg, #6C63FF 0%, #06D6A0 100%);
            --gradient-2: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #EC4899 100%);
            --gradient-3: linear-gradient(135deg, #06D6A0 0%, #22D3EE 100%);
            --shadow-glow: 0 0 30px rgba(108, 99, 255, 0.15);
        }

        /* ── Global Overrides ────────────────────────────────────── */
        .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* ── Hero Header ─────────────────────────────────────────── */
        .hero-header {
            text-align: center;
            padding: 2rem 1rem 1rem;
            margin-bottom: 0.5rem;
        }
        .hero-header h1 {
            font-size: 2.8rem;
            font-weight: 800;
            background: var(--gradient-1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.3rem;
            letter-spacing: -0.02em;
        }
        .hero-header .subtitle {
            font-size: 1.05rem;
            color: var(--text-secondary);
            font-weight: 400;
        }

        /* ── Source Badges ────────────────────────────────────────── */
        .source-badges {
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            margin-top: 0.8rem;
            flex-wrap: wrap;
        }
        .source-badge {
            padding: 0.25rem 0.8rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.03em;
            transition: all 0.3s ease;
        }
        .source-badge:hover {
            transform: scale(1.05);
        }
        .badge-arxiv {
            background: rgba(108, 99, 255, 0.15);
            border: 1px solid rgba(108, 99, 255, 0.3);
            color: var(--primary-light);
        }
        .badge-scholar {
            background: rgba(249, 115, 22, 0.15);
            border: 1px solid rgba(249, 115, 22, 0.3);
            color: var(--orange);
        }
        .badge-semantic {
            background: rgba(6, 214, 160, 0.15);
            border: 1px solid rgba(6, 214, 160, 0.3);
            color: var(--accent);
        }
        .badge-pubmed {
            background: rgba(34, 211, 238, 0.15);
            border: 1px solid rgba(34, 211, 238, 0.3);
            color: var(--cyan);
        }
        .badge-garuda {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #EF4444;
        }
        .badge-gsearch {
            background: rgba(66, 133, 244, 0.15);
            border: 1px solid rgba(66, 133, 244, 0.3);
            color: #4285F4;
        }
        .badge-ddg {
            background: rgba(222, 94, 38, 0.15);
            border: 1px solid rgba(222, 94, 38, 0.3);
            color: #DE5E26;
        }
        .badge-openalex {
            background: rgba(232, 121, 35, 0.15);
            border: 1px solid rgba(232, 121, 35, 0.3);
            color: #E87923;
        }
        .badge-crossref {
            background: rgba(35, 130, 196, 0.15);
            border: 1px solid rgba(35, 130, 196, 0.3);
            color: #2382C4;
        }
        .badge-active {
            box-shadow: 0 0 12px currentColor;
        }

        /* ── Stat Cards ──────────────────────────────────────────── */
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.2rem 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        .stat-card:hover {
            border-color: var(--primary);
            box-shadow: var(--shadow-glow);
            transform: translateY(-2px);
        }
        .stat-card .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary-light);
        }
        .stat-card .stat-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 0.3rem;
        }

        /* ── Result Paper Card ───────────────────────────────────── */
        .paper-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.3rem 1.5rem;
            margin-bottom: 0.8rem;
            transition: all 0.3s ease;
        }
        .paper-card:hover {
            border-color: var(--accent);
            box-shadow: 0 0 20px rgba(6, 214, 160, 0.1);
        }
        .paper-card .paper-title {
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.4rem;
            line-height: 1.4;
        }
        .paper-card .paper-meta {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.3rem;
        }
        .paper-card .paper-status {
            display: inline-block;
            padding: 0.2rem 0.7rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .status-success {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .status-skipped {
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .status-error {
            background: rgba(239, 68, 68, 0.15);
            color: var(--error);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .status-searching {
            background: rgba(108, 99, 255, 0.15);
            color: var(--primary-light);
            border: 1px solid rgba(108, 99, 255, 0.3);
        }

        /* ── Live Terminal / Log ─────────────────────────────────── */
        .live-terminal {
            background: var(--bg-terminal);
            border: 1px solid #30363D;
            border-radius: 12px;
            padding: 0;
            margin: 1rem 0;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        .terminal-header {
            background: #161B22;
            padding: 0.6rem 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border-bottom: 1px solid #30363D;
        }
        .terminal-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .terminal-dot.red { background: #FF5F56; }
        .terminal-dot.yellow { background: #FFBD2E; }
        .terminal-dot.green { background: #27C93F; }
        .terminal-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #8B949E;
            margin-left: 0.5rem;
        }
        .terminal-body {
            padding: 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.6;
            color: var(--text-terminal);
            max-height: 400px;
            overflow-y: auto;
        }
        .terminal-body .log-time {
            color: #6E7681;
        }
        .terminal-body .log-info {
            color: #58A6FF;
        }
        .terminal-body .log-success {
            color: #3FB950;
        }
        .terminal-body .log-warning {
            color: #D29922;
        }
        .terminal-body .log-error {
            color: #F85149;
        }
        .terminal-body .log-source {
            color: #BC8CFF;
            font-weight: 500;
        }
        .terminal-body .log-url {
            color: #8B949E;
            text-decoration: underline;
        }

        /* ── Progress Section ────────────────────────────────────── */
        .progress-header {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 1.5rem 0 0.8rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* ── Download Button Styling ─────────────────────────────── */
        .stDownloadButton > button {
            background: var(--gradient-1) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 0.7rem 2rem !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            transition: all 0.3s ease !important;
            width: 100%;
        }
        .stDownloadButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(108, 99, 255, 0.3) !important;
        }

        /* ── Sidebar Styling ─────────────────────────────────────── */
        section[data-testid="stSidebar"] {
            background: var(--bg-dark);
            border-right: 1px solid var(--border);
        }
        .sidebar-header {
            text-align: center;
            padding: 0.5rem 0 1rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 1.5rem;
        }
        .sidebar-header h2 {
            font-size: 1.3rem;
            font-weight: 700;
            background: var(--gradient-1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .sidebar-header p {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        /* ── Divider ─────────────────────────────────────────────── */
        .custom-divider {
            height: 1px;
            background: var(--gradient-1);
            opacity: 0.3;
            margin: 1.5rem 0;
            border: none;
        }

        /* ── Animation Keyframes ─────────────────────────────────── */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-in {
            animation: fadeInUp 0.5s ease-out forwards;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .pulse {
            animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        .cursor-blink::after {
            content: '█';
            animation: blink 1s step-end infinite;
            color: var(--accent);
        }

        /* ── Info Box ────────────────────────────────────────────── */
        .info-box {
            background: rgba(108, 99, 255, 0.08);
            border: 1px solid rgba(108, 99, 255, 0.2);
            border-radius: 12px;
            padding: 1rem 1.3rem;
            margin: 1rem 0;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        .info-box strong {
            color: var(--primary-light);
        }

        /* ── Source Selection Chips ───────────────────────────────── */
        .source-chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.5rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════
#  SESSION STATE INITIALIZATION
# ═════════════════════════════════════════════════════════════════════

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "search_results": [],
        "downloaded_files": [],
        "download_log": [],
        "live_log_lines": [],
        "is_scraping": False,
        "scraping_complete": False,
        "total_found": 0,
        "total_downloaded": 0,
        "total_skipped": 0,
        "sources_searched": [],
        "zip_data": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ═════════════════════════════════════════════════════════════════════
#  AVAILABLE SCRAPERS REGISTRY
# ═════════════════════════════════════════════════════════════════════

AVAILABLE_SCRAPERS = [
    {
        "name": "🔬 OpenAlex",
        "class": OpenAlexScraper,
        "icon": "🔬",
        "badge_class": "badge-openalex",
        "description": "250M+ works — API gratis, tanpa CAPTCHA! ⭐",
        "needs_browser": False,
    },
    {
        "name": "📚 CrossRef",
        "class": CrossRefScraper,
        "icon": "📚",
        "badge_class": "badge-crossref",
        "description": "150M+ DOIs — full-text PDF links",
        "needs_browser": False,
    },
    {
        "name": "🌐 Google Search",
        "class": GoogleSearchScraper,
        "icon": "🌐",
        "badge_class": "badge-gsearch",
        "description": "Cari PDF dari seluruh internet (mungkin CAPTCHA)",
        "needs_browser": False,
    },
    {
        "name": "🦆 DuckDuckGo",
        "class": DuckDuckGoScraper,
        "icon": "🦆",
        "badge_class": "badge-ddg",
        "description": "Cari dari internet tanpa CAPTCHA",
        "needs_browser": False,
    },
    {
        "name": "arXiv",
        "class": ArxivScraper,
        "icon": "📄",
        "badge_class": "badge-arxiv",
        "description": "Open-access preprints — CS, Physics, Math",
        "needs_browser": True,
    },
    {
        "name": "Google Scholar",
        "class": GoogleScholarScraper,
        "icon": "🎓",
        "badge_class": "badge-scholar",
        "description": "Academic search (sering ke-block bot)",
        "needs_browser": False,
    },
    {
        "name": "Semantic Scholar",
        "class": SemanticScholarScraper,
        "icon": "🧠",
        "badge_class": "badge-semantic",
        "description": "AI-powered search — 200M+ papers",
        "needs_browser": False,
    },
    {
        "name": "PubMed",
        "class": PubMedScraper,
        "icon": "🧬",
        "badge_class": "badge-pubmed",
        "description": "Biomedical & life sciences literature",
        "needs_browser": False,
    },
    {
        "name": "Garuda",
        "class": GarudaScraper,
        "icon": "🇮🇩",
        "badge_class": "badge-garuda",
        "description": "Jurnal ilmiah Indonesia — Kemdikbud",
        "needs_browser": False,
    },
]


# ═════════════════════════════════════════════════════════════════════
#  LIVE TERMINAL LOG HELPER
# ═════════════════════════════════════════════════════════════════════

def _log_line(
    log_lines: list,
    message: str,
    level: str = "info",
    source: str = "",
) -> str:
    """
    Add a timestamped log line and return the full terminal HTML.

    Args:
        log_lines: List to append log entries to.
        message: The log message text.
        level: One of 'info', 'success', 'warning', 'error'.
        source: Source name for colored prefix.

    Returns:
        Full HTML string for the terminal body.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    source_html = (
        f'<span class="log-source">[{source}]</span> '
        if source else ""
    )
    log_lines.append(
        f'<span class="log-time">{timestamp}</span> '
        f'<span class="log-{level}">{"►" if level == "info" else "✓" if level == "success" else "⚠" if level == "warning" else "✗"}</span> '
        f"{source_html}{message}"
    )
    return "\n".join(log_lines)


def _render_terminal(terminal_placeholder, log_lines: list, title: str = "Live Log"):
    """Render the terminal with current log lines."""
    body_html = "<br>".join(log_lines[-50:])  # Keep last 50 lines
    terminal_placeholder.markdown(
        f"""
        <div class="live-terminal">
            <div class="terminal-header">
                <span class="terminal-dot red"></span>
                <span class="terminal-dot yellow"></span>
                <span class="terminal-dot green"></span>
                <span class="terminal-title">{title}</span>
            </div>
            <div class="terminal-body">
                {body_html}
                <span class="cursor-blink"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════
#  CORE: MULTI-SOURCE SCRAPING & DOWNLOAD PIPELINE
# ═════════════════════════════════════════════════════════════════════

def run_multi_source_pipeline(
    query: str,
    num_papers: int,
    selected_sources: list,
    config: ScraperConfig,
    status_placeholder,
    progress_bar,
    terminal_placeholder,
    results_container,
):
    """
    Execute scraping across MULTIPLE sources and download PDFs.

    The pipeline:
        1. For each selected source, search for papers.
        2. Merge and deduplicate results across sources.
        3. Download PDFs one by one with live progress.
        4. Generate ZIP archive.
    """
    download_dir = ensure_download_dir(config.download_dir)
    downloaded_files = []
    download_log = []
    all_results = []
    log_lines = []
    skipped = 0
    sources_searched = []

    total_sources = len(selected_sources)

    # ═══════════════════════════════════════════════════════════════
    #  PHASE 1: SEARCH ACROSS ALL SOURCES
    # ═══════════════════════════════════════════════════════════════

    _log_line(log_lines, f"Starting multi-source search for: <b>\"{query}\"</b>", "info")
    _log_line(log_lines, f"Target: {num_papers} PDFs from {total_sources} source(s)", "info")

    # Show active filters
    if config.year_from or config.year_to:
        if config.year_from and config.year_to:
            _log_line(log_lines, f"📅 Year filter: {config.year_from}–{config.year_to}", "info")
        elif config.year_from:
            _log_line(log_lines, f"📅 Year filter: {config.year_from}+", "info")
        else:
            _log_line(log_lines, f"📅 Year filter: ≤{config.year_to}", "info")
    if config.repository:
        _log_line(log_lines, f"📋 Repository: {config.repository.upper()}", "info")

    _log_line(log_lines, "─" * 50, "info")
    _render_terminal(terminal_placeholder, log_lines, "Scholar Scrape — Live Log")

    status_placeholder.markdown(
        '<div class="progress-header">'
        '🔍 <span class="pulse">Searching across multiple sources...</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    for idx, source_entry in enumerate(selected_sources):
        source_name = source_entry["name"]
        scraper_class = source_entry["class"]
        source_icon = source_entry["icon"]

        _log_line(
            log_lines,
            f"Initializing {source_icon} <b>{source_name}</b> scraper...",
            "info",
            source_name,
        )
        _render_terminal(terminal_placeholder, log_lines)

        status_placeholder.markdown(
            f'<div class="progress-header">'
            f'🔍 <span class="pulse">Searching {source_icon} {source_name} '
            f'({idx+1}/{total_sources})...</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        try:
            # Calculate how many to request from each source
            per_source_limit = max(
                num_papers,
                (num_papers * 2) // total_sources + 10
            )

            _log_line(
                log_lines,
                f"Requesting up to {per_source_limit} results...",
                "info",
                source_name,
            )
            _render_terminal(terminal_placeholder, log_lines)

            with scraper_class(config) as scraper:
                if source_entry.get("needs_browser"):
                    _log_line(
                        log_lines,
                        "Launching headless Chrome browser...",
                        "info",
                        source_name,
                    )
                    _render_terminal(terminal_placeholder, log_lines)
                else:
                    _log_line(
                        log_lines,
                        "Using REST API (no browser needed)...",
                        "info",
                        source_name,
                    )
                    _render_terminal(terminal_placeholder, log_lines)

                source_results = scraper.search(query, max_results=per_source_limit)

                pdf_count = sum(1 for r in source_results if r.pdf_url)

                _log_line(
                    log_lines,
                    f"Found <b>{len(source_results)}</b> papers "
                    f"(<b>{pdf_count}</b> with PDF links)",
                    "success",
                    source_name,
                )

                # Log some titles
                for r in source_results[:3]:
                    pdf_indicator = "📎" if r.pdf_url else "📝"
                    short_title = r.title[:65] + "..." if len(r.title) > 65 else r.title
                    _log_line(
                        log_lines,
                        f"  {pdf_indicator} {short_title}",
                        "info" if r.pdf_url else "warning",
                    )
                if len(source_results) > 3:
                    _log_line(
                        log_lines,
                        f"  ... and {len(source_results) - 3} more",
                        "info",
                    )

                all_results.extend(source_results)
                sources_searched.append(source_name)

        except RuntimeError as e:
            _log_line(
                log_lines,
                f"Browser error: {e}",
                "error",
                source_name,
            )
        except Exception as e:
            _log_line(
                log_lines,
                f"Error: {str(e)[:100]}",
                "error",
                source_name,
            )

        _log_line(log_lines, "─" * 50, "info")
        _render_terminal(terminal_placeholder, log_lines)

        # Delay between sources
        if idx < total_sources - 1:
            time.sleep(config.request_delay)

    # ═══════════════════════════════════════════════════════════════
    #  CHECK RESULTS
    # ═══════════════════════════════════════════════════════════════

    if not all_results:
        _log_line(log_lines, "No results found from any source!", "error")
        _render_terminal(terminal_placeholder, log_lines)
        status_placeholder.error(
            "⚠️ No results found for your query across any source. "
            "Try different keywords."
        )
        st.session_state.is_scraping = False
        return

    st.session_state.total_found = len(all_results)

    _log_line(
        log_lines,
        f"<b>Total results from all sources: {len(all_results)}</b>",
        "success",
    )

    # Deduplicate by title (case-insensitive)
    seen_titles = set()
    unique_results = []
    for r in all_results:
        title_key = r.title.lower().strip()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_results.append(r)

    if len(unique_results) < len(all_results):
        dupes_removed = len(all_results) - len(unique_results)
        _log_line(
            log_lines,
            f"Removed {dupes_removed} duplicate(s). "
            f"Unique papers: {len(unique_results)}",
            "info",
        )

    # Prioritize results with PDF URLs
    unique_results.sort(key=lambda r: (r.pdf_url is None, r.title))

    _log_line(log_lines, "", "info")
    _log_line(log_lines, "═" * 50, "info")
    _log_line(log_lines, "<b>PHASE 2: DOWNLOADING PDFs</b>", "info")
    _log_line(log_lines, "═" * 50, "info")
    _render_terminal(terminal_placeholder, log_lines)

    # ═══════════════════════════════════════════════════════════════
    #  PHASE 2: DOWNLOAD PDFs
    # ═══════════════════════════════════════════════════════════════

    status_placeholder.markdown(
        '<div class="progress-header">'
        '⬇️ <span class="pulse">Downloading PDFs...</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    progress_bar.progress(0)

    for i, paper in enumerate(unique_results):
        if len(downloaded_files) >= num_papers:
            break

        current = len(downloaded_files) + 1
        short_title = paper.title[:60] + "..." if len(paper.title) > 60 else paper.title

        status_placeholder.markdown(
            f'<div class="progress-header">'
            f'⬇️ <span class="pulse">[{current}/{num_papers}] '
            f'Downloading: {short_title}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # Skip if no PDF URL
        if not paper.pdf_url:
            _log_line(
                log_lines,
                f"⏭️  <b>SKIP</b> (no PDF link): {short_title}",
                "warning",
                paper.source,
            )
            download_log.append(("skipped", paper.title, "No PDF URL", paper.source, paper.authors, paper.year))
            skipped += 1
            _render_terminal(terminal_placeholder, log_lines)
            continue

        # Build save path
        filename = sanitize_filename(paper.title)
        save_path = os.path.join(download_dir, filename)

        # Skip if already exists
        if os.path.exists(save_path):
            _log_line(
                log_lines,
                f"✓  Already downloaded: {filename}",
                "success",
                paper.source,
            )
            downloaded_files.append((paper.title, save_path, paper.source))
            download_log.append(("success", paper.title, "Already downloaded", paper.source, paper.authors, paper.year))
            progress_bar.progress(len(downloaded_files) / num_papers)
            _render_terminal(terminal_placeholder, log_lines)
            continue

        # Log the download attempt
        _log_line(
            log_lines,
            f"⬇️  Downloading from <span class='log-url'>{paper.pdf_url[:80]}...</span>",
            "info",
            paper.source,
        )
        _render_terminal(terminal_placeholder, log_lines)

        # Download
        success = download_pdf(
            url=paper.pdf_url,
            save_path=save_path,
            max_retries=config.max_retries,
        )

        if success:
            file_size = format_file_size(os.path.getsize(save_path))
            downloaded_files.append((paper.title, save_path, paper.source))
            download_log.append(("success", paper.title, file_size, paper.source, paper.authors, paper.year))
            _log_line(
                log_lines,
                f"✓  <b>SAVED</b> [{file_size}]: {filename}",
                "success",
                paper.source,
            )
            progress_bar.progress(len(downloaded_files) / num_papers)

            # Render card
            _render_paper_card(results_container, paper, "success", file_size)
        else:
            download_log.append(("error", paper.title, "Download failed", paper.source, paper.authors, paper.year))
            skipped += 1
            _log_line(
                log_lines,
                f"✗  <b>FAILED</b>: {short_title}",
                "error",
                paper.source,
            )
            _render_paper_card(results_container, paper, "error", "Download failed")

        _render_terminal(terminal_placeholder, log_lines)

        # Polite delay
        time.sleep(config.request_delay)

    # ═══════════════════════════════════════════════════════════════
    #  PHASE 3: FINALIZE
    # ═══════════════════════════════════════════════════════════════

    _log_line(log_lines, "", "info")
    _log_line(log_lines, "═" * 50, "info")
    _log_line(log_lines, "<b>COMPLETE!</b>", "success")
    _log_line(
        log_lines,
        f"Downloaded: {len(downloaded_files)}/{num_papers} | "
        f"Skipped: {skipped} | "
        f"Sources: {', '.join(sources_searched)}",
        "success",
    )
    _log_line(log_lines, "═" * 50, "info")
    _render_terminal(terminal_placeholder, log_lines)

    # Create ZIP
    if downloaded_files:
        _log_line(log_lines, "Creating ZIP archive...", "info")
        _render_terminal(terminal_placeholder, log_lines)

        file_paths = [fp for _, fp, _ in downloaded_files]
        zip_data = create_zip_archive(file_paths)
        st.session_state.zip_data = zip_data

        _log_line(
            log_lines,
            f"ZIP archive ready ({format_file_size(len(zip_data))})",
            "success",
        )
        _render_terminal(terminal_placeholder, log_lines)

    # Update session state
    st.session_state.downloaded_files = downloaded_files
    st.session_state.download_log = download_log
    st.session_state.live_log_lines = log_lines
    st.session_state.total_downloaded = len(downloaded_files)
    st.session_state.total_skipped = skipped
    st.session_state.sources_searched = sources_searched
    st.session_state.is_scraping = False
    st.session_state.scraping_complete = True

    if downloaded_files:
        progress_bar.progress(1.0)
        status_placeholder.markdown(
            f'<div class="progress-header">'
            f"✅ Download complete! Got **{len(downloaded_files)}/{num_papers}** "
            f"papers from {len(sources_searched)} source(s)."
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        status_placeholder.warning(
            "⚠️ No PDFs were downloaded. All results were either "
            "missing PDF links or failed to download."
        )


def _render_paper_card(container, paper: PaperResult, status: str, detail: str):
    """Render a styled paper result card."""
    status_class = f"status-{status}"
    status_emoji = {"success": "✅", "skipped": "⏭️", "error": "❌"}.get(status, "")

    authors_display = paper.authors[:100] + "..." if len(paper.authors) > 100 else paper.authors

    # Source color
    source_colors = {
        "🔬 OpenAlex": "#E87923",
        "OpenAlex": "#E87923",
        "📚 CrossRef": "#2382C4",
        "CrossRef": "#2382C4",
        "🌐 Google Search": "#4285F4",
        "Google Search": "#4285F4",
        "🦆 DuckDuckGo": "#DE5E26",
        "DuckDuckGo": "#DE5E26",
        "arXiv": "#8B83FF",
        "Google Scholar": "#F97316",
        "Semantic Scholar": "#06D6A0",
        "PubMed": "#22D3EE",
        "Garuda": "#EF4444",
    }
    source_color = source_colors.get(paper.source, "#9CA3AF")

    container.markdown(
        f"""
        <div class="paper-card animate-in">
            <div class="paper-title">{paper.title}</div>
            <div class="paper-meta">👤 {authors_display or 'Unknown authors'}</div>
            <div class="paper-meta">
                📅 {paper.year or 'N/A'} &nbsp;·&nbsp;
                <span style="color: {source_color}; font-weight: 600;">🏛️ {paper.source}</span>
            </div>
            <div style="margin-top: 0.5rem;">
                <span class="paper-status {status_class}">
                    {status_emoji} {status.upper()} — {detail}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═════════════════════════════════════════════════════════════════════

def render_sidebar():
    """Render the sidebar with configuration options."""
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-header">
                <h2>📚 ScholarScrape</h2>
                <p>Multi-Source PDF Downloader</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Language Selection ────────────────────────────────────
        st.markdown("#### 🌍 Language")
        language = st.radio(
            "Search language",
            options=["en", "id"],
            format_func=lambda x: "🇺🇸 English" if x == "en" else "🇮🇩 Bahasa Indonesia",
            index=0,
            horizontal=True,
            help="Filter results by language. Indonesian mode enables Garuda & Google Scholar ID.",
            label_visibility="collapsed",
        )

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        # ── Source Selection (Multi-select) ──────────────────────
        st.markdown("#### 🌐 Sources")
        st.caption("Select one or more academic databases to search")

        # Set smart defaults based on language
        if language == "id":
            default_sources = ["🔬 OpenAlex", "📚 CrossRef", "Garuda"]
        else:
            default_sources = ["🔬 OpenAlex", "📚 CrossRef", "Semantic Scholar"]

        selected_sources = []
        for scraper in AVAILABLE_SCRAPERS:
            icon = scraper["icon"]
            name = scraper["name"]
            desc = scraper["description"]
            browser_tag = " 🌐" if scraper.get("needs_browser") else " ⚡"

            checked = st.checkbox(
                f"{icon} {name}{browser_tag}",
                value=(name in default_sources),
                help=f"{desc}. {'Uses browser' if scraper.get('needs_browser') else 'Uses HTTP/API (fast)'}",
            )
            if checked:
                selected_sources.append(scraper)

        if not selected_sources:
            st.warning("⚠️ Select at least one source!")

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        # ── Advanced Settings ────────────────────────────────────
        st.markdown("#### ⚙️ Advanced Settings")

        headless = st.toggle(
            "Headless Browser",
            value=True,
            help="Run browser scrapers without a visible window.",
        )

        request_delay = st.slider(
            "Request Delay (seconds)",
            min_value=1.0,
            max_value=10.0,
            value=2.0,
            step=0.5,
            help="Time to wait between requests.",
        )

        page_timeout = st.slider(
            "Page Load Timeout (seconds)",
            min_value=10,
            max_value=120,
            value=30,
            step=5,
            help="Max time to wait for a page to load.",
        )

        max_retries = st.slider(
            "Max Download Retries",
            min_value=1,
            max_value=5,
            value=3,
            help="Retry attempts for failed downloads.",
        )

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        # ── Info ─────────────────────────────────────────────────
        st.markdown(
            """
            <div class="info-box">
                <strong>💡 Tips:</strong><br>
                • 🇮🇩 Mode = Auto-selects Garuda + Google Scholar ID<br>
                • 🌐 = Uses browser (slower) | ⚡ = API (fast)<br>
                • Select multiple sources for best coverage<br>
                • Google Scholar now uses stealth HTTP requests<br>
                • PDFs saved in <code>downloads/</code>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="text-align:center; padding-top:1rem; color: var(--text-secondary); font-size: 0.75rem;">
                Made with ❤️ using Streamlit<br>
                v3.0.0 — Multi-Source + Bahasa 🇮🇩
            </div>
            """,
            unsafe_allow_html=True,
        )

    return selected_sources, language, headless, request_delay, page_timeout, max_retries


# ═════════════════════════════════════════════════════════════════════
#  MAIN UI
# ═════════════════════════════════════════════════════════════════════

def main():
    """Main application entry point."""
    inject_custom_css()

    # ── Sidebar ──────────────────────────────────────────────────
    selected_sources, language, headless, request_delay, page_timeout, max_retries = (
        render_sidebar()
    )

    config = ScraperConfig(
        headless=headless,
        request_delay=request_delay,
        page_load_timeout=page_timeout,
        max_retries=max_retries,
        language=language,
    )

    # ── Hero Header ──────────────────────────────────────────────
    source_badges_html = ""
    for s in AVAILABLE_SCRAPERS:
        active = "badge-active" if s in selected_sources else ""
        source_badges_html += (
            f'<span class="source-badge {s["badge_class"]} {active}">'
            f'{s["icon"]} {s["name"]}'
            f"</span>"
        )

    st.markdown(
        f"""
        <div class="hero-header">
            <h1>📚 ScholarScrape</h1>
            <div class="subtitle">
                Search & download academic PDFs from multiple sources
            </div>
            <div class="source-badges">
                {source_badges_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Search Form ──────────────────────────────────────────────

    # Jurusan definition: keywords + topic list per jurusan
    # Format: { display_name: { "en_kw", "id_kw", "topics_en", "topics_id" } }
    JURUSAN_DATA = {
        "— Semua Jurusan —": {
            "en_kw": "", "id_kw": "",
            "topics_en": [],
            "topics_id": [],
        },
        "🖥️ Teknik Informatika": {
            "en_kw": "computer science software engineering informatics",
            "id_kw": "teknik informatika ilmu komputer rekayasa perangkat lunak",
            "topics_en": [
                "Machine Learning & Deep Learning",
                "Artificial Intelligence",
                "Natural Language Processing (NLP)",
                "Computer Vision & Image Processing",
                "Cybersecurity & Network Security",
                "Internet of Things (IoT)",
                "Cloud Computing & Distributed Systems",
                "Software Engineering & Agile Development",
                "Data Mining & Big Data Analytics",
                "Blockchain & Cryptography",
                "Mobile Application Development",
                "Human-Computer Interaction (HCI)",
                "Robotics & Automation",
                "Web Development & Web Services",
                "Database Systems & Information Retrieval",
            ],
            "topics_id": [
                "Machine Learning & Deep Learning",
                "Kecerdasan Buatan (AI)",
                "Pemrosesan Bahasa Alami (NLP)",
                "Computer Vision & Pengolahan Citra",
                "Keamanan Siber & Jaringan",
                "Internet of Things (IoT)",
                "Cloud Computing & Sistem Terdistribusi",
                "Rekayasa Perangkat Lunak",
                "Data Mining & Analitik Big Data",
                "Blockchain & Kriptografi",
                "Pengembangan Aplikasi Mobile",
                "Interaksi Manusia-Komputer",
                "Robotika & Otomasi",
                "Pengembangan Web & Web Service",
                "Sistem Basis Data & Temu Kembali Informasi",
            ],
        },
        "⚡ Teknik Elektro": {
            "en_kw": "electrical engineering electronics power systems",
            "id_kw": "teknik elektro elektronika sistem tenaga listrik",
            "topics_en": [
                "Power Electronics & Converters",
                "Renewable Energy Systems (Solar, Wind)",
                "Control Systems & Automation",
                "Signal Processing & DSP",
                "Embedded Systems & Microcontrollers",
                "Telecommunications & Wireless",
                "VLSI Design & IC Fabrication",
                "Electric Vehicles & Battery Technology",
                "Smart Grid & Energy Management",
                "Antenna Design & RF Engineering",
            ],
            "topics_id": [
                "Elektronika Daya & Konverter",
                "Sistem Energi Terbarukan (Surya, Angin)",
                "Sistem Kendali & Otomasi",
                "Pengolahan Sinyal Digital",
                "Sistem Embedded & Mikrokontroller",
                "Telekomunikasi & Nirkabel",
                "Desain VLSI & Fabrikasi IC",
                "Kendaraan Listrik & Teknologi Baterai",
                "Smart Grid & Manajemen Energi",
                "Desain Antena & RF Engineering",
            ],
        },
        "🏗️ Teknik Sipil": {
            "en_kw": "civil engineering structural construction",
            "id_kw": "teknik sipil struktur bangunan konstruksi",
            "topics_en": [
                "Structural Analysis & Design",
                "Geotechnical Engineering",
                "Transportation Engineering",
                "Water Resources & Hydraulics",
                "Construction Management",
                "Earthquake Engineering",
                "Green Building & Sustainability",
                "Concrete Technology",
                "Bridge Engineering",
                "Urban Planning & Infrastructure",
            ],
            "topics_id": [
                "Analisis & Desain Struktur",
                "Teknik Geoteknik & Pondasi",
                "Teknik Transportasi & Lalu Lintas",
                "Sumber Daya Air & Hidraulika",
                "Manajemen Konstruksi",
                "Teknik Gempa & Mitigasi Bencana",
                "Bangunan Hijau & Keberlanjutan",
                "Teknologi Beton",
                "Teknik Jembatan",
                "Perencanaan Kota & Infrastruktur",
            ],
        },
        "🔧 Teknik Mesin": {
            "en_kw": "mechanical engineering thermodynamics manufacturing",
            "id_kw": "teknik mesin termodinamika manufaktur",
            "topics_en": [
                "Thermodynamics & Heat Transfer",
                "Fluid Mechanics & CFD",
                "Manufacturing & CNC Machining",
                "Material Science & Metallurgy",
                "Automotive Engineering",
                "Robotics & Mechatronics",
                "CAD/CAM & 3D Printing",
                "Energy Conversion Systems",
                "Vibration & Acoustics",
                "Biomechanics",
            ],
            "topics_id": [
                "Termodinamika & Perpindahan Panas",
                "Mekanika Fluida & CFD",
                "Manufaktur & Pemesinan CNC",
                "Ilmu Material & Metalurgi",
                "Teknik Otomotif",
                "Robotika & Mekatronika",
                "CAD/CAM & 3D Printing",
                "Sistem Konversi Energi",
                "Getaran & Akustik",
                "Biomekanika",
            ],
        },
        "🧪 Teknik Kimia": {
            "en_kw": "chemical engineering process chemistry",
            "id_kw": "teknik kimia proses kimia",
            "topics_en": [
                "Process Engineering & Plant Design",
                "Catalysis & Reaction Engineering",
                "Polymer Science & Engineering",
                "Environmental Engineering",
                "Bioprocess Engineering",
                "Separation Processes",
                "Nanotechnology & Nanomaterials",
                "Food Processing Technology",
                "Corrosion & Surface Engineering",
                "Petroleum & Petrochemical",
            ],
            "topics_id": [
                "Teknik Proses & Perancangan Pabrik",
                "Katalisis & Teknik Reaksi",
                "Ilmu & Teknik Polimer",
                "Teknik Lingkungan",
                "Teknik Bioproses",
                "Proses Pemisahan",
                "Nanoteknologi & Nanomaterial",
                "Teknologi Pengolahan Pangan",
                "Korosi & Teknik Permukaan",
                "Perminyakan & Petrokimia",
            ],
        },
        "🏭 Teknik Industri": {
            "en_kw": "industrial engineering operations management",
            "id_kw": "teknik industri manajemen operasi",
            "topics_en": [
                "Supply Chain Management",
                "Quality Control & Six Sigma",
                "Ergonomics & Work System Design",
                "Operations Research & Optimization",
                "Production Planning & Scheduling",
                "Lean Manufacturing",
                "Project Management",
                "Logistics & Warehousing",
                "Decision Support Systems",
                "Industry 4.0 & Smart Manufacturing",
            ],
            "topics_id": [
                "Manajemen Rantai Pasok",
                "Pengendalian Kualitas & Six Sigma",
                "Ergonomi & Desain Sistem Kerja",
                "Riset Operasi & Optimasi",
                "Perencanaan & Penjadwalan Produksi",
                "Lean Manufacturing",
                "Manajemen Proyek",
                "Logistik & Pergudangan",
                "Sistem Pendukung Keputusan",
                "Industri 4.0 & Smart Manufacturing",
            ],
        },
        "🗣️ Bahasa Inggris / Sastra Inggris": {
            "en_kw": "English linguistics literature TESOL language teaching",
            "id_kw": "bahasa inggris linguistik sastra inggris pengajaran bahasa",
            "topics_en": [
                "TESOL & English Language Teaching",
                "Second Language Acquisition (SLA)",
                "Applied Linguistics",
                "Sociolinguistics & Language Variation",
                "Discourse Analysis",
                "Translation & Interpreting Studies",
                "English Literature & Literary Criticism",
                "Corpus Linguistics",
                "Phonetics & Phonology",
                "Writing & Academic Literacy",
                "Technology-Enhanced Language Learning",
                "Cross-Cultural Communication",
            ],
            "topics_id": [
                "Pengajaran Bahasa Inggris (TESOL/ELT)",
                "Pemerolehan Bahasa Kedua (SLA)",
                "Linguistik Terapan",
                "Sosiolinguistik & Variasi Bahasa",
                "Analisis Wacana",
                "Penerjemahan & Interpretasi",
                "Sastra Inggris & Kritik Sastra",
                "Linguistik Korpus",
                "Fonetik & Fonologi",
                "Menulis & Literasi Akademik",
                "Pembelajaran Bahasa Berbasis Teknologi",
                "Komunikasi Lintas Budaya",
            ],
        },
        "📖 Bahasa Indonesia / Sastra": {
            "en_kw": "Indonesian linguistics literature language",
            "id_kw": "bahasa indonesia linguistik sastra indonesia",
            "topics_en": [
                "Indonesian Language Education",
                "Indonesian Literature & Cultural Studies",
                "Morphology & Syntax of Indonesian",
                "Semantics & Pragmatics",
                "Local Language Preservation",
                "Media & Language Studies",
                "Children's Literature",
                "Folklore & Oral Tradition",
                "Creative Writing Studies",
                "Language Policy & Planning",
            ],
            "topics_id": [
                "Pendidikan Bahasa Indonesia",
                "Sastra Indonesia & Kajian Budaya",
                "Morfologi & Sintaksis Bahasa Indonesia",
                "Semantik & Pragmatik",
                "Pelestarian Bahasa Daerah",
                "Media & Kajian Bahasa",
                "Sastra Anak",
                "Folklor & Tradisi Lisan",
                "Kajian Penulisan Kreatif",
                "Kebijakan & Perencanaan Bahasa",
            ],
        },
        "🇯🇵 Bahasa Jepang": {
            "en_kw": "Japanese language linguistics nihongo",
            "id_kw": "bahasa jepang linguistik nihongo",
            "topics_en": [
                "Japanese Language Education",
                "Japanese Linguistics & Grammar",
                "Japanese Literature & Culture",
                "JLPT & Proficiency Testing",
                "Japanese Translation Studies",
                "Comparative Linguistics (Japanese-Indonesian)",
                "Japanese Pop Culture & Media",
                "Business Japanese",
            ],
            "topics_id": [
                "Pendidikan Bahasa Jepang",
                "Linguistik & Tata Bahasa Jepang",
                "Sastra & Budaya Jepang",
                "JLPT & Uji Kemahiran",
                "Kajian Penerjemahan Bahasa Jepang",
                "Linguistik Komparatif (Jepang-Indonesia)",
                "Budaya Pop & Media Jepang",
                "Bahasa Jepang Bisnis",
            ],
        },
        "📐 Matematika": {
            "en_kw": "mathematics applied math statistics",
            "id_kw": "matematika matematika terapan statistika",
            "topics_en": [
                "Algebra & Number Theory",
                "Calculus & Analysis",
                "Statistics & Probability",
                "Graph Theory & Combinatorics",
                "Numerical Methods & Computation",
                "Mathematical Modeling",
                "Differential Equations",
                "Optimization & Linear Programming",
                "Topology & Geometry",
                "Mathematics Education",
            ],
            "topics_id": [
                "Aljabar & Teori Bilangan",
                "Kalkulus & Analisis",
                "Statistika & Probabilitas",
                "Teori Graf & Kombinatorika",
                "Metode Numerik & Komputasi",
                "Pemodelan Matematika",
                "Persamaan Diferensial",
                "Optimisasi & Pemrograman Linear",
                "Topologi & Geometri",
                "Pendidikan Matematika",
            ],
        },
        "🧬 Biologi": {
            "en_kw": "biology molecular genetics ecology",
            "id_kw": "biologi molekuler genetika ekologi",
            "topics_en": [
                "Molecular Biology & Biotechnology",
                "Genetics & Genomics",
                "Ecology & Conservation",
                "Microbiology & Virology",
                "Cell Biology & Biochemistry",
                "Marine Biology",
                "Biodiversity & Taxonomy",
                "Plant Biology & Botany",
                "Zoology & Animal Behavior",
                "Bioinformatics",
            ],
            "topics_id": [
                "Biologi Molekuler & Bioteknologi",
                "Genetika & Genomika",
                "Ekologi & Konservasi",
                "Mikrobiologi & Virologi",
                "Biologi Sel & Biokimia",
                "Biologi Kelautan",
                "Keanekaragaman Hayati & Taksonomi",
                "Biologi Tumbuhan & Botani",
                "Zoologi & Perilaku Hewan",
                "Bioinformatika",
            ],
        },
        "⚗️ Kimia": {
            "en_kw": "chemistry organic inorganic analytical",
            "id_kw": "kimia organik anorganik analitik",
            "topics_en": [
                "Organic Chemistry & Synthesis",
                "Inorganic & Coordination Chemistry",
                "Analytical Chemistry & Spectroscopy",
                "Physical Chemistry & Thermochemistry",
                "Electrochemistry",
                "Environmental Chemistry",
                "Medicinal Chemistry & Drug Design",
                "Industrial Chemistry",
                "Green Chemistry & Sustainability",
                "Computational Chemistry",
            ],
            "topics_id": [
                "Kimia Organik & Sintesis",
                "Kimia Anorganik & Koordinasi",
                "Kimia Analitik & Spektroskopi",
                "Kimia Fisika & Termokimia",
                "Elektrokimia",
                "Kimia Lingkungan",
                "Kimia Medisinal & Desain Obat",
                "Kimia Industri",
                "Green Chemistry & Keberlanjutan",
                "Kimia Komputasi",
            ],
        },
        "🔭 Fisika": {
            "en_kw": "physics quantum mechanics theoretical",
            "id_kw": "fisika mekanika kuantum fisika teori",
            "topics_en": [
                "Quantum Mechanics & Quantum Computing",
                "Astrophysics & Cosmology",
                "Condensed Matter Physics",
                "Nuclear & Particle Physics",
                "Optics & Photonics",
                "Geophysics & Seismology",
                "Renewable Energy Physics",
                "Computational Physics",
                "Biophysics",
                "Materials Physics",
            ],
            "topics_id": [
                "Mekanika Kuantum & Komputasi Kuantum",
                "Astrofisika & Kosmologi",
                "Fisika Zat Padat",
                "Fisika Nuklir & Partikel",
                "Optika & Fotonika",
                "Geofisika & Seismologi",
                "Fisika Energi Terbarukan",
                "Fisika Komputasi",
                "Biofisika",
                "Fisika Material",
            ],
        },
        "💼 Manajemen": {
            "en_kw": "management business administration marketing",
            "id_kw": "manajemen bisnis administrasi pemasaran",
            "topics_en": [
                "Strategic Management",
                "Digital Marketing & Social Media",
                "Human Resource Management (HRM)",
                "Financial Management & Investment",
                "Entrepreneurship & Startups",
                "Organizational Behavior",
                "Marketing Research & Consumer Behavior",
                "Supply Chain & Operations",
                "Leadership & Change Management",
                "E-Commerce & Digital Business",
            ],
            "topics_id": [
                "Manajemen Strategi",
                "Pemasaran Digital & Media Sosial",
                "Manajemen Sumber Daya Manusia (MSDM)",
                "Manajemen Keuangan & Investasi",
                "Kewirausahaan & Startup",
                "Perilaku Organisasi",
                "Riset Pemasaran & Perilaku Konsumen",
                "Rantai Pasok & Operasi",
                "Kepemimpinan & Manajemen Perubahan",
                "E-Commerce & Bisnis Digital",
            ],
        },
        "📊 Akuntansi": {
            "en_kw": "accounting auditing financial reporting",
            "id_kw": "akuntansi audit laporan keuangan",
            "topics_en": [
                "Financial Accounting & Reporting",
                "Auditing & Assurance",
                "Tax Accounting & Planning",
                "Management Accounting & Cost",
                "Forensic Accounting & Fraud",
                "Public Sector Accounting",
                "International Financial Reporting (IFRS)",
                "Corporate Governance & Ethics",
                "Accounting Information Systems",
                "Sustainability & ESG Reporting",
            ],
            "topics_id": [
                "Akuntansi Keuangan & Pelaporan",
                "Audit & Asurans",
                "Akuntansi Perpajakan",
                "Akuntansi Manajemen & Biaya",
                "Akuntansi Forensik & Kecurangan",
                "Akuntansi Sektor Publik",
                "Pelaporan Keuangan Internasional (IFRS)",
                "Tata Kelola Perusahaan & Etika",
                "Sistem Informasi Akuntansi",
                "Pelaporan Keberlanjutan & ESG",
            ],
        },
        "💰 Ekonomi": {
            "en_kw": "economics microeconomics macroeconomics development",
            "id_kw": "ekonomi mikroekonomi makroekonomi pembangunan",
            "topics_en": [
                "Macroeconomics & Monetary Policy",
                "Microeconomics & Market Theory",
                "Development Economics",
                "International Trade & Economics",
                "Behavioral Economics",
                "Islamic Economics & Finance",
                "Digital Economy & Fintech",
                "Labor Economics & Employment",
                "Public Economics & Fiscal Policy",
                "Environmental & Resource Economics",
            ],
            "topics_id": [
                "Makroekonomi & Kebijakan Moneter",
                "Mikroekonomi & Teori Pasar",
                "Ekonomi Pembangunan",
                "Perdagangan & Ekonomi Internasional",
                "Ekonomi Perilaku",
                "Ekonomi & Keuangan Syariah",
                "Ekonomi Digital & Fintech",
                "Ekonomi Ketenagakerjaan",
                "Ekonomi Publik & Kebijakan Fiskal",
                "Ekonomi Lingkungan & Sumber Daya",
            ],
        },
        "⚖️ Hukum / Ilmu Hukum": {
            "en_kw": "law legal jurisprudence regulation",
            "id_kw": "hukum ilmu hukum peraturan perundang-undangan",
            "topics_en": [
                "Constitutional Law",
                "Criminal Law & Criminology",
                "Civil Law & Contract Law",
                "International Law",
                "Cyber Law & Digital Regulation",
                "Human Rights Law",
                "Environmental Law",
                "Islamic Law (Sharia)",
                "Labor Law & Employment Law",
                "Intellectual Property Law",
            ],
            "topics_id": [
                "Hukum Tata Negara",
                "Hukum Pidana & Kriminologi",
                "Hukum Perdata & Kontrak",
                "Hukum Internasional",
                "Hukum Siber & Regulasi Digital",
                "Hukum Hak Asasi Manusia",
                "Hukum Lingkungan",
                "Hukum Islam (Syariah)",
                "Hukum Ketenagakerjaan",
                "Hukum Kekayaan Intelektual",
            ],
        },
        "🏥 Kedokteran": {
            "en_kw": "medicine clinical medical health",
            "id_kw": "kedokteran klinis medis kesehatan",
            "topics_en": [
                "Internal Medicine",
                "Surgery & Surgical Techniques",
                "Pediatrics & Child Health",
                "Obstetrics & Gynecology",
                "Public Health & Epidemiology",
                "Cardiology & Cardiovascular",
                "Neurology & Neuroscience",
                "Oncology & Cancer Research",
                "Tropical & Infectious Disease",
                "Medical Education",
            ],
            "topics_id": [
                "Ilmu Penyakit Dalam",
                "Bedah & Teknik Operasi",
                "Pediatri & Kesehatan Anak",
                "Obstetri & Ginekologi",
                "Kesehatan Masyarakat & Epidemiologi",
                "Kardiologi & Kardiovaskular",
                "Neurologi & Neurosains",
                "Onkologi & Penelitian Kanker",
                "Penyakit Tropis & Infeksi",
                "Pendidikan Kedokteran",
            ],
        },
        "💊 Farmasi": {
            "en_kw": "pharmacy pharmaceutical drug formulation",
            "id_kw": "farmasi obat formulasi sediaan",
            "topics_en": [
                "Drug Formulation & Delivery",
                "Pharmacology & Toxicology",
                "Pharmaceutical Chemistry",
                "Natural Products & Herbal Medicine",
                "Clinical Pharmacy",
                "Pharmaceutical Biotechnology",
                "Pharmacokinetics & Pharmacodynamics",
                "Quality Control & Standardization",
                "Cosmetic Science",
                "Traditional Medicine & Jamu",
            ],
            "topics_id": [
                "Formulasi & Penghantaran Obat",
                "Farmakologi & Toksikologi",
                "Kimia Farmasi",
                "Bahan Alam & Obat Herbal",
                "Farmasi Klinis",
                "Bioteknologi Farmasi",
                "Farmakokinetik & Farmakodinamik",
                "Pengawasan Mutu & Standarisasi",
                "Ilmu Kosmetik",
                "Obat Tradisional & Jamu",
            ],
        },
        "🦷 Kedokteran Gigi": {
            "en_kw": "dentistry oral health dental",
            "id_kw": "kedokteran gigi kesehatan mulut",
            "topics_en": [
                "Orthodontics & Dental Alignment",
                "Oral Surgery & Implantology",
                "Prosthodontics & Dental Prosthetics",
                "Periodontics & Gum Disease",
                "Pediatric Dentistry",
                "Dental Materials Science",
                "Oral Pathology & Medicine",
                "Preventive & Community Dentistry",
            ],
            "topics_id": [
                "Ortodonti & Perataan Gigi",
                "Bedah Mulut & Implantologi",
                "Prosthodonsia & Gigi Tiruan",
                "Periodonsia & Penyakit Gusi",
                "Kedokteran Gigi Anak",
                "Ilmu Material Kedokteran Gigi",
                "Patologi & Kedokteran Mulut",
                "Kedokteran Gigi Pencegahan & Komunitas",
            ],
        },
        "🩺 Keperawatan": {
            "en_kw": "nursing healthcare patient care",
            "id_kw": "keperawatan kesehatan perawatan pasien",
            "topics_en": [
                "Medical-Surgical Nursing",
                "Community Health Nursing",
                "Pediatric Nursing",
                "Mental Health Nursing",
                "Emergency & Critical Care Nursing",
                "Geriatric Nursing",
                "Nursing Education",
                "Maternity & Women's Health Nursing",
                "Nursing Management & Leadership",
                "Evidence-Based Nursing Practice",
            ],
            "topics_id": [
                "Keperawatan Medikal Bedah",
                "Keperawatan Komunitas",
                "Keperawatan Anak",
                "Keperawatan Jiwa",
                "Keperawatan Gawat Darurat & Kritis",
                "Keperawatan Gerontik",
                "Pendidikan Keperawatan",
                "Keperawatan Maternitas",
                "Manajemen & Kepemimpinan Keperawatan",
                "Praktik Keperawatan Berbasis Bukti",
            ],
        },
        "🏫 Pendidikan": {
            "en_kw": "education pedagogy curriculum learning",
            "id_kw": "pendidikan pedagogik kurikulum pembelajaran",
            "topics_en": [
                "Curriculum Development & Design",
                "E-Learning & Online Education",
                "Educational Psychology",
                "Primary & Elementary Education",
                "Higher Education & University Studies",
                "STEM Education",
                "Inclusive & Special Education",
                "Assessment & Evaluation",
                "Teacher Training & Development",
                "Educational Technology & Innovation",
            ],
            "topics_id": [
                "Pengembangan & Desain Kurikulum",
                "E-Learning & Pembelajaran Daring",
                "Psikologi Pendidikan",
                "Pendidikan Dasar & SD",
                "Pendidikan Tinggi & Perguruan Tinggi",
                "Pendidikan STEM",
                "Pendidikan Inklusif & Luar Biasa",
                "Asesmen & Evaluasi Pembelajaran",
                "Pelatihan & Pengembangan Guru",
                "Teknologi & Inovasi Pendidikan",
            ],
        },
        "🧠 Psikologi": {
            "en_kw": "psychology cognitive behavioral clinical",
            "id_kw": "psikologi kognitif perilaku klinis",
            "topics_en": [
                "Clinical Psychology & Psychotherapy",
                "Developmental Psychology",
                "Social Psychology",
                "Organizational & Industrial Psychology",
                "Educational Psychology",
                "Cognitive Psychology & Neuroscience",
                "Forensic Psychology",
                "Health Psychology & Well-being",
                "Positive Psychology",
                "Child & Adolescent Psychology",
            ],
            "topics_id": [
                "Psikologi Klinis & Psikoterapi",
                "Psikologi Perkembangan",
                "Psikologi Sosial",
                "Psikologi Industri & Organisasi",
                "Psikologi Pendidikan",
                "Psikologi Kognitif & Neurosains",
                "Psikologi Forensik",
                "Psikologi Kesehatan & Kesejahteraan",
                "Psikologi Positif",
                "Psikologi Anak & Remaja",
            ],
        },
        "🌾 Pertanian / Agroteknologi": {
            "en_kw": "agriculture agronomy crop science food",
            "id_kw": "pertanian agroteknologi tanaman pangan",
            "topics_en": [
                "Agronomy & Crop Production",
                "Soil Science & Fertilization",
                "Pest Management & Plant Protection",
                "Horticulture & Plantation",
                "Sustainable Agriculture",
                "Agricultural Biotechnology",
                "Food Science & Post-Harvest",
                "Precision Agriculture & Agri-Tech",
                "Irrigation & Water Management",
                "Organic Farming",
            ],
            "topics_id": [
                "Agronomi & Produksi Tanaman",
                "Ilmu Tanah & Pemupukan",
                "Pengelolaan Hama & Perlindungan Tanaman",
                "Hortikultura & Perkebunan",
                "Pertanian Berkelanjutan",
                "Bioteknologi Pertanian",
                "Ilmu Pangan & Pasca Panen",
                "Pertanian Presisi & Agri-Tech",
                "Irigasi & Pengelolaan Air",
                "Pertanian Organik",
            ],
        },
        "🐄 Peternakan": {
            "en_kw": "animal science livestock husbandry",
            "id_kw": "peternakan ilmu ternak",
            "topics_en": [
                "Animal Nutrition & Feed",
                "Livestock Production & Breeding",
                "Poultry Science",
                "Dairy Science & Milk Processing",
                "Animal Health & Veterinary",
                "Aquaculture & Fish Farming",
                "Animal Genetics & Reproduction",
                "Meat Science & Processing",
            ],
            "topics_id": [
                "Nutrisi Ternak & Pakan",
                "Produksi & Pemuliaan Ternak",
                "Ilmu Unggas",
                "Ilmu Susu & Pengolahan",
                "Kesehatan Hewan & Veteriner",
                "Akuakultur & Budidaya Ikan",
                "Genetika & Reproduksi Ternak",
                "Ilmu & Pengolahan Daging",
            ],
        },
        "🐟 Perikanan / Kelautan": {
            "en_kw": "fisheries marine science oceanography",
            "id_kw": "perikanan kelautan oseanografi",
            "topics_en": [
                "Fisheries Management",
                "Marine Biology & Ecosystem",
                "Aquaculture Technology",
                "Oceanography & Marine Physics",
                "Coastal Zone Management",
                "Fish Processing & Technology",
                "Marine Biodiversity & Conservation",
                "Mariculture & Seaweed Cultivation",
            ],
            "topics_id": [
                "Manajemen Perikanan",
                "Biologi Laut & Ekosistem",
                "Teknologi Akuakultur",
                "Oseanografi & Fisika Kelautan",
                "Pengelolaan Wilayah Pesisir",
                "Pengolahan & Teknologi Ikan",
                "Keanekaragaman Hayati Laut",
                "Marikultur & Budidaya Rumput Laut",
            ],
        },
        "🏛️ Ilmu Politik / HI": {
            "en_kw": "political science international relations diplomacy",
            "id_kw": "ilmu politik hubungan internasional diplomasi",
            "topics_en": [
                "Comparative Politics",
                "International Relations Theory",
                "Public Policy Analysis",
                "Diplomacy & Foreign Policy",
                "Democracy & Elections",
                "Political Communication",
                "Conflict Resolution & Peace Studies",
                "Southeast Asian Politics",
                "Global Governance",
                "Political Economy",
            ],
            "topics_id": [
                "Politik Perbandingan",
                "Teori Hubungan Internasional",
                "Analisis Kebijakan Publik",
                "Diplomasi & Politik Luar Negeri",
                "Demokrasi & Pemilu",
                "Komunikasi Politik",
                "Resolusi Konflik & Studi Perdamaian",
                "Politik Asia Tenggara",
                "Tata Kelola Global",
                "Ekonomi Politik",
            ],
        },
        "👥 Sosiologi": {
            "en_kw": "sociology social research community",
            "id_kw": "sosiologi penelitian sosial masyarakat",
            "topics_en": [
                "Urban Sociology & Urbanization",
                "Gender Studies & Feminism",
                "Social Inequality & Stratification",
                "Sociology of Education",
                "Religion & Society",
                "Digital Society & Social Media",
                "Migration & Diaspora",
                "Community Development",
                "Sociology of Health",
                "Social Movements & Activism",
            ],
            "topics_id": [
                "Sosiologi Perkotaan & Urbanisasi",
                "Studi Gender & Feminisme",
                "Ketimpangan & Stratifikasi Sosial",
                "Sosiologi Pendidikan",
                "Agama & Masyarakat",
                "Masyarakat Digital & Media Sosial",
                "Migrasi & Diaspora",
                "Pengembangan Masyarakat",
                "Sosiologi Kesehatan",
                "Gerakan Sosial & Aktivisme",
            ],
        },
        "📡 Ilmu Komunikasi": {
            "en_kw": "communication media journalism broadcasting",
            "id_kw": "ilmu komunikasi media jurnalistik penyiaran",
            "topics_en": [
                "Mass Communication & Media Studies",
                "Journalism & News Media",
                "Public Relations (PR) & Corporate Comm.",
                "Digital & Social Media Communication",
                "Broadcasting & Film Studies",
                "Advertising & Persuasion",
                "Communication & Health Promotion",
                "Political Communication",
                "Interpersonal Communication",
                "Media Literacy & Education",
            ],
            "topics_id": [
                "Komunikasi Massa & Studi Media",
                "Jurnalistik & Media Berita",
                "Public Relations & Komunikasi Korporat",
                "Komunikasi Digital & Media Sosial",
                "Penyiaran & Studi Film",
                "Periklanan & Persuasi",
                "Komunikasi & Promosi Kesehatan",
                "Komunikasi Politik",
                "Komunikasi Interpersonal",
                "Literasi Media & Pendidikan",
            ],
        },
        "🎨 Desain / DKV": {
            "en_kw": "graphic design visual communication art",
            "id_kw": "desain komunikasi visual seni rupa",
            "topics_en": [
                "Graphic Design & Typography",
                "UI/UX Design & Interaction Design",
                "Branding & Visual Identity",
                "Motion Graphics & Animation",
                "Photography & Visual Storytelling",
                "Illustration & Digital Art",
                "Game Design & Gamification",
                "Package Design & Product Design",
                "Environmental Graphic Design",
                "Design Thinking & Methodology",
            ],
            "topics_id": [
                "Desain Grafis & Tipografi",
                "Desain UI/UX & Interaksi",
                "Branding & Identitas Visual",
                "Motion Graphics & Animasi",
                "Fotografi & Visual Storytelling",
                "Ilustrasi & Seni Digital",
                "Desain Game & Gamifikasi",
                "Desain Kemasan & Produk",
                "Environmental Graphic Design",
                "Design Thinking & Metodologi",
            ],
        },
        "🏛️ Arsitektur": {
            "en_kw": "architecture urban planning building design",
            "id_kw": "arsitektur perencanaan kota desain bangunan",
            "topics_en": [
                "Architectural Design Theory",
                "Sustainable & Green Architecture",
                "Urban Planning & City Design",
                "Interior Design & Space Planning",
                "Building Information Modeling (BIM)",
                "Vernacular & Traditional Architecture",
                "Landscape Architecture",
                "Building Technology & Construction",
                "Heritage Conservation & Restoration",
                "Parametric & Computational Design",
            ],
            "topics_id": [
                "Teori Desain Arsitektur",
                "Arsitektur Berkelanjutan & Hijau",
                "Perencanaan Kota & Desain Kota",
                "Desain Interior & Perencanaan Ruang",
                "Building Information Modeling (BIM)",
                "Arsitektur Vernakular & Tradisional",
                "Arsitektur Lansekap",
                "Teknologi Bangunan & Konstruksi",
                "Konservasi & Restorasi Cagar Budaya",
                "Desain Parametrik & Komputasional",
            ],
        },
    }

    # ── Row 1: Jurusan + Topic ───────────────────────────────────
    col_jurusan, col_topik = st.columns([1, 1])

    with col_jurusan:
        selected_jurusan = st.selectbox(
            "🎓 Jurusan",
            options=list(JURUSAN_DATA.keys()),
            index=0,
            help="Pilih jurusan untuk mempersempit pencarian jurnal sesuai bidang ilmu.",
        )

    # Build topic list based on selected jurusan + language
    jurusan_entry = JURUSAN_DATA[selected_jurusan]
    topic_key = "topics_id" if language == "id" else "topics_en"
    topic_list = jurusan_entry.get(topic_key, [])

    with col_topik:
        if topic_list:
            topic_options = ["— Pilih Topik —"] + topic_list
            selected_topic = st.selectbox(
                "📑 Topik",
                options=topic_options,
                index=0,
                help="Pilih topik spesifik untuk jurusan ini. Wajib jika judul kosong.",
            )
        else:
            selected_topic = "— Pilih Topik —"
            st.selectbox(
                "📑 Topik",
                options=["— Pilih jurusan dulu —"],
                disabled=True,
                help="Pilih jurusan terlebih dahulu untuk melihat daftar topik.",
            )

    # ── Row 1.5: Year Range + Repository ─────────────────────────
    col_year_from, col_year_to, col_repo = st.columns([1, 1, 2])

    current_year = datetime.now().year

    with col_year_from:
        year_from = st.number_input(
            "📅 Tahun Dari",
            min_value=0,
            max_value=current_year,
            value=0,
            step=1,
            help=(
                "Tahun mulai pencarian (0 = tanpa batas). "
                "Contoh: 2021 untuk jurnal dari 2021 ke atas."
            ),
        )

    with col_year_to:
        year_to = st.number_input(
            "📅 Tahun Sampai",
            min_value=0,
            max_value=current_year,
            value=0,
            step=1,
            help=(
                "Tahun akhir pencarian (0 = tanpa batas). "
                "Contoh: 2025 untuk jurnal sampai 2025."
            ),
        )

    REPO_OPTIONS = {
        "— Semua Repositori —": "",
        "🏆 Scopus": "scopus",
        "🇮🇩 SINTA (Indonesia)": "sinta",
        "🔓 DOAJ (Open Access)": "doaj",
        "🌍 Web of Science": "wos",
        "📰 Journal Only": "journal_only",
    }

    with col_repo:
        selected_repo_label = st.selectbox(
            "📋 Repositori / Indeks",
            options=list(REPO_OPTIONS.keys()),
            index=0,
            help=(
                "Filter berdasarkan repositori jurnal. "
                "Scopus = jurnal internasional bereputasi. "
                "SINTA = jurnal Indonesia terakreditasi. "
                "DOAJ = jurnal open access."
            ),
        )
    selected_repo = REPO_OPTIONS[selected_repo_label]

    # Show year hint
    if year_from or year_to:
        if year_from and year_to:
            if year_from == year_to:
                st.caption(f"📅 Mencari jurnal tahun **{year_from}** saja")
            elif year_from > year_to:
                st.warning("⚠️ Tahun Dari harus ≤ Tahun Sampai!")
            else:
                st.caption(f"📅 Mencari jurnal tahun **{year_from}** – **{year_to}**")
        elif year_from:
            st.caption(f"📅 Mencari jurnal dari tahun **{year_from}** ke atas")
        elif year_to:
            st.caption(f"📅 Mencari jurnal sampai tahun **{year_to}**")

    # ── Row 2: Title (optional) + Number + Button ────────────────
    col_input, col_num, col_btn = st.columns([5, 1, 1.5])

    with col_input:
        search_query = st.text_input(
            "🔍 Judul / Kata Kunci (opsional)",
            placeholder=(
                "Optional: add specific keywords or a paper title..."
                if language == "en"
                else "Opsional: tambahkan kata kunci atau judul jurnal spesifik..."
            ),
            help="Boleh kosong jika sudah pilih jurusan + topik di atas.",
        )

    with col_num:
        num_papers = st.number_input(
            "📥 Jumlah",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            help="Jumlah PDF yang ingin didownload (max 50).",
        )

    with col_btn:
        can_search = bool(selected_sources) and not st.session_state.is_scraping
        # Disable if year range is invalid
        if year_from and year_to and year_from > year_to:
            can_search = False
        search_clicked = st.button(
            "🚀 Start",
            use_container_width=True,
            disabled=not can_search,
            type="primary",
        )

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # ── Handle Search Action ─────────────────────────────────────
    if search_clicked:
        has_title = bool(search_query and search_query.strip())
        has_topic = selected_topic != "— Pilih Topik —" and selected_topic != "— Pilih jurusan dulu —"
        has_jurusan = selected_jurusan != "— Semua Jurusan —"

        # Validation: require at least title OR (jurusan + topic)
        if not has_title and not has_topic:
            st.warning(
                "⚠️ Masukkan judul/kata kunci ATAU pilih jurusan + topik dari dropdown!"
            )
            return

        if not selected_sources:
            st.warning("⚠️ Pilih minimal satu sumber di sidebar!")
            return

        # ── Build final query ────────────────────────────────────
        query_parts = []

        # 1. Topic (if selected)
        if has_topic:
            query_parts.append(selected_topic)

        # 2. User-supplied title/keywords (if any)
        if has_title:
            query_parts.append(search_query.strip())

        # 3. Jurusan keywords for relevance
        if has_jurusan:
            kw_key = "id_kw" if language == "id" else "en_kw"
            jurusan_kw = jurusan_entry.get(kw_key, "")
            if jurusan_kw:
                query_parts.append(jurusan_kw)

        final_query = " ".join(query_parts)

        # ── Update config with year/repo filters ─────────────
        config.year_from = year_from if year_from else 0
        config.year_to = year_to if year_to else 0
        config.repository = selected_repo

        # Reset state
        st.session_state.is_scraping = True
        st.session_state.scraping_complete = False
        st.session_state.downloaded_files = []
        st.session_state.download_log = []
        st.session_state.live_log_lines = []
        st.session_state.zip_data = None
        st.session_state.total_found = 0
        st.session_state.total_downloaded = 0
        st.session_state.total_skipped = 0
        st.session_state.sources_searched = []

        # Create progress UI elements
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        terminal_placeholder = st.empty()
        results_container = st.container()

        # Run multi-source pipeline
        run_multi_source_pipeline(
            query=final_query,
            num_papers=num_papers,
            selected_sources=selected_sources,
            config=config,
            status_placeholder=status_placeholder,
            progress_bar=progress_bar,
            terminal_placeholder=terminal_placeholder,
            results_container=results_container,
        )

    # ── Results Dashboard ────────────────────────────────────────
    if st.session_state.scraping_complete:
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        # Stats row
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-value">{st.session_state.total_found}</div>
                    <div class="stat-label">Papers Found</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-value">{st.session_state.total_downloaded}</div>
                    <div class="stat-label">PDFs Downloaded</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c3:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-value">{st.session_state.total_skipped}</div>
                    <div class="stat-label">Skipped / Failed</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c4:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-value">{len(st.session_state.sources_searched)}</div>
                    <div class="stat-label">Sources Used</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("")

        # Download ZIP button
        if st.session_state.zip_data and st.session_state.downloaded_files:
            st.markdown(
                '<div class="progress-header">'
                "📦 Download All Papers as ZIP"
                "</div>",
                unsafe_allow_html=True,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"scholar_scrape_{timestamp}.zip"

            st.download_button(
                label=f"⬇️ Download ZIP ({format_file_size(len(st.session_state.zip_data))})",
                data=st.session_state.zip_data,
                file_name=zip_filename,
                mime="application/zip",
                use_container_width=True,
            )

        # Download log
        if st.session_state.download_log:
            st.markdown(
                '<div class="progress-header">'
                "📋 Download Summary"
                "</div>",
                unsafe_allow_html=True,
            )

            for entry in st.session_state.download_log:
                status, title, detail, source = entry[0], entry[1], entry[2], entry[3]
                authors = entry[4] if len(entry) > 4 else ""
                year = entry[5] if len(entry) > 5 else ""
                _render_paper_card(
                    st,
                    PaperResult(
                        title=title,
                        source=source,
                        authors=authors,
                        year=year,
                    ),
                    status,
                    detail,
                )

        # Show terminal log from session state
        if st.session_state.live_log_lines:
            st.markdown("")
            _render_terminal(st, st.session_state.live_log_lines, "Session Log (Complete)")

    # ── Empty State ──────────────────────────────────────────────
    elif not st.session_state.is_scraping:
        st.markdown("")
        col_empty = st.columns([1, 2, 1])[1]
        with col_empty:
            st.markdown(
                """
                <div style="text-align: center; padding: 3rem 1rem;">
                    <div style="font-size: 4rem; margin-bottom: 1rem;">🔬</div>
                    <h3 style="color: var(--text-secondary); font-weight: 500;">
                        Ready to explore the internet
                    </h3>
                    <p style="color: var(--text-secondary); font-size: 0.9rem; opacity: 0.7;">
                        Select language & sources in the sidebar, enter a search topic,<br>
                        and watch as ScholarScrape hunts across multiple databases<br>
                        to find and download your papers automatically.
                    </p>
                    <div style="margin-top: 1.5rem; display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap;">
                        <span class="source-badge badge-openalex">🔬 OpenAlex</span>
                        <span class="source-badge badge-crossref">📚 CrossRef</span>
                        <span class="source-badge badge-gsearch">🌐 Google</span>
                        <span class="source-badge badge-ddg">🦆 DDG</span>
                        <span class="source-badge badge-arxiv">📄 arXiv</span>
                        <span class="source-badge badge-semantic">🧠 Semantic</span>
                        <span class="source-badge badge-pubmed">🧬 PubMed</span>
                        <span class="source-badge badge-garuda">🇮🇩 Garuda</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ═════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
