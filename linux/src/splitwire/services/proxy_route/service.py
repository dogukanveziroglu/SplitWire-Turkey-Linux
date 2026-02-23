"""
ProxyRouteService - app-based proxy routing for SplitWire Linux.

Routes specific applications through a SOCKS5 proxy (e.g., ByeDPI).
Uses cgproxy or redsocks for transparent proxying.
This is the Linux equivalent of ProxiFyre on Windows.
"""

import json
from pathlib import Path

from splitwire.services.base import BaseService, ServiceStatus, ServiceType
from splitwire.services.split_tunnel import BROWSER_APPS, KNOWN_APPS

from . import backends
from .constants import (
    DEFAULT_PROXY_HOST,
    DEFAULT_PROXY_PORT,
    LOCAL_CONFIG_DIR,
    PROXY_ROUTE_CONFIG_FILE,
    REDSOCKS_SERVICE,
)
from .models import ProxiedApp, ProxyMethod, ProxyRouteConfig


class ProxyRouteService(BaseService):
    """
    App-based proxy routing service.

    Routes specific applications through a SOCKS5 proxy using either:
    - cgproxy: cgroup-based routing (clean, recommended)
    - redsocks: iptables-based transparent proxy redirect
    """

    def __init__(self):
        """Initialize proxy route service."""
        super().__init__(
            name="proxy-route",
            display_name="Proxy Routing",
            description="App-based proxy routing for ByeDPI",
            service_type=ServiceType.SYSTEM,
        )
        self._config = ProxyRouteConfig()
        self._ensure_directories()
        self._load_config()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> None:
        """Load configuration from file."""
        if PROXY_ROUTE_CONFIG_FILE.exists():
            self._logger.debug(
                f"[PROXY] Loading config from {PROXY_ROUTE_CONFIG_FILE}"
            )
            try:
                data = json.loads(PROXY_ROUTE_CONFIG_FILE.read_text())
                self._config = self._parse_config_data(data)
                self._logger.debug(
                    "[PROXY] Config loaded: proxy=%s:%s, method=%s",
                    self._config.proxy_host,
                    self._config.proxy_port,
                    self._config.method.value,
                )
            except Exception as e:
                self._logger.warning(
                    f"[PROXY] Failed to load config: {e}"
                )

    @staticmethod
    def _parse_config_data(data: dict) -> ProxyRouteConfig:
        """Parse configuration dict into ProxyRouteConfig."""
        config = ProxyRouteConfig(
            enabled=data.get("enabled", False),
            method=ProxyMethod(data.get("method", "cgproxy")),
            proxy_host=data.get("proxy_host", DEFAULT_PROXY_HOST),
            proxy_port=data.get("proxy_port", DEFAULT_PROXY_PORT),
            include_browsers=data.get("include_browsers", False),
            custom_paths=data.get("custom_paths", []),
        )
        for app_data in data.get("apps", []):
            config.apps.append(
                ProxiedApp(
                    name=app_data.get("name", ""),
                    path=app_data.get("path", ""),
                    enabled=app_data.get("enabled", True),
                    is_custom=app_data.get("is_custom", False),
                )
            )
        return config

    def _save_config(self) -> None:
        """Save configuration to file."""
        self._logger.debug(
            f"[PROXY] Saving config to {PROXY_ROUTE_CONFIG_FILE}"
        )
        data = {
            "enabled": self._config.enabled,
            "method": self._config.method.value,
            "proxy_host": self._config.proxy_host,
            "proxy_port": self._config.proxy_port,
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
        PROXY_ROUTE_CONFIG_FILE.write_text(json.dumps(data, indent=2))
        self._logger.debug(
            f"[PROXY] Config saved: {len(self._config.apps)} apps"
        )

    # =========================================================================
    # BaseService implementation
    # =========================================================================

    def install(
        self,
        apps: list[str] | None = None,
        include_browsers: bool = False,
        proxy_host: str = DEFAULT_PROXY_HOST,
        proxy_port: int = DEFAULT_PROXY_PORT,
        method: ProxyMethod = ProxyMethod.CGPROXY,
        **kwargs,
    ) -> bool:
        """Install and configure proxy routing."""
        self._logger.info(
            f"Installing proxy routing via {method.value}"
        )
        self._notify_status_change(ServiceStatus.INSTALLING)

        try:
            if not self._check_dependencies(method):
                return False

            self._config.proxy_host = proxy_host
            self._config.proxy_port = proxy_port
            self._config.method = method
            self._config.include_browsers = include_browsers

            proxy_apps = self._build_app_list(apps, include_browsers)
            if not proxy_apps:
                self._logger.warning("No apps to route")
                return False

            self._config.apps = proxy_apps
            app_paths = [a.path for a in proxy_apps if a.enabled]

            if method == ProxyMethod.CGPROXY:
                if not backends.setup_cgproxy(
                    self._run_privileged,
                    proxy_host, proxy_port, app_paths,
                ):
                    return False
            elif (
                method == ProxyMethod.REDSOCKS
                and not backends.setup_redsocks(
                    self._run_privileged, proxy_host, proxy_port
                )
            ):
                return False

            self._config.enabled = True
            self._save_config()
            self._logger.info("Proxy routing installed successfully")
            return True

        except Exception as e:
            self._logger.exception(f"Installation failed: {e}")
            self._notify_status_change(ServiceStatus.FAILED)
            return False

    def remove(self) -> bool:
        """Remove proxy routing configuration."""
        self._logger.info("Removing proxy routing")
        try:
            if self.is_running():
                self.stop()

            if self._config.method == ProxyMethod.CGPROXY:
                backends.cleanup_cgproxy(self._run_privileged)
            elif self._config.method == ProxyMethod.REDSOCKS:
                backends.cleanup_redsocks(self._run_privileged)

            self._config.enabled = False
            self._save_config()
            self._logger.info("Proxy routing removed")
            self._notify_status_change(ServiceStatus.NOT_INSTALLED)
            return True

        except Exception as e:
            self._logger.exception(f"Removal failed: {e}")
            return False

    def start(self) -> bool:
        """Start proxy routing."""
        self._logger.info("Starting proxy routing")
        if self._config.method == ProxyMethod.REDSOCKS:
            result = self._run_privileged(
                ["systemctl", "start", REDSOCKS_SERVICE], timeout=30
            )
            if result.success:
                backends.add_iptables_rules(self._run_privileged)
            else:
                self._logger.error(
                    f"Failed to start redsocks: {result.stderr}"
                )
                return False

        self._notify_status_change(ServiceStatus.RUNNING)
        return True

    def stop(self) -> bool:
        """Stop proxy routing."""
        self._logger.info("Stopping proxy routing")
        if self._config.method == ProxyMethod.REDSOCKS:
            backends.remove_iptables_rules(self._run_privileged)
            self._run_privileged(
                ["systemctl", "stop", REDSOCKS_SERVICE], timeout=30
            )
        self._notify_status_change(ServiceStatus.STOPPED)
        return True

    def status(self) -> ServiceStatus:
        """Get proxy routing status."""
        if not self.is_installed():
            return ServiceStatus.NOT_INSTALLED
        if self._config.method == ProxyMethod.REDSOCKS:
            result = self._shell.run(
                ["systemctl", "is-active", REDSOCKS_SERVICE], timeout=10
            )
            if result.stdout.strip().lower() == "active":
                return ServiceStatus.RUNNING
            return ServiceStatus.STOPPED
        if self._config.enabled:
            return ServiceStatus.RUNNING
        return ServiceStatus.STOPPED

    def is_installed(self) -> bool:
        """Check if proxy routing is configured."""
        return self._config.enabled

    # =========================================================================
    # Proxy route specific methods
    # =========================================================================

    def get_config(self) -> ProxyRouteConfig:
        """Get current configuration."""
        return self._config

    def get_available_apps(self) -> list[ProxiedApp]:
        """Get list of apps available for proxy routing."""
        available = []
        for app_name, paths in KNOWN_APPS.items():
            for path in paths:
                if Path(path).exists():
                    available.append(
                        ProxiedApp(
                            name=app_name, path=path,
                            enabled=False, is_custom=False,
                        )
                    )
                    break
        return available

    def get_proxied_apps(self) -> list[ProxiedApp]:
        """Get list of currently proxied apps."""
        return [app for app in self._config.apps if app.enabled]

    def add_custom_app(self, name: str, path: str) -> bool:
        """Add a custom app to proxy list."""
        if not Path(path).exists():
            self._logger.error(f"Path does not exist: {path}")
            return False

        for app in self._config.apps:
            if app.path == path:
                self._logger.info(f"App already in list: {path}")
                return True

        self._config.apps.append(
            ProxiedApp(
                name=name, path=path, enabled=True, is_custom=True,
            )
        )
        self._config.custom_paths.append(path)
        self._save_config()
        return True

    def remove_custom_app(self, path: str) -> bool:
        """Remove a custom app from proxy list."""
        self._config.apps = [
            app for app in self._config.apps if app.path != path
        ]
        if path in self._config.custom_paths:
            self._config.custom_paths.remove(path)
        self._save_config()
        return True

    def set_proxy(self, host: str, port: int) -> None:
        """Set proxy server address."""
        self._logger.info(
            f"[PROXY] Setting proxy address: {host}:{port}"
        )
        self._config.proxy_host = host
        self._config.proxy_port = port
        self._save_config()

    def configure(
        self,
        apps: list[str] | None = None,
        include_browsers: bool = False,
        proxy_host: str | None = None,
        proxy_port: int | None = None,
    ) -> bool:
        """Configure proxy routing (wrapper for install)."""
        return self.install(
            apps=apps,
            include_browsers=include_browsers,
            proxy_host=proxy_host or self._config.proxy_host,
            proxy_port=proxy_port or self._config.proxy_port,
            method=self._config.method,
        )

    def run_app_through_proxy(
        self, app_path: str, args: list[str] | None = None
    ) -> bool:
        """Run an application through the proxy."""
        if self._config.method == ProxyMethod.CGPROXY:
            return backends.run_via_cgproxy(self._shell, app_path, args)
        if self._config.method == ProxyMethod.ENV:
            return backends.run_via_env(
                self._config.proxy_host,
                self._config.proxy_port,
                app_path,
                args,
            )
        self._logger.warning(
            "Run through proxy only supported for cgproxy/env"
        )
        return False

    # =========================================================================
    # Helper methods
    # =========================================================================

    def _check_dependencies(self, method: ProxyMethod) -> bool:
        """Check required dependencies."""
        if method == ProxyMethod.CGPROXY:
            if not self._shell.command_exists("cgproxy"):
                self._logger.error("cgproxy not installed")
                self._logger.info(
                    "Install from: https://github.com/springzfx/cgproxy"
                )
                return False
            if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
                self._logger.error("cgroups v2 not available")
                return False

        elif method == ProxyMethod.REDSOCKS:
            if not self._shell.command_exists("redsocks"):
                self._logger.error("redsocks not installed")
                self._logger.info(
                    "Install with: sudo apt install redsocks"
                )
                return False

        return True

    def _build_app_list(
        self, apps: list[str] | None, include_browsers: bool,
    ) -> list[ProxiedApp]:
        """Build list of apps to route through proxy."""
        result: list[ProxiedApp] = []
        added_paths: set[str] = set()

        if apps:
            _add_requested_apps(apps, result, added_paths)
        if include_browsers:
            _add_browser_apps(result, added_paths)
        _add_discord_if_missing(result, added_paths)
        return result


def _add_requested_apps(
    apps: list[str],
    result: list[ProxiedApp],
    added_paths: set[str],
) -> None:
    """Add explicitly requested apps to the list."""
    for app in apps:
        if app in KNOWN_APPS:
            for path in KNOWN_APPS[app]:
                if Path(path).exists() and path not in added_paths:
                    result.append(
                        ProxiedApp(
                            name=app, path=path,
                            enabled=True, is_custom=False,
                        )
                    )
                    added_paths.add(path)
                    break
        elif Path(app).exists() and app not in added_paths:
            result.append(
                ProxiedApp(
                    name=Path(app).stem, path=app,
                    enabled=True, is_custom=True,
                )
            )
            added_paths.add(app)


def _add_browser_apps(
    result: list[ProxiedApp],
    added_paths: set[str],
) -> None:
    """Add browser apps to the list."""
    for browser in BROWSER_APPS:
        if browser in KNOWN_APPS:
            for path in KNOWN_APPS[browser]:
                if Path(path).exists() and path not in added_paths:
                    result.append(
                        ProxiedApp(
                            name=browser, path=path,
                            enabled=True, is_custom=False,
                        )
                    )
                    added_paths.add(path)
                    break


def _add_discord_if_missing(
    result: list[ProxiedApp],
    added_paths: set[str],
) -> None:
    """Always add Discord if available and not already in list."""
    if "discord" not in [app.name for app in result]:
        for path in KNOWN_APPS.get("discord", []):
            if Path(path).exists() and path not in added_paths:
                result.append(
                    ProxiedApp(
                        name="discord", path=path,
                        enabled=True, is_custom=False,
                    )
                )
                break
