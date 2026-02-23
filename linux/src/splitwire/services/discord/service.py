"""Discord repair and management service for SplitWire Linux."""

import json
import shutil
import time
from datetime import datetime

from splitwire.services.base import BaseService, ServiceStatus, ServiceType

from .constants import (
    CONFIG_FILE,
    DISCORD_BINARIES,
    DISCORD_CACHE_DIRS,
    DISCORD_CONFIG_DIRS,
    LOCAL_CONFIG_DIR,
)
from .detection import (
    detect_version,
    detect_webcord,
    get_dir_size_mb,
    is_discord_running,
)
from .install import (
    install_discord,
    install_webcord,
    launch_discord,
    launch_webcord,
    reinstall_deb,
    reinstall_flatpak,
    reinstall_snap,
    uninstall_discord,
    uninstall_webcord,
)
from .models import (
    DiscordConfig,
    DiscordInstallation,
    DiscordVersion,
    InstallMethod,
    RepairResult,
    WebCordInstallation,
)


class DiscordService(BaseService):
    """
    Discord repair and management service.

    Provides detection, repair, cache clearing, and alternative client support
    for Discord Stable, PTB, Canary, and WebCord.
    """

    # Discord-specific timeouts (seconds)
    TIMEOUT_PROCESS_KILL = 5  # pkill operations

    def __init__(self):
        """Initialize Discord service."""
        super().__init__(
            name="discord",
            display_name="Discord Repair",
            description="Discord detection, repair, and alternative clients",
            service_type=ServiceType.SYSTEM,
        )
        self._config = DiscordConfig()
        self._installations: dict[DiscordVersion, DiscordInstallation] = {}
        self._webcord: WebCordInstallation | None = None
        self._ensure_directories()
        self._load_config()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text())
            self._config = DiscordConfig(
                last_repair_date=data.get("last_repair_date"),
                auto_clear_cache=data.get("auto_clear_cache", False),
                preferred_version=data.get("preferred_version", "stable"),
            )
        except Exception as e:
            self._logger.warning("Failed to load config: %s", e)

    def _save_config(self) -> None:
        """Save configuration to file."""
        data = {
            "last_repair_date": self._config.last_repair_date,
            "auto_clear_cache": self._config.auto_clear_cache,
            "preferred_version": self._config.preferred_version,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    def install(self, version: str = "stable", **kwargs) -> bool:
        """Install Discord version."""
        try:
            dv = DiscordVersion(version.lower())
        except ValueError:
            self._logger.error("Invalid Discord version: %s", version)
            return False
        return install_discord(self, dv)

    def remove(self) -> bool:
        """Remove is not applicable for Discord service."""
        self._logger.info("Use uninstall_discord() for specific version removal")
        return True

    def start(self) -> bool:
        """Launch Discord."""
        return launch_discord(self, DiscordVersion.STABLE)

    def stop(self) -> bool:
        """Stop/kill Discord processes."""
        return self.kill_discord()

    def status(self) -> ServiceStatus:
        """Get Discord status."""
        self.detect_all()
        has_installed = any(
            inst.method != InstallMethod.NOT_INSTALLED for inst in self._installations.values()
        )
        if not has_installed:
            return ServiceStatus.NOT_INSTALLED
        has_running = any(inst.is_running for inst in self._installations.values())
        return ServiceStatus.RUNNING if has_running else ServiceStatus.STOPPED

    def is_installed(self) -> bool:
        """Check if any Discord version is installed."""
        self.detect_all()
        return any(
            inst.method != InstallMethod.NOT_INSTALLED for inst in self._installations.values()
        )

    def detect_all(self) -> dict[DiscordVersion, DiscordInstallation]:
        """Detect all Discord installations."""
        self._logger.info("[DISCORD] Detecting all Discord installations...")
        for version in DiscordVersion:
            self._installations[version] = self._detect_version(version)
            inst = self._installations[version]
            if inst.method != InstallMethod.NOT_INSTALLED:
                self._logger.debug(
                    "[DISCORD] Found %s: method=%s",
                    version.value,
                    inst.method.value,
                )
        self._webcord = self._detect_webcord()
        if self._webcord.installed:
            self._logger.debug(
                "[DISCORD] Found WebCord: method=%s",
                self._webcord.method.value,
            )
        installed_count = sum(
            1 for i in self._installations.values() if i.method != InstallMethod.NOT_INSTALLED
        )
        self._logger.info(
            "[DISCORD] Detection complete: %d Discord versions found",
            installed_count,
        )
        return self._installations.copy()

    def _detect_version(self, version: DiscordVersion) -> DiscordInstallation:
        """Detect a specific Discord version."""
        return detect_version(self, version)

    def _detect_webcord(self) -> WebCordInstallation:
        """Detect WebCord installation."""
        return detect_webcord(self)

    def _is_discord_running(self, version: DiscordVersion) -> bool:
        """Check if Discord version is running."""
        return is_discord_running(self, version)

    def repair_discord(
        self,
        version: DiscordVersion = DiscordVersion.STABLE,
        clear_cache: bool = True,
        reinstall: bool = False,
    ) -> RepairResult:
        """Repair Discord installation."""
        self._logger.info("Repairing Discord %s", version.value)
        errors: list[str] = []
        cache_cleared = 0.0

        if self._is_discord_running(version):
            self._logger.info("Stopping Discord...")
            self._kill_discord_version(version)

        if clear_cache:
            cache_result = self.clear_cache(version)
            if cache_result.success:
                cache_cleared = cache_result.cache_cleared_mb
            else:
                errors.extend(cache_result.errors)

        self._remove_corrupt_files(version, errors)

        if reinstall:
            self._handle_reinstall(version, errors)

        self._config.last_repair_date = datetime.now().isoformat()
        self._save_config()

        success = len(errors) == 0
        message = (
            "Repair completed successfully"
            if success
            else f"Repair completed with {len(errors)} error(s)"
        )
        return RepairResult(
            success=success,
            message=message,
            cache_cleared_mb=cache_cleared,
            errors=errors,
        )

    def _remove_corrupt_files(self, version: DiscordVersion, errors: list[str]) -> None:
        """Remove potentially corrupted config subdirectories."""
        config_dir = DISCORD_CONFIG_DIRS.get(version.value)
        if not config_dir or not config_dir.exists():
            return
        for name in ["GPUCache", "Code Cache", "Crashpad"]:
            cf = config_dir / name
            if cf.exists():
                try:
                    shutil.rmtree(cf)
                    self._logger.info("Removed: %s", cf)
                except Exception as e:
                    errors.append(f"Failed to remove {cf}: {e}")

    def _handle_reinstall(self, version: DiscordVersion, errors: list[str]) -> None:
        """Reinstall Discord via the detected method."""
        installation = self._detect_version(version)
        method_handlers = {
            InstallMethod.DEB: (reinstall_deb, "Discord DEB package"),
            InstallMethod.FLATPAK: (reinstall_flatpak, "Discord Flatpak"),
            InstallMethod.SNAP: (reinstall_snap, "Discord Snap"),
        }
        handler = method_handlers.get(installation.method)
        if handler:
            func, label = handler
            if not func(self, version):
                errors.append(f"Failed to reinstall {label}")

    def clear_cache(self, version: DiscordVersion = DiscordVersion.STABLE) -> RepairResult:
        """Clear Discord cache."""
        self._logger.info("Clearing cache for Discord %s", version.value)
        errors: list[str] = []
        total_cleared = 0.0

        total_cleared += self._clear_cache_dir(version, errors)
        total_cleared += self._clear_config_cache(version, errors)

        success = len(errors) == 0
        message = f"Cleared {total_cleared:.1f} MB of cache" if success else "Cache had errors"
        return RepairResult(
            success=success,
            message=message,
            cache_cleared_mb=total_cleared,
            errors=errors,
        )

    def _clear_cache_dir(self, version: DiscordVersion, errors: list[str]) -> float:
        """Clear the main cache directory for a version."""
        cache_dir = DISCORD_CACHE_DIRS.get(version.value)
        if not cache_dir or not cache_dir.exists():
            return 0.0
        size = get_dir_size_mb(cache_dir)
        try:
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._logger.info("Cleared %.1f MB from %s", size, cache_dir)
            return size
        except Exception as e:
            errors.append(f"Failed to clear cache dir: {e}")
            return 0.0

    def _clear_config_cache(self, version: DiscordVersion, errors: list[str]) -> float:
        """Clear cache subdirectories inside config dir."""
        config_dir = DISCORD_CONFIG_DIRS.get(version.value)
        if not config_dir or not config_dir.exists():
            return 0.0
        total = 0.0
        for subdir in ["Cache", "GPUCache", "Code Cache", "blob_storage"]:
            subdir_path = config_dir / subdir
            if subdir_path.exists():
                size = get_dir_size_mb(subdir_path)
                try:
                    shutil.rmtree(subdir_path)
                    total += size
                    self._logger.info("Cleared %.1f MB from %s", size, subdir_path)
                except Exception as e:
                    errors.append(f"Failed to clear {subdir}: {e}")
        return total

    def clear_all_cache(self) -> RepairResult:
        """Clear cache for all Discord versions."""
        total_cleared = 0.0
        all_errors: list[str] = []
        for version in DiscordVersion:
            result = self.clear_cache(version)
            total_cleared += result.cache_cleared_mb
            all_errors.extend(result.errors)
        return RepairResult(
            success=len(all_errors) == 0,
            message=f"Cleared {total_cleared:.1f} MB total",
            cache_cleared_mb=total_cleared,
            errors=all_errors,
        )

    def install_discord(
        self,
        version: DiscordVersion = DiscordVersion.STABLE,
        method: InstallMethod = InstallMethod.DEB,
    ) -> bool:
        """Install Discord."""
        return install_discord(self, version, method)

    def uninstall_discord(self, version: DiscordVersion) -> bool:
        """Uninstall Discord."""
        return uninstall_discord(self, version)

    def install_webcord(
        self,
        method: InstallMethod = InstallMethod.FLATPAK,
        create_shortcut: bool = True,
    ) -> bool:
        """Install WebCord."""
        return install_webcord(self, method)

    def uninstall_webcord(self) -> bool:
        """Uninstall WebCord."""
        return uninstall_webcord(self)

    def launch_discord(self, version: DiscordVersion = DiscordVersion.STABLE) -> bool:
        """Launch Discord."""
        return launch_discord(self, version)

    def launch_webcord(self) -> bool:
        """Launch WebCord."""
        return launch_webcord(self)

    def kill_discord(self, version: DiscordVersion | None = None) -> bool:
        """Kill Discord process(es)."""
        if version:
            return self._kill_discord_version(version)
        return all(self._kill_discord_version(v) for v in DiscordVersion)

    def _kill_discord_version(self, version: DiscordVersion) -> bool:
        """Kill specific Discord version."""
        binaries = DISCORD_BINARIES.get(version.value, [])
        for binary in binaries:
            self._shell.run(["pkill", "-f", binary], timeout=self.TIMEOUT_PROCESS_KILL)
        time.sleep(1)
        return not self._is_discord_running(version)

    def get_config(self) -> DiscordConfig:
        """Get current configuration."""
        return self._config

    def get_installations(self) -> dict[DiscordVersion, DiscordInstallation]:
        """Get all detected installations."""
        self.detect_all()
        return self._installations.copy()

    def get_installation(self, version: DiscordVersion) -> DiscordInstallation:
        """Get specific installation info."""
        return self._detect_version(version)

    def get_webcord(self) -> WebCordInstallation:
        """Get WebCord installation info."""
        return self._detect_webcord()

    def get_total_cache_size(self) -> float:
        """Get total cache size for all Discord versions in MB."""
        total = 0.0
        for version in DiscordVersion:
            cache_dir = DISCORD_CACHE_DIRS.get(version.value)
            if cache_dir and cache_dir.exists():
                total += get_dir_size_mb(cache_dir)
            config_dir = DISCORD_CONFIG_DIRS.get(version.value)
            if config_dir and config_dir.exists():
                for subdir in ["Cache", "GPUCache", "Code Cache"]:
                    subdir_path = config_dir / subdir
                    if subdir_path.exists():
                        total += get_dir_size_mb(subdir_path)
        return total

    def set_preferred_version(self, version: str) -> None:
        """Set preferred Discord version."""
        self._config.preferred_version = version
        self._save_config()

    def set_auto_clear_cache(self, enabled: bool) -> None:
        """Set auto clear cache option."""
        self._config.auto_clear_cache = enabled
        self._save_config()


_discord_service: DiscordService | None = None


def get_discord_service() -> DiscordService:
    """Get the global Discord service instance."""
    global _discord_service
    if _discord_service is None:
        _discord_service = DiscordService()
    return _discord_service
