"""
Main Page (WireGuard/WireSock) for SplitWire-Turkey.

Provides WireGuard VPN setup with split tunneling support.
Equivalent to Windows "Ana Sayfa" tab.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk

from splitwire.core import get_config, get_text
from splitwire.services import (
    KNOWN_APPS,
    ServiceStatus,
    get_dns_service,
    get_split_tunnel_service,
    get_wireguard_service,
)
from splitwire.services.wireguard import TunnelMode

from .base_page import BasePage
from .main_page_helpers import (
    do_disconnect,
    do_remove_services,
    do_wireguard_setup,
    load_page_settings,
    save_page_settings,
)

if TYPE_CHECKING:
    from splitwire.ui.window import SplitWireWindow


class MainPage(BasePage):
    """WireGuard/WireSock setup page."""

    def __init__(self, window: "SplitWireWindow") -> None:
        """Initialize main page with VPN service references.

        Args:
            window: Parent application window.
        """
        self._wg_service = get_wireguard_service()
        self._st_service = get_split_tunnel_service()
        self._dns_service = get_dns_service()
        config = get_config()
        self._custom_apps: list[str] = list(config.wireguard.custom_apps or [])
        self._enabled_apps: dict[str, bool] = dict.fromkeys(KNOWN_APPS.keys(), True)
        super().__init__(window)

    def _build_ui(self) -> None:
        """Build the main page UI."""
        self._build_status_section()
        self._build_action_buttons()
        self._build_options_section()
        self._build_footer()
        self._load_settings()
        self._update_status_indicator()

    def _build_status_section(self) -> None:
        """Build the connection status indicator."""
        self._status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=8,
            margin_bottom=8,
        )
        self.append(self._status_box)

    def _build_action_buttons(self) -> None:
        """Build the main setup/disconnect buttons group."""
        group = self.create_preferences_group(title=get_text("main", "setup"))
        self.append(group)
        self._btn_standard = self.create_action_button(
            label=get_text("main", "standard_setup"),
            callback=self._on_standard_setup,
            tooltip=get_text("tooltips", "standard_install"),
            suggested=True,
        )
        group.add(self._btn_standard)
        self._btn_disconnect = self.create_action_button(
            label=get_text("buttons", "disconnect"),
            callback=self._on_disconnect,
            tooltip=get_text("tooltips", "wireguard_disconnect"),
            destructive=True,
        )
        self._btn_disconnect.set_visible(False)
        group.add(self._btn_disconnect)

    def _build_options_section(self) -> None:
        """Build the options group with switches and expander."""
        group = self.create_preferences_group(title=get_text("main", "options"))
        self.append(group)
        self._switch_browser = self.create_switch_row(
            title=get_text("main", "browser_tunneling"),
            subtitle=get_text("tooltips", "browser_tunneling"),
            active=False,
            callback=self._on_browser_tunneling_changed,
        )
        group.add(self._switch_browser)
        self._switch_full_tunnel = self.create_switch_row(
            title=get_text("main", "full_tunnel"),
            subtitle=get_text("tooltips", "full_tunnel"),
            active=True,
            callback=self._on_full_tunnel_changed,
        )
        group.add(self._switch_full_tunnel)
        self._switch_refresh = self.create_switch_row(
            title=get_text("main", "refresh_timer"),
            subtitle=get_text("tooltips", "wiresock_repeater"),
            active=False,
            callback=self._on_refresh_timer_changed,
        )
        group.add(self._switch_refresh)
        self._advanced_expander = Adw.ExpanderRow(
            title=get_text("main", "folder_customization"),
            subtitle=get_text("tooltips", "folder_customization"),
        )
        group.add(self._advanced_expander)
        self._build_app_list()
        self._build_expander_buttons()

    def _build_expander_buttons(self) -> None:
        """Build folder/config buttons inside advanced expander."""
        custom_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=8,
            margin_bottom=8,
        )
        self._advanced_expander.add_row(Adw.ActionRow(child=custom_box))
        self._btn_add_folder = Gtk.Button(
            label=get_text("main", "add_folder"),
            tooltip_text=get_text("tooltips", "add_folder"),
        )
        self._btn_add_folder.connect("clicked", self._on_add_folder)
        custom_box.append(self._btn_add_folder)
        self._btn_clear = Gtk.Button(
            label=get_text("main", "clear_list"),
            tooltip_text=get_text("tooltips", "clear_list"),
        )
        self._btn_clear.connect("clicked", self._on_clear_list)
        custom_box.append(self._btn_clear)

        adv_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=8,
        )
        self._advanced_expander.add_row(Adw.ActionRow(child=adv_box))
        self._btn_custom = Gtk.Button(
            label=get_text("main", "custom_setup"),
            tooltip_text=get_text("tooltips", "custom_install"),
        )
        self._btn_custom.connect("clicked", self._on_custom_setup)
        adv_box.append(self._btn_custom)
        self._btn_generate = Gtk.Button(
            label=get_text("main", "generate_config"),
            tooltip_text=get_text("tooltips", "generate_config"),
        )
        self._btn_generate.connect("clicked", self._on_generate_config)
        adv_box.append(self._btn_generate)

    def _build_footer(self) -> None:
        """Build remove-service and help buttons."""
        remove_box = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=16)
        self.append(remove_box)
        self._btn_remove = self.create_action_button(
            label=get_text("main", "remove_service"),
            callback=self._on_remove_service,
            destructive=True,
        )
        remove_box.append(self._btn_remove)
        help_box = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.END, vexpand=True)
        self.append(help_box)
        help_box.append(self.create_help_button(self._on_help))

    def _build_app_list(self) -> None:
        """Build app selection list inside the expander."""
        for app_id, paths in KNOWN_APPS.items():
            subtitle = ""
            for path in paths:
                if Path(path).exists():
                    subtitle = path
                    break
            if not subtitle and paths:
                subtitle = paths[0]
            display = app_id.replace("-", " ").replace("_", " ").title()
            row = Adw.ActionRow(title=display, subtitle=subtitle)
            check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
            check.set_name(app_id)
            check.connect("toggled", self._on_app_toggled)
            row.add_prefix(check)
            self._advanced_expander.add_row(row)

    def _update_status_indicator(self) -> None:
        """Update the status indicator and button visibility."""
        while child := self._status_box.get_first_child():
            self._status_box.remove(child)
        try:
            running = self._wg_service.status() == ServiceStatus.RUNNING
        except Exception:
            running = False
        dot_class = "status-running" if running else "status-stopped"
        self._status_box.append(Gtk.Label(label="\u25cf", css_classes=[dot_class]))
        key = "running" if running else "stopped"
        self._status_box.append(Gtk.Label(label=get_text("status", key)))
        self._btn_standard.set_sensitive(not running)
        self._btn_disconnect.set_visible(running)

    def refresh(self) -> None:
        """Refresh page data."""
        self._update_status_indicator()

    def refresh_translations(self) -> None:
        """Refresh UI translations."""
        self._btn_standard.set_label(get_text("main", "standard_setup"))
        self._switch_browser.set_title(get_text("main", "browser_tunneling"))
        self._switch_refresh.set_title(get_text("main", "refresh_timer"))
        self._btn_remove.set_label(get_text("main", "remove_service"))

    def _finish_operation(self, result: object, success_msg: str) -> None:
        """Handle common on_complete pattern for async ops."""
        self._update_status_indicator()
        success, error = result if isinstance(result, tuple) else (result, None)
        if success:
            self.show_toast(success_msg)
        else:
            msg = (
                get_text("messages", "error_generic").format(error)
                if error
                else get_text("status", "error")
            )
            self.show_toast(msg)
        self.set_status("")

    def _on_standard_setup(self, button: object) -> None:
        """Handle standard setup button click."""
        self._logger.info("[UI:Main] Starting standard setup...")
        self.set_status(get_text("status", "installing"))
        tunnel_mode = TunnelMode.FULL if self._switch_full_tunnel.get_active() else TunnelMode.SPLIT

        def task() -> tuple[bool, str | None]:
            """Run WireGuard setup and persist settings on success."""
            result = do_wireguard_setup(self._wg_service, self._dns_service, tunnel_mode)
            if result[0]:
                self._save_settings()
            return result

        self.run_async(
            task,
            lambda r: self._finish_operation(r, get_text("messages", "setup_complete")),
        )

    def _on_disconnect(self, button: object) -> None:
        """Handle disconnect button click."""
        self._logger.info("[UI:Main] Disconnecting VPN...")
        self.set_status(get_text("status", "disconnecting"))
        self.run_async(
            lambda: do_disconnect(self._wg_service, self._dns_service),
            lambda r: self._finish_operation(
                r,
                get_text("messages", "service_stopped").format("WireGuard"),
            ),
        )

    def _on_browser_tunneling_changed(self, row: object, param: object) -> None:
        """Handle browser tunneling switch change."""
        self._logger.info("[UI:Main] Browser tunneling: %s", row.get_active())

    def _on_full_tunnel_changed(self, row: object, param: object) -> None:
        """Handle full tunnel mode switch change."""
        self._logger.info("[UI:Main] Full tunnel: %s", row.get_active())

    def _on_refresh_timer_changed(self, row: object, param: object) -> None:
        """Handle refresh timer switch change."""
        active = row.get_active()
        self._logger.info("[UI:Main] Refresh timer: %s", active)
        if active:
            self._wg_service.enable_refresh_timer()
        else:
            self._wg_service.disable_refresh_timer()

    def _on_app_toggled(self, check: object) -> None:
        """Handle app checkbox toggle."""
        app_id = check.get_name()
        self._enabled_apps[app_id] = check.get_active()
        self._logger.info(
            "[UI:Main] App toggled: %s %s",
            app_id,
            "enabled" if check.get_active() else "disabled",
        )
        self._save_settings()

    def _on_add_folder(self, button: object) -> None:
        """Handle add folder button click."""
        dialog = Gtk.FileDialog(title=get_text("dialogs", "select_folder"))
        dialog.select_folder(self._window, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: object, result: object) -> None:
        """Handle folder selection result."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                if path not in self._custom_apps:
                    self._custom_apps.append(path)
                    self._save_settings()
                    self.show_toast(get_text("messages", "item_added").format(path))
                else:
                    self.show_toast(get_text("messages", "item_exists").format(path))
        except GLib.Error as e:
            if e.code != 2:
                self._logger.error("Folder selection error: %s", e)

    def _on_clear_list(self, button: object) -> None:
        """Handle clear list button click."""
        self._custom_apps.clear()
        self._save_settings()
        self.show_toast(get_text("messages", "list_cleared"))

    def _on_custom_setup(self, button: object) -> None:
        """Handle custom setup button click."""
        self._logger.info("[UI:Main] Starting custom setup...")
        if not self._custom_apps:
            self.show_toast(get_text("messages", "no_custom_apps"))
            return
        self.set_status(get_text("status", "installing"))

        def task() -> tuple[bool, str | None]:
            """Run custom WireGuard setup and persist settings on success."""
            result = do_wireguard_setup(self._wg_service, self._dns_service)
            if result[0]:
                self._save_settings()
            return result

        self.run_async(
            task,
            lambda r: self._finish_operation(r, get_text("messages", "setup_complete")),
        )

    def _on_generate_config(self, button: object) -> None:
        """Handle generate config button click."""
        dialog = Gtk.FileDialog(
            title=get_text("dialogs", "save_config"),
            initial_name="splitwire.conf",
        )
        dialog.save(self._window, None, self._on_config_save_selected)

    def _on_config_save_selected(self, dialog: object, result: object) -> None:
        """Handle config save location selection."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                content = self._wg_service.generate_config_content(
                    include_browsers=self._switch_browser.get_active()
                )
                with open(path, "w") as f:
                    f.write(content)
                self.show_toast(get_text("messages", "config_saved"))
        except GLib.Error as e:
            if e.code != 2:
                self._logger.error("Config save error: %s", e)

    def _on_remove_service(self, button: object) -> None:
        """Handle remove service button click."""
        dialog = Adw.MessageDialog(
            transient_for=self._window,
            heading=get_text("dialogs", "confirm_remove"),
            body=get_text("dialogs", "remove_wireguard_body"),
        )
        dialog.add_response("cancel", get_text("buttons", "cancel"))
        dialog.add_response("remove", get_text("buttons", "remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_remove_confirmed)
        dialog.present()

    def _on_remove_confirmed(self, dialog: object, response: str) -> None:
        """Handle remove confirmation response."""
        if response != "remove":
            return
        self._logger.info("[UI:Main] Removing WireGuard...")
        self.set_status(get_text("status", "removing"))
        self.run_async(
            lambda: do_remove_services(
                self._wg_service,
                self._st_service,
                self._dns_service,
            ),
            lambda r: self._finish_operation(r, get_text("messages", "service_removed")),
        )

    def _on_help(self, button: object) -> None:
        """Handle help button click."""
        dialog = Adw.MessageDialog(
            transient_for=self._window,
            heading=get_text("help", "wireguard_title"),
            body=get_text("help", "wireguard_body"),
        )
        dialog.add_response("ok", get_text("buttons", "ok"))
        dialog.present()

    def _get_selected_apps(self) -> list[str]:
        """Get list of enabled apps for tunneling."""
        apps: list[str] = []
        for app_id, enabled in self._enabled_apps.items():
            if enabled and app_id in KNOWN_APPS:
                paths = KNOWN_APPS[app_id]
                for path in paths:
                    if Path(path).exists():
                        apps.append(path)
                        break
                else:
                    if paths:
                        apps.append(paths[0])
        apps.extend(self._custom_apps)
        return apps

    def _save_settings(self) -> None:
        """Save current settings to config file."""
        save_page_settings(
            self._enabled_apps,
            self._custom_apps,
            self._switch_browser,
            self._switch_refresh,
            self._switch_full_tunnel,
        )

    def _load_settings(self) -> None:
        """Load settings from config file and update UI."""
        self._custom_apps = load_page_settings(
            self._enabled_apps,
            self._custom_apps,
            self._switch_browser,
            self._switch_refresh,
            self._switch_full_tunnel,
        )
