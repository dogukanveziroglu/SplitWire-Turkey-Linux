"""DNS service data models and presets."""

from dataclasses import dataclass
from enum import Enum


class DNSManager(Enum):
    """DNS management backend."""

    SYSTEMD_RESOLVED = "systemd-resolved"  # Primary for Ubuntu
    NETWORK_MANAGER = "networkmanager"  # Alternative
    RESOLVCONF = "resolvconf"  # Legacy
    MANUAL = "manual"  # Direct /etc/resolv.conf edit
    UNKNOWN = "unknown"


class DoHMode(Enum):
    """DNS over HTTPS mode."""

    OFF = "off"  # No DoH
    OPPORTUNISTIC = "opportunistic"  # Use DoH if available
    STRICT = "strict"  # Require DoH, fail if unavailable


@dataclass
class DNSServer:
    """DNS server configuration."""

    name: str
    primary: str
    secondary: str
    doh_url: str | None = None
    dot_hostname: str | None = None  # DNS over TLS hostname


@dataclass
class DNSBackup:
    """Backup of original DNS settings."""

    timestamp: str
    dns_servers: list[str]
    search_domains: list[str]
    doh_enabled: bool
    interface: str | None = None
    raw_config: str | None = None


@dataclass
class DNSConfig:
    """DNS service configuration."""

    enabled: bool = False
    preset_name: str = "cloudflare"
    custom_primary: str = ""
    custom_secondary: str = ""
    doh_mode: DoHMode = DoHMode.OPPORTUNISTIC
    auto_apply_on_install: bool = False
    backup_exists: bool = False


DNS_PRESETS: dict[str, DNSServer] = {
    "google": DNSServer(
        name="Google DNS",
        primary="8.8.8.8",
        secondary="8.8.4.4",
        doh_url="https://dns.google/dns-query",
        dot_hostname="dns.google",
    ),
    "cloudflare": DNSServer(
        name="Cloudflare DNS",
        primary="1.1.1.1",
        secondary="1.0.0.1",
        doh_url="https://cloudflare-dns.com/dns-query",
        dot_hostname="cloudflare-dns.com",
    ),
    "cloudflare_family": DNSServer(
        name="Cloudflare Family",
        primary="1.1.1.3",
        secondary="1.0.0.3",
        doh_url="https://family.cloudflare-dns.com/dns-query",
        dot_hostname="family.cloudflare-dns.com",
    ),
    "quad9": DNSServer(
        name="Quad9 DNS",
        primary="9.9.9.9",
        secondary="149.112.112.112",
        doh_url="https://dns.quad9.net/dns-query",
        dot_hostname="dns.quad9.net",
    ),
    "quad9_unsecured": DNSServer(
        name="Quad9 Unsecured",
        primary="9.9.9.10",
        secondary="149.112.112.10",
        doh_url="https://dns10.quad9.net/dns-query",
        dot_hostname="dns10.quad9.net",
    ),
    "opendns": DNSServer(
        name="OpenDNS",
        primary="208.67.222.222",
        secondary="208.67.220.220",
        doh_url="https://doh.opendns.com/dns-query",
        dot_hostname="dns.opendns.com",
    ),
    "adguard": DNSServer(
        name="AdGuard DNS",
        primary="94.140.14.14",
        secondary="94.140.15.15",
        doh_url="https://dns.adguard-dns.com/dns-query",
        dot_hostname="dns.adguard-dns.com",
    ),
    "adguard_family": DNSServer(
        name="AdGuard Family",
        primary="94.140.14.15",
        secondary="94.140.15.16",
        doh_url="https://family.adguard-dns.com/dns-query",
        dot_hostname="family.adguard-dns.com",
    ),
    "turkish_telecom": DNSServer(
        name="Turk Telekom DNS",
        primary="195.175.39.39",
        secondary="195.175.39.40",
        doh_url=None,  # No DoH support
        dot_hostname=None,
    ),
}
