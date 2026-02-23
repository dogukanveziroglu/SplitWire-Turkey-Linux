"""iptables rule management for the Zapret service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .constants import (
    DEFAULT_HTTP_PORTS,
    DEFAULT_HTTPS_PORTS,
    NFQUEUE_NUM,
    TPWS_PORT,
)
from .models import ZapretMode

if TYPE_CHECKING:
    from .service import ZapretService

logger = logging.getLogger(__name__)


def add_iptables_rules(service: ZapretService) -> bool:
    """
    Add iptables rules for traffic redirection.

    Args:
        service: The ZapretService instance providing config and privileged execution.

    Returns:
        True if at least one rule was added successfully.
    """
    try:
        mode = service._get_current_mode()
        http_ports = service._config.http_ports or DEFAULT_HTTP_PORTS
        https_ports = service._config.https_ports or DEFAULT_HTTPS_PORTS

        rules_added: list[str] = []

        nfqws_modes = [ZapretMode.NFQWS, ZapretMode.COMBINED]
        if mode in nfqws_modes:
            rules_added.extend(_add_nfqueue_rules(service, http_ports, https_ports))

        tpws_modes = [ZapretMode.TPWS, ZapretMode.COMBINED]
        if mode in tpws_modes:
            rules_added.extend(_add_redirect_rules(service, https_ports))

        logger.debug("Added iptables rules: %s", rules_added)
        return len(rules_added) > 0

    except Exception as e:
        logger.error("Failed to add iptables rules: %s", e)
        return False


def _add_nfqueue_rules(
    service: ZapretService,
    http_ports: list[int],
    https_ports: list[int],
) -> list[str]:
    """Add NFQUEUE rules for nfqws on HTTP and HTTPS ports."""
    rules_added = [
        f"NFQUEUE HTTP {port}" for port in http_ports if _add_single_nfqueue_rule(service, port)
    ]
    rules_added.extend(
        f"NFQUEUE HTTPS {port}" for port in https_ports if _add_single_nfqueue_rule(service, port)
    )
    return rules_added


def _add_single_nfqueue_rule(service: ZapretService, port: int) -> bool:
    """Add a single NFQUEUE iptables rule for the given port."""
    logger.debug("[ZAPRET] Adding NFQUEUE rule for port %s", port)
    result = service._run_privileged(
        [
            "iptables",
            "-t",
            "mangle",
            "-A",
            "POSTROUTING",
            "-p",
            "tcp",
            "--dport",
            str(port),
            "-j",
            "NFQUEUE",
            "--queue-num",
            str(NFQUEUE_NUM),
        ]
    )
    if result.success:
        logger.debug("[ZAPRET] Added NFQUEUE rule for port %s", port)
        return True

    logger.warning(
        "[ZAPRET] Failed to add NFQUEUE rule for port %s: %s",
        port,
        result.stderr,
    )
    return False


def _add_redirect_rules(
    service: ZapretService,
    https_ports: list[int],
) -> list[str]:
    """Add REDIRECT rules for tpws on HTTPS ports."""
    return [f"REDIRECT {port}" for port in https_ports if _add_single_redirect_rule(service, port)]


def _add_single_redirect_rule(service: ZapretService, port: int) -> bool:
    """Add a single REDIRECT iptables rule for the given port."""
    logger.debug(
        "[ZAPRET] Adding REDIRECT rule for port %s to %s",
        port,
        TPWS_PORT,
    )
    result = service._run_privileged(
        [
            "iptables",
            "-t",
            "nat",
            "-A",
            "OUTPUT",
            "-p",
            "tcp",
            "--dport",
            str(port),
            "-j",
            "REDIRECT",
            "--to-port",
            str(TPWS_PORT),
        ]
    )
    if result.success:
        logger.debug("[ZAPRET] Added REDIRECT rule for port %s", port)
        return True

    logger.warning(
        "[ZAPRET] Failed to add REDIRECT rule for port %s: %s",
        port,
        result.stderr,
    )
    return False


def remove_iptables_rules(service: ZapretService) -> bool:
    """
    Remove all iptables rules added by zapret.

    Args:
        service: The ZapretService instance providing config and privileged execution.

    Returns:
        True if removal completed without exceptions.
    """
    logger.info("[ZAPRET] Removing iptables rules...")
    try:
        http_ports = service._config.http_ports or DEFAULT_HTTP_PORTS
        https_ports = service._config.https_ports or DEFAULT_HTTPS_PORTS

        _remove_nfqueue_rules(service, http_ports + https_ports)
        _remove_redirect_rules(service, https_ports)

        logger.info("[ZAPRET] iptables rules removed")
        return True

    except Exception as e:
        logger.error("Failed to remove iptables rules: %s", e)
        return False


def _remove_nfqueue_rules(service: ZapretService, ports: list[int]) -> None:
    """Remove NFQUEUE rules for the given ports."""
    for port in ports:
        logger.debug("[ZAPRET] Removing NFQUEUE rule for port %s", port)
        result = service._run_privileged(
            [
                "iptables",
                "-t",
                "mangle",
                "-D",
                "POSTROUTING",
                "-p",
                "tcp",
                "--dport",
                str(port),
                "-j",
                "NFQUEUE",
                "--queue-num",
                str(NFQUEUE_NUM),
            ]
        )
        if not result.success:
            logger.debug(
                "[ZAPRET] NFQUEUE rule for port %s may not exist: %s",
                port,
                result.stderr,
            )


def _remove_redirect_rules(service: ZapretService, ports: list[int]) -> None:
    """Remove REDIRECT rules for the given ports."""
    for port in ports:
        logger.debug("[ZAPRET] Removing REDIRECT rule for port %s", port)
        result = service._run_privileged(
            [
                "iptables",
                "-t",
                "nat",
                "-D",
                "OUTPUT",
                "-p",
                "tcp",
                "--dport",
                str(port),
                "-j",
                "REDIRECT",
                "--to-port",
                str(TPWS_PORT),
            ]
        )
        if not result.success:
            logger.debug(
                "[ZAPRET] REDIRECT rule for port %s may not exist: %s",
                port,
                result.stderr,
            )
