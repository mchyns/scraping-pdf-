"""
utils.py — Utility functions for the PDF scraping application.

Provides helpers for:
    - Filename sanitization
    - PDF downloading with streaming
    - ZIP archive creation
    - Directory management
"""

import os
import re
import io
import time
import zipfile
import logging
from typing import List, Tuple, Optional

import requests

logger = logging.getLogger(__name__)

# Maximum filename length (to avoid OS limits)
MAX_FILENAME_LENGTH = 200


def sanitize_filename(title: str) -> str:
    """
    Convert a paper title into a safe, filesystem-friendly filename.

    Steps:
        1. Lowercase the title.
        2. Replace spaces and special chars with underscores.
        3. Collapse multiple underscores.
        4. Truncate to MAX_FILENAME_LENGTH characters.
        5. Append .pdf extension.

    Args:
        title: The raw paper title.

    Returns:
        A sanitized filename string ending in .pdf.

    Examples:
        >>> sanitize_filename("Attention Is All You Need")
        'attention_is_all_you_need.pdf'
        >>> sanitize_filename("A 3D-CNN Model: What's Next?")
        'a_3d_cnn_model_whats_next.pdf'
    """
    # Lowercase
    name = title.lower().strip()

    # Replace common special characters
    name = re.sub(r"[^\w\s-]", "", name)

    # Replace whitespace and hyphens with underscores
    name = re.sub(r"[\s\-]+", "_", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)

    # Strip leading/trailing underscores
    name = name.strip("_")

    # Truncate if too long
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH].rstrip("_")

    # Append extension
    return f"{name}.pdf"


def ensure_download_dir(directory: str = "downloads") -> str:
    """
    Ensure the download directory exists. Create it if it doesn't.

    Args:
        directory: Path to the download directory.

    Returns:
        Absolute path to the created/existing directory.
    """
    abs_path = os.path.abspath(directory)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def download_pdf(
    url: str,
    save_path: str,
    timeout: int = 60,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> bool:
    """
    Download a PDF file using requests with streaming.

    Implements retry logic for transient network errors and validates
    that the downloaded content is actually a PDF.

    Args:
        url: Direct URL to the PDF file.
        save_path: Local file path to save the PDF.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts.
        retry_delay: Delay between retries in seconds.

    Returns:
        True if download was successful, False otherwise.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*",
    }

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"[Download] Attempt {attempt}/{max_retries}: {url}"
            )

            response = requests.get(
                url, headers=headers, stream=True, timeout=timeout
            )
            response.raise_for_status()

            # Verify content type is PDF-like
            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
                # Some servers don't set correct content type, check magic bytes
                first_chunk = next(response.iter_content(chunk_size=8))
                if not first_chunk.startswith(b"%PDF"):
                    logger.warning(
                        f"[Download] Content is not a PDF "
                        f"(Content-Type: {content_type}). Skipping."
                    )
                    return False
                # Write the first chunk and continue
                with open(save_path, "wb") as f:
                    f.write(first_chunk)
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            else:
                # Stream and write the file
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            # Verify file size is reasonable (> 1KB)
            file_size = os.path.getsize(save_path)
            if file_size < 1024:
                logger.warning(
                    f"[Download] File too small ({file_size} bytes). "
                    f"Likely not a valid PDF."
                )
                os.remove(save_path)
                return False

            logger.info(
                f"[Download] Success! Saved to {save_path} "
                f"({file_size / 1024:.1f} KB)"
            )
            return True

        except requests.exceptions.Timeout:
            logger.warning(f"[Download] Timeout on attempt {attempt}.")
        except requests.exceptions.ConnectionError:
            logger.warning(f"[Download] Connection error on attempt {attempt}.")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[Download] HTTP error {e.response.status_code}: {e}")
            if e.response.status_code == 404:
                return False  # Don't retry 404s
        except Exception as e:
            logger.error(f"[Download] Unexpected error: {e}")

        # Retry delay with exponential backoff
        if attempt < max_retries:
            wait = retry_delay * attempt
            logger.info(f"[Download] Retrying in {wait:.1f}s...")
            time.sleep(wait)

    logger.error(f"[Download] Failed after {max_retries} attempts: {url}")
    return False


def create_zip_archive(
    file_paths: List[str], zip_name: str = "journals.zip"
) -> Optional[bytes]:
    """
    Create an in-memory ZIP archive from a list of file paths.

    Args:
        file_paths: List of absolute paths to files to include.
        zip_name: Name for the zip (used for logging only).

    Returns:
        Bytes of the ZIP file, or None if no files were added.
    """
    if not file_paths:
        logger.warning("[ZIP] No files to archive.")
        return None

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in file_paths:
            if os.path.exists(fpath):
                arcname = os.path.basename(fpath)
                zf.write(fpath, arcname)
                logger.info(f"[ZIP] Added: {arcname}")
            else:
                logger.warning(f"[ZIP] File not found, skipping: {fpath}")

    buffer.seek(0)
    logger.info(
        f"[ZIP] Archive created: {zip_name} "
        f"({buffer.getbuffer().nbytes / 1024:.1f} KB)"
    )
    return buffer.getvalue()


def format_file_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
