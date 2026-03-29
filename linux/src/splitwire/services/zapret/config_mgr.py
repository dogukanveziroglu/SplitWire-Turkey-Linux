"""Configuration, preset, and blacklist management for the Zapret service."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .constants import (
    BLACKLIST_FILE,
    CUSTOM_CONFIG_FILE,
    LOCAL_CONFIG_DIR,
    PRESETS_FILE,
)
from .models import (
    DEFAULT_PRESETS,
    ZapretConfig,
    ZapretMode,
    ZapretPreset,
)

if TYPE_CHECKING:
    from .service import ZapretService

logger = logging.getLogger(__name__)


# =========================================================================
# Preset Management
# =========================================================================


def load_presets(service: ZapretService) -> None:
    """Load presets from file or use defaults."""
    service._presets = DEFAULT_PRESETS.copy()
    if not PRESETS_FILE.exists():
        return
    try:
        data = json.loads(PRESETS_FILE.read_text())
        for name, pdata in data.get("custom_presets", {}).items():
            service._presets[name] = ZapretPreset(
                name=pdata.get("name", name),
                description=pdata.get("description", ""),
                nfqws_args=pdata.get("nfqws_args", ""),
                tpws_args=pdata.get("tpws_args", ""),
                mode=ZapretMode(pdata.get("mode", "nfqws")),
                use_blacklist=pdata.get("use_blacklist", False),
                is_custom=True,
            )
    except Exception as e:
        logger.warning("Failed to load presets: %s", e)


def save_presets(service: ZapretService) -> None:
    """Save custom presets to file."""
    try:
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        custom = {
            name: {
                "name": p.name,
                "description": p.description,
                "nfqws_args": p.nfqws_args,
                "tpws_args": p.tpws_args,
                "mode": p.mode.value,
                "use_blacklist": p.use_blacklist,
            }
            for name, p in service._presets.items()
            if p.is_custom
        }
        data = {"custom_presets": custom}
        PRESETS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("Failed to save presets: %s", e)


# =========================================================================
# Configuration Persistence
# =========================================================================


def load_config(service: ZapretService) -> None:
    """Load configuration from file."""
    if not CUSTOM_CONFIG_FILE.exists():
        return
    try:
        data = json.loads(CUSTOM_CONFIG_FILE.read_text())
        service._config = ZapretConfig(
            enabled=data.get("enabled", False),
            mode=ZapretMode(data.get("mode", "nfqws")),
            preset_name=data.get("preset_name", "discord"),
            custom_nfqws_args=data.get("custom_nfqws_args", ""),
            custom_tpws_args=data.get("custom_tpws_args", ""),
            use_blacklist=data.get("use_blacklist", False),
            http_ports=data.get("http_ports", [80]),
            https_ports=data.get("https_ports", [443]),
            quic_enabled=data.get("quic_enabled", False),
        )
    except Exception as e:
        logger.warning("Failed to load config: %s", e)


def save_config(service: ZapretService) -> None:
    """Save configuration to file."""
    try:
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "enabled": service._config.enabled,
            "mode": service._config.mode.value,
            "preset_name": service._config.preset_name,
            "custom_nfqws_args": service._config.custom_nfqws_args,
            "custom_tpws_args": service._config.custom_tpws_args,
            "use_blacklist": service._config.use_blacklist,
            "http_ports": service._config.http_ports,
            "https_ports": service._config.https_ports,
            "quic_enabled": service._config.quic_enabled,
        }
        CUSTOM_CONFIG_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error("Failed to save config: %s", e)


# =========================================================================
# Blacklist Management
# =========================================================================


def get_blacklist() -> list[str]:
    """Get current blacklist domains."""
    if not BLACKLIST_FILE.exists():
        logger.debug("[ZAPRET] Blacklist file does not exist: %s", BLACKLIST_FILE)
        return []
    try:
        content = BLACKLIST_FILE.read_text()
        domains = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        logger.debug("[ZAPRET] Loaded %d domains from blacklist", len(domains))
        return domains
    except Exception as e:
        logger.error("[ZAPRET] Failed to read blacklist: %s", e)
        return []


def set_blacklist(domains: list[str]) -> bool:
    """Set blacklist domains."""
    try:
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        content = "# SplitWire Zapret Blacklist\n"
        content += "# One domain per line\n\n"
        content += "\n".join(domains)
        BLACKLIST_FILE.write_text(content)
        return True
    except Exception as e:
        logger.error("Failed to save blacklist: %s", e)
        return False
