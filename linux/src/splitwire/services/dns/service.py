"""DNS management service for SplitWire Linux."""

import json
import re
from datetime import datetime
from pathlib import Path

from ..base import BaseService, ServiceStatus, ServiceType
from .backends import (
    apply_manual_dns,
    apply_network_manager,
    apply_systemd_resolved,
    parse_resolv_conf,
    parse_resolvectl_output,
    remove_systemd_resolved,
    restore_manual_dns,
    restore_network_manager,
)
from .constants import BACKUP_FILE, CONFIG_FILE, LOCAL_CONFIG_DIR
from .models import (
    DNS_PRESETS,
    DNSBackup,
    DNSConfig,
    DNSManager,
    DNSServer,
    DoHMode,
)


class DNSService(BaseService):
    """
    DNS management service.

    Provides DNS configuration with DoH support using systemd-resolved
    on Ubuntu systems. Supports multiple DNS presets and custom servers.
    """

    def __init__(self):
        """Initialize DNS service."""
        super().__init__(
            name="dns",
            display_name="DNS Service",
            description="DNS management with DoH support",
            service_type=ServiceType.DNS,
        )
        self._config = DNSConfig()
        self._dns_manager: DNSManager | None = None
        self._ensure_directories()
        self._load_config()
        self._detect_dns_manager()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text())
            self._config = DNSConfig(
                enabled=data.get("enabled", False),
                preset_name=data.get("preset_name", "cloudflare"),
                custom_primary=data.get("custom_primary", ""),
                custom_secondary=data.get("custom_secondary", ""),
                doh_mode=DoHMode(data.get("doh_mode", "opportunistic")),
                auto_apply_on_install=data.get("auto_apply_on_install", False),
                backup_exists=data.get("backup_exists", False),
            )
        except Exception as e:
            self._logger.warning(f"Failed to load config: {e}")

    def _save_config(self) -> None:
        """Save configuration to file."""
        data = {
            "enabled": self._config.enabled,
            "preset_name": self._config.preset_name,
            "custom_primary": self._config.custom_primary,
            "custom_secondary": self._config.custom_secondary,
            "doh_mode": self._config.doh_mode.value,
            "auto_apply_on_install": self._config.auto_apply_on_install,
            "backup_exists": self._config.backup_exists,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    def _detect_dns_manager(self) -> None:
        """Detect which DNS manager is in use."""
        self._logger.info("[DNS] Detecting DNS manager...")

        result = self._shell.run(["systemctl", "is-active", "systemd-resolved"], timeout=5)
        if result.success and result.stdout.strip() == "active":
            self._dns_manager = DNSManager.SYSTEMD_RESOLVED
            self._logger.info("[DNS] Detected: systemd-resolved")
            return

        result = self._shell.run(["systemctl", "is-active", "NetworkManager"], timeout=5)
        if result.success and result.stdout.strip() == "active":
            self._dns_manager = DNSManager.NETWORK_MANAGER
            self._logger.info("[DNS] Detected: NetworkManager (fallback)")
            return

        if self._shell.command_exists("resolvconf"):
            self._dns_manager = DNSManager.RESOLVCONF
            self._logger.info("[DNS] Detected: resolvconf (fallback)")
            return

        self._dns_manager = DNSManager.MANUAL
        self._logger.warning("[DNS] No supported DNS manager, using manual")

    def install(
        self,
        preset: str | None = None,
        primary: str | None = None,
        secondary: str | None = None,
        doh_mode: DoHMode = DoHMode.OPPORTUNISTIC,
        **kwargs,
    ) -> bool:
        """Install DNS configuration."""
        self._logger.info("Installing DNS configuration")
        self._notify_status_change(ServiceStatus.INSTALLING)

        try:
            if not self._config.backup_exists:
                self._backup_current_dns()

            dns_primary, dns_secondary = self._resolve_dns_servers(preset, primary, secondary)
            self._config.doh_mode = doh_mode

            if not self._apply_dns(dns_primary, dns_secondary, doh_mode):
                return False

            self._config.enabled = True
            self._save_config()
            self._logger.info(f"DNS configured: {dns_primary}, {dns_secondary}")
            self._notify_status_change(ServiceStatus.RUNNING)
            return True

        except Exception as e:
            self._logger.exception(f"DNS installation failed: {e}")
            self._notify_status_change(ServiceStatus.FAILED)
            return False

    def _resolve_dns_servers(
        self,
        preset: str | None,
        primary: str | None,
        secondary: str | None,
    ) -> tuple[str, str]:
        """Determine DNS servers from arguments."""
        if primary:
            self._config.custom_primary = primary
            self._config.custom_secondary = secondary or ""
            return primary, secondary or primary

        if preset and preset in DNS_PRESETS:
            dns_server = DNS_PRESETS[preset]
            self._config.preset_name = preset
            return dns_server.primary, dns_server.secondary

        dns_server = DNS_PRESETS["cloudflare"]
        return dns_server.primary, dns_server.secondary

    def _apply_dns(self, primary: str, secondary: str, doh_mode: DoHMode) -> bool:
        """Apply DNS settings based on detected manager."""
        if self._dns_manager == DNSManager.SYSTEMD_RESOLVED:
            return apply_systemd_resolved(
                primary,
                secondary,
                doh_mode,
                self._run_privileged,
                self._logger,
            )
        if self._dns_manager == DNSManager.NETWORK_MANAGER:
            return apply_network_manager(
                primary,
                secondary,
                self._shell,
                self._run_privileged,
                self._logger,
            )
        return apply_manual_dns(primary, secondary, self._run_privileged, self._logger)

    def remove(self) -> bool:
        """Remove DNS configuration and restore original settings."""
        self._logger.info("Removing DNS configuration")
        try:
            if self._config.backup_exists:
                self._restore_dns()

            self._config.enabled = False
            self._save_config()
            self._logger.info("DNS configuration removed")
            self._notify_status_change(ServiceStatus.NOT_INSTALLED)
            return True

        except Exception as e:
            self._logger.exception(f"DNS removal failed: {e}")
            return False

    def start(self) -> bool:
        """Start/apply DNS configuration."""
        if not self._config.enabled:
            return self.install()
        return True

    def stop(self) -> bool:
        """Stop DNS configuration (restore original)."""
        return self.remove()

    def status(self) -> ServiceStatus:
        """Get DNS service status."""
        if not self._config.enabled:
            return ServiceStatus.NOT_INSTALLED

        current_dns = self._get_current_dns()
        self._logger.debug(f"[DNS] Current DNS servers: {current_dns}")

        if current_dns:
            preset = self.get_current_preset()
            if preset and (preset.primary in current_dns or preset.secondary in current_dns):
                return ServiceStatus.RUNNING

            if self._config.custom_primary and self._config.custom_primary in current_dns:
                return ServiceStatus.RUNNING

        return ServiceStatus.STOPPED

    def is_installed(self) -> bool:
        """Check if DNS is configured."""
        return self._config.enabled

    def get_config(self) -> DNSConfig:
        """Get current configuration."""
        return self._config

    def get_dns_manager(self) -> DNSManager:
        """Get detected DNS manager."""
        return self._dns_manager or DNSManager.UNKNOWN

    def get_all_presets(self) -> dict[str, DNSServer]:
        """Get all available DNS presets."""
        return DNS_PRESETS.copy()

    def get_preset(self, name: str) -> DNSServer | None:
        """Get a specific preset by name."""
        return DNS_PRESETS.get(name)

    def get_current_preset(self) -> DNSServer | None:
        """Get the currently selected preset."""
        return self.get_preset(self._config.preset_name)

    def set_preset(self, name: str) -> bool:
        """Set the active DNS preset."""
        if name not in DNS_PRESETS:
            self._logger.error(f"Unknown preset: {name}")
            return False
        self._config.preset_name = name
        self._config.custom_primary = ""
        self._config.custom_secondary = ""
        self._save_config()
        return True

    def set_custom_dns(self, primary: str, secondary: str = "") -> None:
        """Set custom DNS servers."""
        self._config.custom_primary = primary
        self._config.custom_secondary = secondary
        self._save_config()

    def set_doh_mode(self, mode: DoHMode) -> None:
        """Set DNS over HTTPS mode."""
        self._config.doh_mode = mode
        self._save_config()

    def set_auto_apply(self, enabled: bool) -> None:
        """Set auto-apply DNS on install option."""
        self._config.auto_apply_on_install = enabled
        self._save_config()

    def get_current_dns(self) -> list[str]:
        """Get currently configured DNS servers."""
        return self._get_current_dns()

    def is_doh_enabled(self) -> bool:
        """Check if DoH is currently enabled."""
        if self._dns_manager == DNSManager.SYSTEMD_RESOLVED:
            result = self._shell.run(["resolvectl", "status"], timeout=10)
            if result.success:
                return "DNSOverTLS" in result.stdout and "yes" in result.stdout.lower()
        return False

    def restore_original(self) -> bool:
        """Restore original DNS settings from backup."""
        return self._restore_dns()

    def has_backup(self) -> bool:
        """Check if backup exists."""
        return self._config.backup_exists and BACKUP_FILE.exists()

    def should_auto_apply(self) -> bool:
        """Check if DNS should be auto-applied on service install."""
        return self._config.auto_apply_on_install

    def apply_if_auto(self) -> bool:
        """Apply DNS if auto-apply is enabled."""
        if self.should_auto_apply() and not self._config.enabled:
            return self.install()
        return True

    def _backup_current_dns(self) -> bool:
        """Backup current DNS settings."""
        self._logger.info("Backing up current DNS settings")
        try:
            dns_servers, search_domains, doh_enabled, raw_config = self._read_current_dns_state()

            backup = DNSBackup(
                timestamp=datetime.now().isoformat(),
                dns_servers=list(dict.fromkeys(dns_servers)),
                search_domains=list(dict.fromkeys(search_domains)),
                doh_enabled=doh_enabled,
                raw_config=raw_config,
            )

            backup_data = {
                "timestamp": backup.timestamp,
                "dns_servers": backup.dns_servers,
                "search_domains": backup.search_domains,
                "doh_enabled": backup.doh_enabled,
                "raw_config": backup.raw_config,
            }
            BACKUP_FILE.write_text(json.dumps(backup_data, indent=2))

            self._config.backup_exists = True
            self._save_config()
            self._logger.info(f"DNS backup saved: {backup.dns_servers}")
            return True

        except Exception as e:
            self._logger.exception(f"Failed to backup DNS: {e}")
            return False

    def _read_current_dns_state(
        self,
    ) -> tuple[list[str], list[str], bool, str | None]:
        """Read current DNS state from the active manager."""
        dns_servers: list[str] = []
        search_domains: list[str] = []
        doh_enabled = False
        raw_config = None

        if self._dns_manager == DNSManager.SYSTEMD_RESOLVED:
            result = self._shell.run(["resolvectl", "status"], timeout=10)
            if result.success:
                raw_config = result.stdout
                dns_servers, search_domains, doh_enabled = parse_resolvectl_output(result.stdout)

        elif self._dns_manager == DNSManager.MANUAL:
            resolv_path = Path("/etc/resolv.conf")
            if resolv_path.exists():
                raw_config = resolv_path.read_text()
                dns_servers, search_domains = parse_resolv_conf(raw_config)

        return dns_servers, search_domains, doh_enabled, raw_config

    def _restore_dns(self) -> bool:
        """Restore DNS settings from backup."""
        self._logger.info("Restoring DNS settings from backup")

        if not BACKUP_FILE.exists():
            self._logger.warning("No backup file found")
            return False

        try:
            backup_data = json.loads(BACKUP_FILE.read_text())

            if self._dns_manager == DNSManager.SYSTEMD_RESOLVED:
                remove_systemd_resolved(self._run_privileged, self._logger)
            elif self._dns_manager == DNSManager.NETWORK_MANAGER:
                restore_network_manager(self._shell, self._run_privileged)
            elif self._dns_manager == DNSManager.MANUAL:
                restore_manual_dns(backup_data, self._run_privileged)

            self._config.enabled = False
            self._save_config()
            self._logger.info("DNS settings restored")
            return True

        except Exception as e:
            self._logger.exception(f"Failed to restore DNS: {e}")
            return False

    def _get_current_dns(self) -> list[str]:
        """Get currently configured DNS servers."""
        dns_servers: list[str] = []
        try:
            if self._dns_manager == DNSManager.SYSTEMD_RESOLVED:
                result = self._shell.run(["resolvectl", "status"], timeout=10)
                if result.success:
                    for line in result.stdout.split("\n"):
                        if "DNS Servers:" in line or "Current DNS Server:" in line:
                            ips = re.findall(r"\d+\.\d+\.\d+\.\d+", line)
                            dns_servers.extend(ips)

            elif self._dns_manager == DNSManager.MANUAL:
                resolv_path = Path("/etc/resolv.conf")
                if resolv_path.exists():
                    content = resolv_path.read_text()
                    dns_servers.extend(
                        line.split()[1]
                        for line in content.split("\n")
                        if line.startswith("nameserver")
                    )

        except Exception as e:
            self._logger.warning(f"Failed to get current DNS: {e}")

        return list(dict.fromkeys(dns_servers))


_dns_service: DNSService | None = None


def get_dns_service() -> DNSService:
    """Get the global DNS service instance."""
    global _dns_service
    if _dns_service is None:
        _dns_service = DNSService()
    return _dns_service
