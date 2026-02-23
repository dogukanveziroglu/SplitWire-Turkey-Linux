"""DNS management service for SplitWire Linux."""

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
    "get_dns_service",
]
