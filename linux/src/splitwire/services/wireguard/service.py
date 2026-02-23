"""WireGuard VPN service for SplitWire Linux."""

import tempfile
from pathlib import Path

from splitwire.core import get_config

from ..base import BaseService, ServiceInfo, ServiceStatus, ServiceType
from ..systemd import get_systemd_manager
from .config_helpers import build_config_content, parse_wg_show
from .constants import (
    REFRESH_SERVICE_UNIT,
    REFRESH_TIMER_UNIT,
    SPLITWIRE_CONFIG_FILE,
    SPLITWIRE_CONFIG_NAME,
    WGCF_DIR,
    WGCF_PROFILE_FILE,
    WIREGUARD_CONFIG_DIR,
)
from .models import TunnelMode, WireGuardInterface
from .wgcf import (
    ensure_wgcf,
    generate_warp_config,
    generate_warp_profile,
    get_config_content,
    register_warp_account,
)


class WireGuardService(BaseService):
    """
    WireGuard VPN service manager.

    Features:
    - Install/remove WireGuard configuration
    - Start/stop VPN connection via wg-quick
    - WGCF integration for Cloudflare WARP
    - IP-based split tunneling
    - Interface status monitoring
    """

    # WireGuard-specific timeouts (seconds)
    TIMEOUT_WG_QUICK = 30
    TIMEOUT_CONFIG_CHECK = 5
    TIMEOUT_CONNECTION_TEST = 10
    PING_COUNT = 1
    PING_WAIT_SECONDS = 5

    def __init__(self):
        """Initialize WireGuard service."""
        super().__init__(
            name="wireguard",
            display_name="WireGuard VPN",
            description="WireGuard VPN with Cloudflare WARP",
            service_type=ServiceType.VPN,
        )
        self._interface_name = SPLITWIRE_CONFIG_NAME
        self._config_file = SPLITWIRE_CONFIG_FILE
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        WGCF_DIR.mkdir(parents=True, exist_ok=True)

    def install(
        self,
        allowed_apps: list[str] | None = None,
        include_browsers: bool = False,
        use_warp: bool = True,
        custom_config: Path | None = None,
        endpoint_type: str = "standard",
        **kwargs,
    ) -> bool:
        """
        Install WireGuard VPN configuration.

        Args:
            allowed_apps: List of app paths to tunnel
            include_browsers: Include browsers in tunneling
            use_warp: Use Cloudflare WARP via wgcf
            custom_config: Path to custom WireGuard config
            endpoint_type: WARP endpoint type

        Returns:
            True if installation successful
        """
        self._logger.info(f"Installing WireGuard VPN (endpoint={endpoint_type})")
        self._notify_status_change(ServiceStatus.INSTALLING)

        try:
            if not self._check_dependencies():
                return False

            config_content = self._resolve_config_source(use_warp, custom_config, endpoint_type)
            if not config_content:
                return False

            if allowed_apps:
                config = get_config()
                config.wireguard.allowed_apps = allowed_apps

            if not self._install_config(config_content):
                return False

            if not self.start():
                return False

            self._logger.info("WireGuard VPN installed successfully")
            return True

        except Exception as e:
            self._logger.exception(f"Installation failed: {e}")
            self._notify_status_change(ServiceStatus.FAILED)
            return False

    def _resolve_config_source(
        self,
        use_warp: bool,
        custom_config: Path | None,
        endpoint_type: str,
    ) -> str | None:
        """Resolve WireGuard config content from sources."""
        if custom_config and custom_config.exists():
            return custom_config.read_text()

        if use_warp:
            content = generate_warp_config(
                self._shell,
                self._logger,
                endpoint_type=endpoint_type,
            )
            if not content:
                self._logger.error("Failed to generate WARP config")
                return None
            return content

        self._logger.error("No config source specified")
        return None

    def remove(self) -> bool:
        """Remove WireGuard VPN configuration."""
        self._logger.info("Removing WireGuard VPN")

        try:
            if self.is_running():
                self.stop()

            if self._check_config_exists():
                result = self._run_privileged(["rm", "-f", str(self._config_file)])
                if not result.success:
                    self._logger.warning(f"Failed to remove config: {result.stderr}")

            self._logger.info("WireGuard VPN removed")
            self._notify_status_change(ServiceStatus.NOT_INSTALLED)
            return True

        except Exception as e:
            self._logger.exception(f"Removal failed: {e}")
            return False

    def start(self) -> bool:
        """Start WireGuard VPN connection."""
        self._logger.info("Starting WireGuard VPN")

        if self.is_running():
            self._logger.info("WireGuard VPN already running")
            return True

        if not self._check_config_exists():
            self._logger.error("Config file not found")
            return False

        result = self._run_privileged(
            ["wg-quick", "up", self._interface_name], timeout=self.TIMEOUT_WG_QUICK
        )

        if result.success:
            self._logger.info("WireGuard VPN started")
            self._notify_status_change(ServiceStatus.RUNNING)
            return True
        self._logger.error(f"Failed to start: {result.stderr}")
        self._notify_status_change(ServiceStatus.FAILED)
        return False

    def stop(self) -> bool:
        """Stop WireGuard VPN connection."""
        self._logger.info("Stopping WireGuard VPN")

        result = self._run_privileged(
            ["wg-quick", "down", self._interface_name], timeout=self.TIMEOUT_WG_QUICK
        )

        if result.success:
            self._logger.info("WireGuard VPN stopped")
            self._notify_status_change(ServiceStatus.STOPPED)
            return True
        if "is not a WireGuard interface" in result.stderr:
            self._notify_status_change(ServiceStatus.STOPPED)
            return True
        self._logger.error(f"Failed to stop: {result.stderr}")
        return False

    def status(self) -> ServiceStatus:
        """Get WireGuard VPN status."""
        if not self.is_installed():
            return ServiceStatus.NOT_INSTALLED

        result = self._shell.run(["ip", "link", "show", self._interface_name])
        if result.success:
            return ServiceStatus.RUNNING
        return ServiceStatus.STOPPED

    def _check_config_exists(self) -> bool:
        """Check if config file exists (handles permissions)."""
        try:
            return self._config_file.exists()
        except PermissionError:
            result = self._shell.run(
                ["sudo", "test", "-f", str(self._config_file)],
                timeout=self.TIMEOUT_CONFIG_CHECK,
            )
            return result.success

    def is_installed(self) -> bool:
        """Check if WireGuard config is installed."""
        return self._check_config_exists()

    def get_info(self) -> ServiceInfo:
        """Get comprehensive service information."""
        info = super().get_info()

        if self.is_running():
            interface = self.get_interface_info()
            if interface:
                info.metadata = {
                    "public_key": interface.public_key,
                    "endpoint": interface.endpoint,
                    "latest_handshake": interface.latest_handshake,
                    "transfer_rx": interface.transfer_rx,
                    "transfer_tx": interface.transfer_tx,
                }

        info.config_path = self._config_file
        return info

    def get_interface_info(self) -> WireGuardInterface | None:
        """Get information about the WireGuard interface."""
        if not self.is_running():
            return None

        result = self._run_privileged(["wg", "show", self._interface_name])
        if not result.success:
            self._logger.error(f"[WG] wg show failed: {result.stderr}")
            return None

        return parse_wg_show(result.stdout, self._interface_name)

    def test_connection(self, test_host: str = "1.1.1.1") -> bool:
        """Test VPN connection by pinging through tunnel."""
        if not self.is_running():
            return False

        result = self._shell.run(
            [
                "ping",
                "-c",
                "1",
                "-W",
                str(self.PING_WAIT_SECONDS),
                "-I",
                self._interface_name,
                test_host,
            ],
            timeout=self.TIMEOUT_CONNECTION_TEST,
        )
        return result.success

    def get_transfer_stats(self) -> tuple[int, int]:
        """Get transfer statistics as (rx_bytes, tx_bytes)."""
        interface = self.get_interface_info()
        if interface:
            return (interface.transfer_rx, interface.transfer_tx)
        return (0, 0)

    def ensure_wgcf(self) -> bool:
        """Ensure wgcf binary is available."""
        return ensure_wgcf(self._logger)

    def register_warp_account(self) -> bool:
        """Register a new Cloudflare WARP account."""
        return register_warp_account(self._shell, self._logger)

    def generate_warp_profile(self) -> bool:
        """Generate WireGuard profile from WARP account."""
        return generate_warp_profile(self._shell, self._logger)

    def register_wgcf(self) -> bool:
        """Alias for register_warp_account()."""
        return self.register_warp_account()

    def _check_dependencies(self) -> bool:
        """Check required dependencies are installed."""
        required = ["wg", "wg-quick", "ip"]
        missing = [cmd for cmd in required if not self._check_binary_exists(cmd)]

        if missing:
            self._logger.error(f"Missing dependencies: {', '.join(missing)}")
            self._logger.info("Install with: sudo apt install wireguard-tools")
            return False
        return True

    def _install_config(self, config_content: str) -> bool:
        """Install WireGuard config file to /etc/wireguard/."""
        result = self._run_privileged(["mkdir", "-p", str(WIREGUARD_CONFIG_DIR)])
        if not result.success:
            self._logger.error(f"Failed to create config dir: {result.stderr}")
            return False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = self._run_privileged(["cp", temp_path, str(self._config_file)])
            if not result.success:
                self._logger.error(f"Failed to copy config: {result.stderr}")
                return False

            result = self._run_privileged(["chmod", "600", str(self._config_file)])
            if not result.success:
                self._logger.warning(f"Failed to set permissions: {result.stderr}")
            return True
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def enable_refresh_timer(self) -> bool:
        """Enable connection refresh timer via systemd."""
        self._logger.info("Enabling WireGuard refresh timer")
        try:
            systemd = get_systemd_manager()

            if not self._install_refresh_units(systemd):
                return False

            systemd.enable(REFRESH_TIMER_UNIT)
            systemd.start(REFRESH_TIMER_UNIT)
            self._logger.info("WireGuard refresh timer enabled (30 min)")
            return True
        except Exception as e:
            self._logger.exception(f"Failed to enable refresh timer: {e}")
            return False

    def _install_refresh_units(self, systemd) -> bool:
        """Install refresh service and timer systemd units."""
        if not systemd.unit_exists(REFRESH_SERVICE_UNIT) and not systemd.install_unit(
            REFRESH_SERVICE_UNIT, enable=False
        ):
            self._logger.error("Failed to install refresh service unit")
            return False

        if not systemd.unit_exists(REFRESH_TIMER_UNIT) and not systemd.install_unit(
            REFRESH_TIMER_UNIT, enable=True, start=True
        ):
            self._logger.error("Failed to install refresh timer unit")
            return False
        return True

    def disable_refresh_timer(self) -> bool:
        """Disable connection refresh timer."""
        self._logger.info("Disabling WireGuard refresh timer")
        try:
            systemd = get_systemd_manager()
            if systemd.is_active(REFRESH_TIMER_UNIT):
                systemd.stop(REFRESH_TIMER_UNIT)
            if systemd.is_enabled(REFRESH_TIMER_UNIT):
                systemd.disable(REFRESH_TIMER_UNIT)
            self._logger.info("WireGuard refresh timer disabled")
            return True
        except Exception as e:
            self._logger.exception(f"Failed to disable refresh timer: {e}")
            return False

    def is_refresh_timer_enabled(self) -> bool:
        """Check if refresh timer is enabled and running."""
        try:
            systemd = get_systemd_manager()
            return systemd.is_active(REFRESH_TIMER_UNIT)
        except Exception as e:
            self._logger.warning(f"[WG] Failed to check refresh timer: {e}")
            return False

    def generate_config(
        self,
        allowed_apps: list[str] | None = None,
        include_browsers: bool = False,
        endpoint: str | None = None,
        tunnel_mode: str = TunnelMode.SPLIT,
    ) -> str | None:
        """Generate WireGuard config and install it."""
        endpoint_type = endpoint or "standard"

        if not self.generate_warp_profile():
            return None

        try:
            content = build_config_content(
                WGCF_PROFILE_FILE.read_text(),
                endpoint_type,
                tunnel_mode,
            )
            if self._install_config(content):
                return str(self._config_file)
            self._logger.error("Failed to install config")
            return None
        except Exception as e:
            self._logger.error(f"Failed to generate config: {e}")
            return None

    def generate_config_content(
        self,
        allowed_apps: list[str] | None = None,
        include_browsers: bool = False,
        endpoint: str | None = None,
        tunnel_mode: str = TunnelMode.SPLIT,
    ) -> str:
        """Generate WireGuard config content as string."""
        endpoint_type = endpoint or "standard"
        return get_config_content(
            self._shell,
            self._logger,
            endpoint_type,
            tunnel_mode,
        )


# Convenience functions
_wireguard_service: WireGuardService | None = None


def get_wireguard_service() -> WireGuardService:
    """Get the global WireGuard service instance."""
    global _wireguard_service
    if _wireguard_service is None:
        _wireguard_service = WireGuardService()
    return _wireguard_service
