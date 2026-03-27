"""DNS management service for SplitWire Linux."""

from .constants import BACKUP_FILE, CONFIG_FILE, LOCAL_CONFIG_DIR
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
    "BACKUP_FILE",
    "CONFIG_FILE",
    "LOCAL_CONFIG_DIR",
    "get_dns_service",
]
