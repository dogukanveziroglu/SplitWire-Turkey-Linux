"""
SplitTunnelService - app-based split tunneling for SplitWire Linux.

Uses cgproxy (cgroup-based routing) to route specific applications
through the VPN tunnel while allowing other traffic to bypass it.
This is the Linux equivalent of WireSock's AllowedApps functionality.
"""

import json
import tempfile
from pathlib import Path

from splitwire.services.base import BaseService, ServiceStatus, ServiceType

from .constants import (
    APPS_CONFIG_FILE,
    BROWSER_APPS,
    CGPROXY_CONFIG_DIR,
    CGPROXY_CONFIG_FILE,
    CGPROXY_SERVICE,
    KNOWN_APPS,
    LOCAL_CONFIG_DIR,
)
from .models import SplitTunnelConfig, TunneledApp


class SplitTunnelService(BaseService):
    """
    App-based split tunneling using cgproxy.

    cgproxy uses cgroups v2 to route traffic from specific processes
    through a designated network interface (e.g., WireGuard).
    """

    def __init__(self):
        """Initialize split tunnel service."""
        super().__init__(
            name="split-tunnel",
            display_name="Split Tunneling",
            description="App-based VPN routing via cgproxy",
            service_type=ServiceType.SYSTEM,
        )
        self._config = SplitTunnelConfig()
        self._ensure_directories()
        self._load_config()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> None:
        """Load tunneled apps configuration."""
        if APPS_CONFIG_FILE.exists():
            self._logger.debug(
                f"[TUNNEL] Loading config from {APPS_CONFIG_FILE}"
            )
            try:
                data = json.loads(APPS_CONFIG_FILE.read_text())
                self._config.enabled = data.get("enabled", False)
                self._config.include_browsers = data.get(
                    "include_browsers", False
                )
                self._config.custom_paths = data.get("custom_paths", [])
                self._config.apps = [
                    TunneledApp(
                        name=a.get("name", ""),
                        path=a.get("path", ""),
                        enabled=a.get("enabled", True),
                        is_custom=a.get("is_custom", False),
                    )
                    for a in data.get("apps", [])
                ]
                self._logger.debug(
                    "[TUNNEL] Config loaded: %d apps, "
                    "include_browsers=%s",
                    len(self._config.apps),
                    self._config.include_browsers,
                )
            except Exception as e:
                self._logger.warning(
                    f"[TUNNEL] Failed to load config: {e}"
                )

    def _save_config(self) -> None:
        """Save tunneled apps configuration."""
        self._logger.debug(
            f"[TUNNEL] Saving config to {APPS_CONFIG_FILE}"
        )
        data = {
            "enabled": self._config.enabled,
            "include_browsers": self._config.include_browsers,
            "custom_paths": self._config.custom_paths,
            "apps": [
                {
                    "name": app.name,
                    "path": app.path,
                    "enabled": app.enabled,
                    "is_custom": app.is_custom,
                }
                for app in self._config.apps
            ],
        }
        APPS_CONFIG_FILE.write_text(json.dumps(data, indent=2))
        self._logger.debug(
            f"[TUNNEL] Config saved: {len(self._config.apps)} apps"
        )

    # -- BaseService implementation --

    def install(
        self,
        apps: list[str] | None = None,
        include_browsers: bool = False,
        interface: str = "splitwire",
        **kwargs,
    ) -> bool:
        """Install and configure split tunneling."""
        self._logger.info("Installing split tunneling")
        self._notify_status_change(ServiceStatus.INSTALLING)

        try:
            if not self._check_dependencies():
                return False

            tunnel_apps = build_app_list(apps, include_browsers)
            if not tunnel_apps:
                self._logger.warning("No apps to tunnel")
                return False

            if not self._generate_cgproxy_config(tunnel_apps, interface):
                return False
            if not self.start():
                return False

            self._config.enabled = True
            self._config.include_browsers = include_browsers
            self._config.apps = tunnel_apps
            self._save_config()

            self._logger.info("Split tunneling installed successfully")
            return True

        except Exception as e:
            self._logger.exception(f"Installation failed: {e}")
            self._notify_status_change(ServiceStatus.FAILED)
            return False

    def remove(self) -> bool:
        """Remove split tunneling configuration."""
        self._logger.info("Removing split tunneling")
        try:
            if self.is_running():
                self.stop()
            if CGPROXY_CONFIG_FILE.exists():
                result = self._run_privileged(
                    ["rm", "-f", str(CGPROXY_CONFIG_FILE)]
                )
                if not result.success:
                    self._logger.warning(
                        f"Failed to remove config: {result.stderr}"
                    )
            self._config.enabled = False
            self._save_config()
            self._logger.info("Split tunneling removed")
            self._notify_status_change(ServiceStatus.NOT_INSTALLED)
            return True
        except Exception as e:
            self._logger.exception(f"Removal failed: {e}")
            return False

    def start(self) -> bool:
        """Start cgproxy service."""
        self._logger.info("Starting cgproxy")
        result = self._run_privileged(
            ["systemctl", "start", CGPROXY_SERVICE], timeout=30
        )
        if result.success:
            self._logger.info("cgproxy started")
            self._notify_status_change(ServiceStatus.RUNNING)
            return True
        self._logger.error(
            f"Failed to start cgproxy: {result.stderr}"
        )
        self._notify_status_change(ServiceStatus.FAILED)
        return False

    def stop(self) -> bool:
        """Stop cgproxy service."""
        self._logger.info("Stopping cgproxy")
        result = self._run_privileged(
            ["systemctl", "stop", CGPROXY_SERVICE], timeout=30
        )
        if result.success:
            self._logger.info("cgproxy stopped")
            self._notify_status_change(ServiceStatus.STOPPED)
            return True
        self._logger.error(
            f"Failed to stop cgproxy: {result.stderr}"
        )
        return False

    def status(self) -> ServiceStatus:
        """Get cgproxy service status."""
        if not self.is_installed():
            return ServiceStatus.NOT_INSTALLED
        result = self._shell.run(
            ["systemctl", "is-active", CGPROXY_SERVICE], timeout=10
        )
        stdout = result.stdout.strip().lower()
        if stdout == "active":
            return ServiceStatus.RUNNING
        if stdout == "inactive":
            return ServiceStatus.STOPPED
        if stdout == "failed":
            return ServiceStatus.FAILED
        return ServiceStatus.UNKNOWN

    def is_installed(self) -> bool:
        """Check if cgproxy is configured."""
        return CGPROXY_CONFIG_FILE.exists() and self._config.enabled

    # -- Split tunnel specific methods --

    def get_known_apps(self) -> dict[str, list[str]]:
        """Get dictionary of known apps and their paths."""
        return KNOWN_APPS.copy()

    def get_available_apps(self) -> list[TunneledApp]:
        """Get list of apps available for tunneling (installed)."""
        self._logger.debug(
            "[TUNNEL] Discovering available apps on system..."
        )
        available = []
        for app_name, paths in KNOWN_APPS.items():
            for path in paths:
                if Path(path).exists():
                    available.append(
                        TunneledApp(
                            name=app_name, path=path,
                            enabled=False, is_custom=False,
                        )
                    )
                    self._logger.debug(
                        f"[TUNNEL] Found app: {app_name} at {path}"
                    )
                    break
        self._logger.info(
            f"[TUNNEL] Discovered {len(available)} available apps"
        )
        return available

    def get_tunneled_apps(self) -> list[TunneledApp]:
        """Get list of currently tunneled apps."""
        return [app for app in self._config.apps if app.enabled]

    def add_custom_app(self, name: str, path: str) -> bool:
        """Add a custom app to tunnel list."""
        self._logger.debug(
            f"[TUNNEL] Adding custom app: {name} ({path})"
        )
        if not Path(path).exists():
            self._logger.error(
                f"[TUNNEL] Path does not exist: {path}"
            )
            return False
        for app in self._config.apps:
            if app.path == path:
                self._logger.info(
                    f"[TUNNEL] App already in list: {path}"
                )
                return True
        self._config.apps.append(
            TunneledApp(
                name=name, path=path, enabled=True, is_custom=True,
            )
        )
        self._config.custom_paths.append(path)
        self._save_config()
        self._logger.info(
            f"[TUNNEL] Added custom app: {name} ({path})"
        )
        return True

    def remove_custom_app(self, path: str) -> bool:
        """Remove a custom app from tunnel list."""
        self._config.apps = [
            app for app in self._config.apps if app.path != path
        ]
        if path in self._config.custom_paths:
            self._config.custom_paths.remove(path)
        self._save_config()
        return True

    def set_include_browsers(self, include: bool) -> None:
        """Set whether to include browsers in tunneling."""
        self._config.include_browsers = include
        self._save_config()

    def configure(
        self,
        apps: list[str] | None = None,
        include_browsers: bool = False,
        interface: str = "splitwire",
    ) -> bool:
        """Configure split tunneling (wrapper for install)."""
        return self.install(
            apps=apps,
            include_browsers=include_browsers,
            interface=interface,
        )

    def run_app_through_tunnel(
        self, app_path: str, args: list[str] | None = None
    ) -> bool:
        """Run an application through the tunnel using cgproxy."""
        if not self._check_binary_exists("cgproxy"):
            self._logger.error("cgproxy not installed")
            return False
        cmd = ["cgproxy", app_path]
        if args:
            cmd.extend(args)
        result = self._shell.run(cmd, timeout=5)
        return result.success

    # -- Helper methods --

    def _check_dependencies(self) -> bool:
        """Check required dependencies are installed."""
        if not self._check_binary_exists("cgproxy"):
            self._logger.error("cgproxy not installed")
            self._logger.info("Install with: sudo apt install cgproxy")
            self._logger.info(
                "Or from: https://github.com/springzfx/cgproxy"
            )
            return False
        if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
            self._logger.error("cgroups v2 not available")
            self._logger.info("Ensure your system uses cgroups v2")
            return False
        return True

    def _generate_cgproxy_config(
        self, apps: list[TunneledApp], interface: str
    ) -> bool:
        """Generate cgproxy configuration file."""
        config = {
            "comment": "Generated by SplitWire",
            "port": 0,
            "program_noproxy": [],
            "program_proxy": [
                app.path for app in apps if app.enabled
            ],
            "cgroup_noproxy": ["/"],
            "cgroup_proxy": [],
            "enable_gateway": False,
            "enable_dns": True,
            "enable_udp": True,
            "enable_tcp": True,
            "enable_ipv6": True,
            "table": 10007,
            "fwmark": 0x9973,
            "cgroup_root": "/sys/fs/cgroup",
        }
        config_content = json.dumps(config, indent=2)

        result = self._run_privileged(
            ["mkdir", "-p", str(CGPROXY_CONFIG_DIR)]
        )
        if not result.success:
            self._logger.error(
                f"Failed to create config dir: {result.stderr}"
            )
            return False

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = self._run_privileged(
                ["cp", temp_path, str(CGPROXY_CONFIG_FILE)]
            )
            if not result.success:
                self._logger.error(
                    f"Failed to write config: {result.stderr}"
                )
                return False
            self._run_privileged(
                ["chmod", "644", str(CGPROXY_CONFIG_FILE)]
            )
            return True
        finally:
            Path(temp_path).unlink(missing_ok=True)


# ============================================================================
# Module-level helpers for building app lists
# ============================================================================


def build_app_list(
    apps: list[str] | None, include_browsers: bool
) -> list[TunneledApp]:
    """Build list of apps to tunnel."""
    result: list[TunneledApp] = []
    added_paths: set[str] = set()

    if apps:
        _add_requested_apps(apps, result, added_paths)
    if include_browsers:
        _add_browser_apps(result, added_paths)
    _add_discord_if_missing(result, added_paths)
    return result


def _add_requested_apps(
    apps: list[str],
    result: list[TunneledApp],
    added_paths: set[str],
) -> None:
    """Add explicitly requested apps to the list."""
    for app in apps:
        if app in KNOWN_APPS:
            for path in KNOWN_APPS[app]:
                if Path(path).exists() and path not in added_paths:
                    result.append(
                        TunneledApp(
                            name=app, path=path,
                            enabled=True, is_custom=False,
                        )
                    )
                    added_paths.add(path)
                    break
        elif Path(app).exists() and app not in added_paths:
            result.append(
                TunneledApp(
                    name=Path(app).stem, path=app,
                    enabled=True, is_custom=True,
                )
            )
            added_paths.add(app)


def _add_browser_apps(
    result: list[TunneledApp],
    added_paths: set[str],
) -> None:
    """Add browser apps to the list."""
    for browser in BROWSER_APPS:
        if browser in KNOWN_APPS:
            for path in KNOWN_APPS[browser]:
                if Path(path).exists() and path not in added_paths:
                    result.append(
                        TunneledApp(
                            name=browser, path=path,
                            enabled=True, is_custom=False,
                        )
                    )
                    added_paths.add(path)
                    break


def _add_discord_if_missing(
    result: list[TunneledApp],
    added_paths: set[str],
) -> None:
    """Always add Discord if available and not already in list."""
    if "discord" not in [app.name for app in result]:
        for path in KNOWN_APPS.get("discord", []):
            if Path(path).exists() and path not in added_paths:
                result.append(
                    TunneledApp(
                        name="discord", path=path,
                        enabled=True, is_custom=False,
                    )
                )
                break
