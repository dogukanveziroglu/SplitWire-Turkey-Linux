"""
ByeDPI binary download and extraction.

Downloads and installs the ciadpi binary from GitHub releases.
"""

import json
import os
import platform
import tempfile
import urllib.request
from pathlib import Path

from .constants import (
    BYEDPI_BINARY,
    BYEDPI_INSTALL_DIR,
    CIADPI_RELEASE_URL,
)

# Download-specific timeouts (seconds)
TIMEOUT_API_REQUEST = 30
TIMEOUT_BINARY_DOWNLOAD = 120


def is_binary_installed() -> bool:
    """Check if ciadpi binary is installed and executable."""
    exists = BYEDPI_BINARY.exists()
    executable = os.access(BYEDPI_BINARY, os.X_OK) if exists else False
    return exists and executable


def fetch_release_info(logger) -> dict | None:
    """
    Fetch latest release info from GitHub API.

    Args:
        logger: Logger instance

    Returns:
        Release data dict or None on failure
    """
    logger.info("Fetching latest release info...")
    req = urllib.request.Request(
        CIADPI_RELEASE_URL,
        headers={"User-Agent": "SplitWire-Turkey"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_API_REQUEST) as response:
        return json.loads(response.read().decode())


def find_asset_url(release_data: dict, logger) -> str | None:
    """
    Find the download URL for current architecture.

    Args:
        release_data: GitHub API release response
        logger: Logger instance

    Returns:
        Download URL or None
    """
    arch_map = {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
        "armv7l": "armv7l",
        "i686": "i686",
    }
    arch = platform.machine()
    arch_suffix = arch_map.get(arch)

    if not arch_suffix:
        logger.error(f"Unsupported architecture: {arch}")
        return None

    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        if arch_suffix in name and name.endswith(".tar.gz") and "w64" not in name:
            return asset.get("browser_download_url")

    logger.error(f"No asset found for {arch_suffix}")
    return None


def download_and_extract(url: str, run_privileged_fn, logger) -> bool:
    """
    Download and extract ciadpi binary from tar.gz archive.

    Args:
        url: Download URL
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance

    Returns:
        True if successful
    """
    import tarfile

    result = run_privileged_fn(["mkdir", "-p", str(BYEDPI_INSTALL_DIR)])
    if not result.success:
        return False

    logger.info(f"Downloading from {url}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
        tmp_path = tmp.name

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SplitWire-Turkey"})
        with (
            urllib.request.urlopen(req, timeout=TIMEOUT_BINARY_DOWNLOAD) as resp,
            open(tmp_path, "wb") as f,
        ):
            f.write(resp.read())

        if not _extract_binary(tarfile, tmp_path, run_privileged_fn, logger):
            return False

        result = run_privileged_fn(["chmod", "+x", str(BYEDPI_BINARY)])
        if not result.success:
            return False

        logger.info("ciadpi downloaded successfully")
        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _extract_binary(tarfile, tmp_path: str, run_privileged_fn, logger) -> bool:
    """
    Extract ciadpi binary from tar.gz archive.

    Args:
        tarfile: tarfile module reference
        tmp_path: Path to downloaded archive
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance

    Returns:
        True if binary found and extracted
    """
    with tempfile.TemporaryDirectory() as extract_dir:
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extractall(  # noqa: S202 -- trusted GitHub release archive
                extract_dir
            )

        for root, _dirs, files in os.walk(extract_dir):
            for filename in files:
                if filename.startswith("ciadpi"):
                    src = Path(root) / filename
                    result = run_privileged_fn(["cp", str(src), str(BYEDPI_BINARY)])
                    if result.success:
                        return True

    logger.error("ciadpi binary not found in archive")
    return False


def download_binary(run_privileged_fn, logger) -> bool:
    """
    Download ciadpi binary from GitHub releases.

    Args:
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance

    Returns:
        True if download successful
    """
    try:
        release_data = fetch_release_info(logger)
        if not release_data:
            return False

        url = find_asset_url(release_data, logger)
        if not url:
            return False

        return download_and_extract(url, run_privileged_fn, logger)
    except Exception as e:
        logger.exception(f"Failed to download ciadpi: {e}")
        return False
