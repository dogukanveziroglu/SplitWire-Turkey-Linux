"""
WGCF (Cloudflare WARP) integration for WireGuard service.

Provides WARP account registration, profile generation,
and wgcf binary download functionality.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from splitwire.core.shell.executor import ShellExecutor

from .config_helpers import (
    build_config_content,
    clean_dns_config,
    modify_allowed_ips,
    modify_endpoint,
)
from .constants import (
    WGCF_ACCOUNT_FILE,
    WGCF_BINARY,
    WGCF_DIR,
    WGCF_GITHUB_API,
    WGCF_PROFILE_FILE,
)
from .models import TunnelMode

# WGCF-specific timeouts (seconds)
TIMEOUT_WGCF_COMMAND = 60
TIMEOUT_API_REQUEST = 30
TIMEOUT_BINARY_DOWNLOAD = 120


def ensure_wgcf(logger: logging.Logger) -> bool:
    """
    Ensure wgcf binary is available.

    Args:
        logger: Logger instance

    Returns:
        True if wgcf is available
    """
    if WGCF_BINARY.exists() and os.access(WGCF_BINARY, os.X_OK):
        return True

    logger.info("Downloading wgcf...")
    return download_wgcf(logger)


def register_warp_account(shell: ShellExecutor, logger: logging.Logger) -> bool:
    """
    Register a new Cloudflare WARP account using wgcf.

    Args:
        shell: Shell runner instance
        logger: Logger instance

    Returns:
        True if registration successful
    """
    if not ensure_wgcf(logger):
        return False

    if WGCF_ACCOUNT_FILE.exists():
        logger.info("WARP account already exists")
        return True

    logger.info("Registering WARP account...")
    result = shell.run(
        [str(WGCF_BINARY), "register", "--accept-tos"],
        cwd=WGCF_DIR,
        timeout=TIMEOUT_WGCF_COMMAND,
    )

    if result.success:
        logger.info("WARP account registered")
        return True
    logger.error(f"Registration failed: {result.stderr}")
    return False


def generate_warp_profile(shell: ShellExecutor, logger: logging.Logger) -> bool:
    """
    Generate WireGuard profile from WARP account.

    Args:
        shell: Shell runner instance
        logger: Logger instance

    Returns:
        True if generation successful
    """
    if not WGCF_ACCOUNT_FILE.exists() and not register_warp_account(shell, logger):
        return False

    logger.info("Generating WARP profile...")
    result = shell.run(
        [str(WGCF_BINARY), "generate"],
        cwd=WGCF_DIR,
        timeout=TIMEOUT_WGCF_COMMAND,
    )

    if result.success and WGCF_PROFILE_FILE.exists():
        logger.info("WARP profile generated")
        return True
    logger.error(f"Profile generation failed: {result.stderr}")
    return False


def generate_warp_config(
    shell: ShellExecutor,
    logger: logging.Logger,
    endpoint_type: str = "standard",
    tunnel_mode: str = TunnelMode.SPLIT,
) -> str | None:
    """
    Generate WireGuard config for WARP.

    Args:
        shell: Shell runner instance
        logger: Logger instance
        endpoint_type: WARP endpoint type
        tunnel_mode: TunnelMode.SPLIT or TunnelMode.FULL

    Returns:
        Config content or None
    """
    if not WGCF_PROFILE_FILE.exists() and not generate_warp_profile(shell, logger):
        return None

    config = WGCF_PROFILE_FILE.read_text()
    config = modify_allowed_ips(config, tunnel_mode=tunnel_mode)
    config = modify_endpoint(config, endpoint_type)
    return clean_dns_config(config)


def get_config_content(
    shell: ShellExecutor,
    logger: logging.Logger,
    endpoint_type: str = "standard",
    tunnel_mode: str = TunnelMode.SPLIT,
) -> str:
    """
    Generate WireGuard config content as string.

    Args:
        shell: Shell runner instance
        logger: Logger instance
        endpoint_type: WARP endpoint type
        tunnel_mode: TunnelMode.SPLIT or TunnelMode.FULL

    Returns:
        Configuration content or empty string
    """
    if not WGCF_PROFILE_FILE.exists() and not generate_warp_profile(shell, logger):
        return ""

    try:
        return build_config_content(
            WGCF_PROFILE_FILE.read_text(),
            endpoint_type,
            tunnel_mode,
        )
    except Exception as e:
        logger.error(f"Failed to read config: {e}")
        return ""


def download_wgcf(logger: logging.Logger) -> bool:
    """
    Download wgcf binary from GitHub.

    Args:
        logger: Logger instance

    Returns:
        True if download successful
    """
    try:
        logger.debug("Fetching wgcf release info...")
        req = Request(WGCF_GITHUB_API)
        req.add_header("User-Agent", "SplitWire-Turkey")

        with urlopen(req, timeout=TIMEOUT_API_REQUEST) as response:
            release_info = json.loads(response.read().decode())

        url = _find_download_url(release_info, logger)
        if not url:
            return False

        return _download_and_install(url, logger)

    except (URLError, HTTPError) as e:
        logger.error(f"Download failed: {e}")
        return False
    except Exception as e:
        logger.exception(f"Download error: {e}")
        return False


def _find_download_url(release_info: dict, logger: logging.Logger) -> str | None:
    """Find Linux amd64 asset URL from release info."""
    for asset in release_info.get("assets", []):
        name = asset.get("name", "")
        if "linux" in name.lower() and "amd64" in name.lower():
            return asset.get("browser_download_url")

    logger.error("Could not find wgcf Linux amd64 binary")
    return None


def _download_and_install(url: str, logger: logging.Logger) -> bool:
    """Download and install wgcf binary from URL."""
    logger.info(f"Downloading from {url}")
    req = Request(url)
    req.add_header("User-Agent", "SplitWire-Turkey")

    with urlopen(req, timeout=TIMEOUT_BINARY_DOWNLOAD) as response:
        binary_data = response.read()

    WGCF_BINARY.write_bytes(binary_data)
    os.chmod(WGCF_BINARY, 0o755)  # noqa: S103 -- binary needs execute permission

    logger.info("wgcf downloaded successfully")
    return True
