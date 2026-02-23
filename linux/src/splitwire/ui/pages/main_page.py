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

from splitwire.core import get_config, get_text, save_config
from splitwire.services import (
    KNOWN_APPS,
    ServiceStatus,
    get_dns_service,
    get_split_tunnel_service,
    get_wireguard_service,
)
from splitwire.services.wireguard import TunnelMode

from .base_page import BasePage

if TYPE_CHECKING:
    from splitwire.ui.window import SplitWireWindow


class MainPage(BasePage):
    """WireGuard/WireSock setup page."""

    def __init__(self, window: "SplitWireWindow"):
        self._wg_service = get_wireguard_service()
        self._st_service = get_split_tunnel_service()
        self._dns_service = get_dns_service()
        # Load custom apps from config
        config = get_config()
        self._custom_apps: list[str] = list(config.wireguard.custom_apps or [])
        # Track which known apps are enabled (all enabled by default)
        self._enabled_apps: dict[str, bool] = dict.fromkeys(KNOWN_APPS.keys(), True)
        super().__init__(window)

    def _build_ui(self):
        """Build the main page UI."""
        # Status indicator
        self._status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=8,
            margin_bottom=8,
        )
        self.append(self._status_box)
        # Note: _update_status_indicator() called at end of _build_ui after buttons exist

        # Main buttons group
        buttons_group = self.create_preferences_group(title=get_text("main", "setup"))
        self.append(buttons_group)

        # Standard setup button
        self._btn_standard = self.create_action_button(
            label=get_text("main", "standard_setup"),
            callback=self._on_standard_setup,
            tooltip=get_text("tooltips", "standard_install"),
            suggested=True,
        )
        buttons_group.add(self._btn_standard)

        # Disconnect button (initially hidden)
        self._btn_disconnect = self.create_action_button(
            label=get_text("buttons", "disconnect"),
            callback=self._on_disconnect,
            tooltip=get_text("tooltips", "wireguard_disconnect"),
            destructive=True,
        )
        self._btn_disconnect.set_visible(False)
        buttons_group.add(self._btn_disconnect)

        # Options group
        options_group = self.create_preferences_group(
            title=get_text("main", "options")
        )
        self.append(options_group)

        # Browser tunneling switch
        self._switch_browser = self.create_switch_row(
            title=get_text("main", "browser_tunneling"),
            subtitle=get_text("tooltips", "browser_tunneling"),
            active=False,
            callback=self._on_browser_tunneling_changed,
        )
        options_group.add(self._switch_browser)

        # Full tunnel mode switch (default: ON - all traffic through VPN)
        self._switch_full_tunnel = self.create_switch_row(
            title=get_text("main", "full_tunnel"),
            subtitle=get_text("tooltips", "full_tunnel"),
            active=True,
            callback=self._on_full_tunnel_changed,
        )
        options_group.add(self._switch_full_tunnel)

        # Refresh timer switch
        self._switch_refresh = self.create_switch_row(
            title=get_text("main", "refresh_timer"),
            subtitle=get_text("tooltips", "wiresock_repeater"),
            active=False,
            callback=self._on_refresh_timer_changed,
        )
        options_group.add(self._switch_refresh)

        # Advanced settings expander
        self._advanced_expander = Adw.ExpanderRow(
            title=get_text("main", "folder_customization"),
            subtitle=get_text("tooltips", "folder_customization"),
        )
        options_group.add(self._advanced_expander)

        # App list inside expander
        self._build_app_list()

        # Custom buttons row
        custom_buttons_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=8,
            margin_bottom=8,
        )
        self._advanced_expander.add_row(Adw.ActionRow(child=custom_buttons_box))

        # Add folder button
        self._btn_add_folder = Gtk.Button(
            label=get_text("main", "add_folder"),
            tooltip_text=get_text("tooltips", "add_folder"),
        )
        self._btn_add_folder.connect("clicked", self._on_add_folder)
        custom_buttons_box.append(self._btn_add_folder)

        # Clear list button
        self._btn_clear = Gtk.Button(
            label=get_text("main", "clear_list"),
            tooltip_text=get_text("tooltips", "clear_list"),
        )
        self._btn_clear.connect("clicked", self._on_clear_list)
        custom_buttons_box.append(self._btn_clear)

        # Advanced buttons row
        advanced_buttons_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=8,
        )
        self._advanced_expander.add_row(Adw.ActionRow(child=advanced_buttons_box))

        # Custom setup button
        self._btn_custom = Gtk.Button(
            label=get_text("main", "custom_setup"),
            tooltip_text=get_text("tooltips", "custom_install"),
        )
        self._btn_custom.connect("clicked", self._on_custom_setup)
        advanced_buttons_box.append(self._btn_custom)

        # Generate config button
        self._btn_generate = Gtk.Button(
            label=get_text("main", "generate_config"),
            tooltip_text=get_text("tooltips", "generate_config"),
        )
        self._btn_generate.connect("clicked", self._on_generate_config)
        advanced_buttons_box.append(self._btn_generate)

        # Remove service button
        remove_box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            margin_top=16,
        )
        self.append(remove_box)

        self._btn_remove = self.create_action_button(
            label=get_text("main", "remove_service"),
            callback=self._on_remove_service,
            destructive=True,
        )
        remove_box.append(self._btn_remove)

        # Help button
        help_box = Gtk.Box(
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            vexpand=True,
        )
        self.append(help_box)
        help_btn = self.create_help_button(self._on_help)
        help_box.append(help_btn)

        # Load saved settings
        self._load_settings()

        # Update status indicator now that all buttons exist
        self._update_status_indicator()

    def _build_app_list(self):
        """Build the app selection list inside the expander."""
        # Known apps section - KNOWN_APPS is {app_id: [paths...]}
        for app_id, paths in KNOWN_APPS.items():
            # Get first existing path as subtitle
            subtitle = ""
            for path in paths:
                if Path(path).exists():
                    subtitle = path
                    break
            if not subtitle and paths:
                subtitle = paths[0]

            # Format app name nicely
            display_name = app_id.replace("-", " ").replace("_", " ").title()

            row = Adw.ActionRow(
                title=display_name,
                subtitle=subtitle,
            )

            # Check button - use set_name to store app_id (GTK4 compatible)
            check = Gtk.CheckButton(
                active=True,
                valign=Gtk.Align.CENTER,
            )
            check.set_name(app_id)  # Store app_id in widget name
            check.connect("toggled", self._on_app_toggled)
            row.add_prefix(check)

            self._advanced_expander.add_row(row)

    def _update_status_indicator(self):
        """Update the status indicator and button visibility."""
        # Clear existing children
        while child := self._status_box.get_first_child():
            self._status_box.remove(child)

        # Get current status
        try:
            status = self._wg_service.status()
            running = status == ServiceStatus.RUNNING
        except Exception:
            running = False

        # Status dot
        dot_label = "●"
        dot_class = "status-running" if running else "status-stopped"
        dot = Gtk.Label(
            label=dot_label,
            css_classes=[dot_class],
        )
        self._status_box.append(dot)

        # Status text
        status_text = get_text("status", "running") if running else get_text("status", "stopped")
        label = Gtk.Label(label=status_text)
        self._status_box.append(label)

        # Update button visibility based on VPN state
        self._btn_standard.set_sensitive(not running)
        self._btn_disconnect.set_visible(running)

    def refresh(self):
        """Refresh page data."""
        self._update_status_indicator()

    def refresh_translations(self):
        """Refresh UI translations."""
        self._btn_standard.set_label(get_text("main", "standard_setup"))
        self._switch_browser.set_title(
            get_text("main", "browser_tunneling")
        )
        self._switch_refresh.set_title(
            get_text("main", "refresh_timer")
        )
        self._btn_remove.set_label(get_text("main", "remove_service"))

    # Event handlers

    def _on_standard_setup(self, button):
        """Handle standard setup button click."""
        self._logger.info("[UI:Main] Starting standard setup...")
        self.set_status(get_text("status", "installing"))

        def do_setup():
            error_msg = None
            try:
                # Register WGCF account if needed
                if not self._wg_service.register_wgcf():
                    return (
                        False,
                        get_text("errors", "wgcf_register_failed"),
                    )

                # Determine tunnel mode based on switch state
                tunnel_mode = (
                    TunnelMode.FULL if self._switch_full_tunnel.get_active() else TunnelMode.SPLIT
                )

                # Generate config with selected tunnel mode
                if not self._wg_service.generate_config(tunnel_mode=tunnel_mode):
                    return (
                        False,
                        get_text("errors", "config_generate_failed"),
                    )

                # CRITICAL: Start WireGuard BEFORE changing DNS
                # DNS change before VPN can cause endpoint resolution failure
                # if ISP blocks/throttles public DNS servers like 1.1.1.1
                if not self._wg_service.start():
                    return (
                        False,
                        get_text("errors", "service_start_failed"),
                    )

                # Verify VPN connection is working
                import time

                time.sleep(1)  # Give WireGuard a moment to establish connection
                if not self._wg_service.test_connection():
                    self._logger.warning(
                        "[UI:Main] VPN connection test failed, continuing anyway..."
                    )

                # NOW it's safe to change DNS (VPN is active, DNS queries can go through VPN)
                self._dns_service.install(preset="cloudflare")

                # Setup split tunnel with selected apps (optional, for app-based routing)
                include_browsers = self._switch_browser.get_active()
                apps = self._get_selected_apps()
                # Note: cgproxy split tunneling is separate from WireGuard's IP-based routing
                # WireGuard already routes Discord/Cloudflare IPs through VPN via AllowedIPs
                # self._st_service.configure(apps=apps, include_browsers=include_browsers)

                # Save settings
                self._save_settings()

                return (True, None)

            except Exception as e:
                self._logger.exception(f"Standard setup failed: {e}")
                return (False, str(e))

        def on_complete(result):
            self._update_status_indicator()
            success, error = result if isinstance(result, tuple) else (result, None)
            if success:
                self._logger.info("[UI:Main] Standard setup completed successfully")
                self.show_toast(get_text("messages", "setup_complete"))
            else:
                self._logger.error(f"[UI:Main] Standard setup failed: {error}")
                error_msg = get_text("messages", "error_generic").format(error) if error else get_text("status", "error")
                self.show_toast(error_msg)
            self.set_status("")

        self.run_async(do_setup, on_complete)

    def _on_disconnect(self, button):
        """Handle disconnect button click."""
        self._logger.info("[UI:Main] Disconnecting VPN...")
        self.set_status(get_text("status", "disconnecting"))

        def do_disconnect():
            try:
                self._wg_service.stop()
                # Restore original DNS settings
                self._dns_service.remove()
                return (True, None)
            except Exception as e:
                self._logger.exception(f"Disconnect failed: {e}")
                return (False, str(e))

        def on_complete(result):
            self._update_status_indicator()
            success, error = result if isinstance(result, tuple) else (result, None)
            if success:
                self.show_toast(get_text("messages", "service_stopped").format("WireGuard"))
            else:
                error_msg = get_text("messages", "error_generic").format(error) if error else get_text("status", "error")
                self.show_toast(error_msg)
            self.set_status("")

        self.run_async(do_disconnect, on_complete)

    def _on_browser_tunneling_changed(self, row, param):
        """Handle browser tunneling switch change."""
        active = row.get_active()
        self._logger.info(f"[UI:Main] Browser tunneling changed: {active}")
        # Will be applied during setup

    def _on_full_tunnel_changed(self, row, param):
        """Handle full tunnel mode switch change."""
        active = row.get_active()
        self._logger.info(f"[UI:Main] Full tunnel mode changed: {active}")
        # Will be applied during setup

    def _on_refresh_timer_changed(self, row, param):
        """Handle refresh timer switch change."""
        active = row.get_active()
        self._logger.info(f"[UI:Main] Refresh timer changed: {active}")
        # Enable/disable the refresh timer
        if active:
            self._wg_service.enable_refresh_timer()
        else:
            self._wg_service.disable_refresh_timer()

    def _on_app_toggled(self, check):
        """Handle app checkbox toggle."""
        app_id = check.get_name()  # Retrieve app_id from widget name
        active = check.get_active()
        self._enabled_apps[app_id] = active
        self._logger.info(f"[UI:Main] App toggled: {app_id} {'enabled' if active else 'disabled'}")
        # Save to config immediately
        self._save_settings()

    def _on_add_folder(self, button):
        """Handle add folder button click."""
        dialog = Gtk.FileDialog(
            title=get_text("dialogs", "select_folder"),
        )
        dialog.select_folder(
            self._window,
            None,
            self._on_folder_selected,
        )

    def _on_folder_selected(self, dialog, result):
        """Handle folder selection result."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                if path not in self._custom_apps:
                    self._custom_apps.append(path)
                    self._save_settings()  # Persist the change
                    self.show_toast(
                        get_text("messages", "item_added").format(path)
                    )
                else:
                    self.show_toast(
                        get_text("messages", "item_exists").format(path)
                    )
        except GLib.Error as e:
            if e.code != 2:  # Not cancelled
                self._logger.error(f"Folder selection error: {e}")

    def _on_clear_list(self, button):
        """Handle clear list button click."""
        self._custom_apps.clear()
        self._save_settings()  # Persist the change
        self.show_toast(get_text("messages", "list_cleared"))

    def _on_custom_setup(self, button):
        """Handle custom setup button click."""
        self._logger.info("[UI:Main] Starting custom setup...")
        if not self._custom_apps:
            self._logger.warning("[UI:Main] Custom setup cancelled: no custom apps")
            self.show_toast(get_text("messages", "no_custom_apps"))
            return

        self.set_status(get_text("status", "installing"))

        def do_setup():
            try:
                # Register WGCF account if needed
                if not self._wg_service.register_wgcf():
                    return (
                        False,
                        get_text("errors", "wgcf_register_failed"),
                    )

                # Generate config
                if not self._wg_service.generate_config():
                    return (
                        False,
                        get_text("errors", "config_generate_failed"),
                    )

                # CRITICAL: Start WireGuard BEFORE changing DNS
                if not self._wg_service.start():
                    return (
                        False,
                        get_text("errors", "service_start_failed"),
                    )

                # Verify VPN connection is working
                import time

                time.sleep(1)
                if not self._wg_service.test_connection():
                    self._logger.warning(
                        "[UI:Main] VPN connection test failed, continuing anyway..."
                    )

                # NOW it's safe to change DNS (VPN is active)
                self._dns_service.install(preset="cloudflare")

                # Save settings
                self._save_settings()

                return (True, None)

            except Exception as e:
                self._logger.exception(f"Custom setup failed: {e}")
                return (False, str(e))

        def on_complete(result):
            self._update_status_indicator()
            success, error = result if isinstance(result, tuple) else (result, None)
            if success:
                self.show_toast(get_text("messages", "setup_complete"))
            else:
                error_msg = get_text("messages", "error_generic").format(error) if error else get_text("status", "error")
                self.show_toast(error_msg)
            self.set_status("")

        self.run_async(do_setup, on_complete)

    def _on_generate_config(self, button):
        """Handle generate config button click."""
        dialog = Gtk.FileDialog(
            title=get_text("dialogs", "save_config"),
            initial_name="splitwire.conf",
        )
        dialog.save(
            self._window,
            None,
            self._on_config_save_selected,
        )

    def _on_config_save_selected(self, dialog, result):
        """Handle config save location selection."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                config_content = self._wg_service.generate_config_content(
                    include_browsers=self._switch_browser.get_active()
                )
                with open(path, "w") as f:
                    f.write(config_content)
                self.show_toast(get_text("messages", "config_saved"))
        except GLib.Error as e:
            if e.code != 2:  # Not cancelled
                self._logger.error(f"Config save error: {e}")

    def _on_remove_service(self, button):
        """Handle remove service button click."""
        # Confirmation dialog
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

    def _on_remove_confirmed(self, dialog, response):
        """Handle remove confirmation response."""
        if response == "remove":
            self._logger.info("[UI:Main] Removing WireGuard service...")
            self.set_status(get_text("status", "removing"))

            def do_remove():
                try:
                    self._wg_service.stop()
                    self._wg_service.remove()
                    self._st_service.remove()
                    # Restore DNS settings
                    self._dns_service.remove()
                    return (True, None)
                except Exception as e:
                    self._logger.exception(f"Service removal failed: {e}")
                    return (False, str(e))

            def on_complete(result):
                self._update_status_indicator()
                success, error = result if isinstance(result, tuple) else (result, None)
                if success:
                    self.show_toast(get_text("messages", "service_removed"))
                else:
                    error_msg = get_text("messages", "error_generic").format(error) if error else get_text("status", "error")
                    self.show_toast(error_msg)
                self.set_status("")

            self.run_async(do_remove, on_complete)

    def _on_help(self, button):
        """Handle help button click."""
        dialog = Adw.MessageDialog(
            transient_for=self._window,
            heading=get_text("help", "wireguard_title"),
            body=get_text("help", "wireguard_body"),
        )
        dialog.add_response("ok", get_text("buttons", "ok"))
        dialog.present()

    # Helper methods

    def _get_selected_apps(self) -> list[str]:
        """
        Get list of enabled apps for tunneling.

        Returns a combined list of:
        - Known apps that are enabled (from checkboxes)
        - Custom apps added by user

        Returns:
            List of app paths to tunnel
        """
        apps = []

        # Add enabled known apps
        for app_id, enabled in self._enabled_apps.items():
            if enabled and app_id in KNOWN_APPS:
                paths = KNOWN_APPS[app_id]
                # Add first existing path, or first path if none exist
                for path in paths:
                    if Path(path).exists():
                        apps.append(path)
                        break
                else:
                    if paths:
                        apps.append(paths[0])

        # Add custom apps
        apps.extend(self._custom_apps)

        return apps

    def _save_settings(self):
        """Save current settings to config file."""
        try:
            config = get_config()

            # Save app selections
            config.wireguard.enabled_known_apps = self._enabled_apps.copy()
            config.wireguard.custom_apps = self._custom_apps.copy()

            # Save switch states
            config.wireguard.include_browsers = self._switch_browser.get_active()
            config.wireguard.refresh_timer_enabled = self._switch_refresh.get_active()
            config.wireguard.full_tunnel_mode = self._switch_full_tunnel.get_active()

            # Persist to disk
            save_config()
            self._logger.debug("Settings saved")

        except Exception as e:
            self._logger.error(f"Failed to save settings: {e}")

    def _load_settings(self):
        """Load settings from config file and update UI."""
        try:
            config = get_config()

            # Load app selections
            if config.wireguard.enabled_known_apps:
                self._enabled_apps.update(config.wireguard.enabled_known_apps)

            if config.wireguard.custom_apps:
                self._custom_apps = list(config.wireguard.custom_apps)

            # Update switch states
            self._switch_browser.set_active(config.wireguard.include_browsers)
            self._switch_refresh.set_active(config.wireguard.refresh_timer_enabled)
            self._switch_full_tunnel.set_active(config.wireguard.full_tunnel_mode)

            self._logger.debug("Settings loaded")

        except Exception as e:
            self._logger.error(f"Failed to load settings: {e}")
