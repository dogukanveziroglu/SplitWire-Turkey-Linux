"""DNS management service for SplitWire Linux."""

from .constants import LOCAL_CONFIG_DIR
from .models import (
    DNS_PRESETS,
    DNSBackup,
    DNSConfig,
    DNSManager,
    DNSServer,
    DoHMode,
)
from .service import DNSService, get_dns_service

__all__ = [
    "DNS_PRESETS",
    "DNSBackup",
    "DNSConfig",
    "DNSManager",
    "DNSServer",
    "DNSService",
    "DoHMode",
    "LOCAL_CONFIG_DIR",
    "get_dns_service",
]
