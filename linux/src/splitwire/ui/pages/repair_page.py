"""
Repair Page for SplitWire-Turkey.

Provides Discord repair and alternative client installation.
Equivalent to Windows "Onarim" (Repair) tab.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from typing import TYPE_CHECKING

from gi.repository import Adw, Gtk

from splitwire.core import get_text
from splitwire.services import (
    DiscordVersion,
    get_discord_service,
)

from .base_page import BasePage

if TYPE_CHECKING:
    from splitwire.ui.window import SplitWireWindow


class RepairPage(BasePage):
    """Discord repair and installation page."""

    def __init__(self, window: "SplitWireWindow"):
        self._discord_service = get_discord_service()
        super().__init__(window)

    def _build_ui(self):
        """Build the repair page UI."""
        # Main actions group
        actions_group = self.create_preferences_group(title=get_text("repair", "actions"))
        self.append(actions_group)

        # Discord repair button
        self._btn_repair = self.create_action_button(
            label=get_text("repair", "repair_discord"),
            callback=self._on_repair_discord,
            tooltip=get_text("tooltips", "discord_repair"),
            suggested=True,
        )
        actions_group.add(self._btn_repair)

        # Discord PTB install button
        self._btn_ptb = self.create_action_button(
            label=get_text("repair", "install_ptb"),
            callback=self._on_install_ptb,
            tooltip=get_text("tooltips", "discord_ptb_install"),
        )
        actions_group.add(self._btn_ptb)

        # WebCord install button
        self._btn_webcord = self.create_action_button(
            label=get_text("repair", "install_webcord"),
            callback=self._on_install_webcord,
            tooltip=get_text("tooltips", "webcord_install"),
        )
        actions_group.add(self._btn_webcord)

        # Options group
        options_group = self.create_preferences_group(title=get_text("repair", "options"))
        self.append(options_group)

        # Clean install for PTB switch
        self._switch_clean_ptb = self.create_switch_row(
            title=get_text("repair", "clean_install_ptb"),
            subtitle=get_text("tooltips", "clean_install_ptb"),
            active=False,
        )
        options_group.add(self._switch_clean_ptb)

        # Create shortcut for WebCord switch
        self._switch_webcord_shortcut = self.create_switch_row(
            title=get_text("repair", "webcord_shortcut"),
            subtitle=get_text("tooltips", "webcord_shortcut"),
            active=True,
        )
        options_group.add(self._switch_webcord_shortcut)

        # Status group
        status_group = self.create_preferences_group(title=get_text("repair", "status"))
        self.append(status_group)

        # Discord status row
        self._discord_status = self._create_status_row(
            "Discord",
            "discord",
            self._on_discord_action,
            self._on_discord_remove,
        )
        status_group.add(self._discord_status["row"])

        # Discord PTB status row
        self._ptb_status = self._create_status_row(
            "Discord PTB",
            "discord_ptb",
            self._on_ptb_action,
            self._on_ptb_remove,
        )
        status_group.add(self._ptb_status["row"])

        # WebCord status row
        self._webcord_status = self._create_status_row(
            "WebCord",
            "webcord",
            self._on_webcord_action,
            self._on_webcord_remove,
        )
        status_group.add(self._webcord_status["row"])

        # Refresh status
        self._refresh_status()

        # Help button
        help_box = Gtk.Box(
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            vexpand=True,
        )
        self.append(help_box)
        help_btn = self.create_help_button(self._on_help)
        help_box.append(help_btn)

    def _create_status_row(self, title: str, key: str, action_callback, remove_callback) -> dict:
        """Create a status row with action and remove buttons."""
        row = Adw.ActionRow(
            title=title,
        )

        # Status indicator
        status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            valign=Gtk.Align.CENTER,
        )

        status_dot = Gtk.Label(
            label="●",
            css_classes=["status-stopped"],
        )
        status_box.append(status_dot)

        status_label = Gtk.Label(
            label=get_text("status", "not_installed"),
        )
        status_box.append(status_label)

        row.add_suffix(status_box)

        # Action button
        action_btn = Gtk.Button(
            label=get_text("buttons", "install"),
            valign=Gtk.Align.CENTER,
            margin_start=8,
        )
        action_btn.connect("clicked", action_callback)
        row.add_suffix(action_btn)

        # Remove button (hidden by default)
        remove_btn = Gtk.Button(
            label=get_text("buttons", "remove"),
            css_classes=["destructive-action"],
            valign=Gtk.Align.CENTER,
            margin_start=8,
            visible=False,
        )
        remove_btn.connect("clicked", remove_callback)
        row.add_suffix(remove_btn)

        return {
            "row": row,
            "status_dot": status_dot,
            "status_label": status_label,
            "action_btn": action_btn,
            "remove_btn": remove_btn,
            "key": key,
        }

    def _update_status_row(self, status_dict: dict, installed: bool, running: bool = False):
        """Update a status row's appearance."""
        if installed:
            if running:
                status_dict["status_dot"].set_css_classes(["status-running"])
                status_dict["status_label"].set_label(get_text("status", "running"))
            else:
                status_dict["status_dot"].set_css_classes(["status-stopped"])
                status_dict["status_label"].set_label(get_text("status", "installed"))

            status_dict["action_btn"].set_label(get_text("buttons", "launch"))
            status_dict["remove_btn"].set_visible(True)
        else:
            status_dict["status_dot"].set_css_classes(["status-stopped"])
            status_dict["status_label"].set_label(get_text("status", "not_installed"))
            status_dict["action_btn"].set_label(get_text("buttons", "install"))
            status_dict["remove_btn"].set_visible(False)

    def _refresh_status(self):
        """Refresh all status indicators."""
        self._logger.debug("[UI:Repair] Refreshing Discord status...")

        def do_refresh():
            # Get Discord installations
            installations = self._discord_service.get_installations()
            webcord = self._discord_service.get_webcord()

            # Check each version - installations is dict[DiscordVersion, DiscordInstallation]
            discord_stable = installations.get(DiscordVersion.STABLE)
            discord_ptb = installations.get(DiscordVersion.PTB)

            return {
                "discord": discord_stable,
                "ptb": discord_ptb,
                "webcord": webcord,
            }

        def on_complete(result):
            if result:
                # Update Discord status
                discord_inst = result.get("discord")
                self._update_status_row(
                    self._discord_status,
                    installed=discord_inst is not None,
                    running=discord_inst.is_running if discord_inst else False,
                )

                # Update PTB status
                ptb_inst = result.get("ptb")
                self._update_status_row(
                    self._ptb_status,
                    installed=ptb_inst is not None,
                    running=ptb_inst.is_running if ptb_inst else False,
                )

                # Update WebCord status
                webcord_inst = result.get("webcord")
                self._update_status_row(
                    self._webcord_status,
                    installed=webcord_inst is not None,
                    running=webcord_inst.is_running if webcord_inst else False,
                )

        self.run_async(do_refresh, on_complete)

    def refresh(self):
        """Refresh page data."""
        self._refresh_status()

    def refresh_translations(self):
        """Refresh UI translations."""
        self._btn_repair.set_label(get_text("repair", "repair_discord"))
        self._btn_ptb.set_label(get_text("repair", "install_ptb"))
        self._btn_webcord.set_label(get_text("repair", "install_webcord"))

    # Event handlers

    def _on_repair_discord(self, button):
        """Handle repair Discord button."""
        self._logger.info("[UI:Repair] Repairing Discord...")
        self.set_status(get_text("status", "installing"))

        def do_repair():
            return self._discord_service.repair_discord()

        def on_complete(result):
            self._refresh_status()
            if result and result.success:
                self.show_toast(get_text("messages", "install_success").format("Discord"))
            else:
                msg = result.message if result else get_text("status", "error")
                self.show_toast(get_text("messages", "error_generic").format(msg))
            self.set_status("")

        self.run_async(do_repair, on_complete)

    def _on_install_ptb(self, button):
        """Handle install PTB button."""
        self._logger.info("[UI:Repair] Installing Discord PTB...")
        clean_install = self._switch_clean_ptb.get_active()

        if clean_install:
            # Confirmation dialog
            dialog = Adw.MessageDialog(
                transient_for=self._window,
                heading=get_text("repair", "clean_install_ptb"),
                body=get_text("dialogs", "clean_install_body"),
            )
            dialog.add_response("cancel", get_text("buttons", "cancel"))
            dialog.add_response("continue", get_text("buttons", "ok"))
            dialog.set_response_appearance("continue", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect("response", self._on_clean_install_confirmed)
            dialog.present()
        else:
            self._do_install_ptb()

    def _on_clean_install_confirmed(self, dialog, response):
        """Handle clean install confirmation."""
        if response == "continue":
            self._do_install_ptb(clean=True)

    def _do_install_ptb(self, clean: bool = False):
        """Perform PTB installation."""
        self.set_status(get_text("status", "installing"))

        def do_install():
            if clean:
                # Remove existing Discord first
                self._discord_service.clear_all_cache()
                installations = self._discord_service.get_installations()
                stable_inst = installations.get(DiscordVersion.STABLE)
                if stable_inst:
                    self._discord_service.uninstall_discord(stable_inst)

            # Install PTB
            self._discord_service.install_discord(DiscordVersion.PTB)
            return True

        def on_complete(result):
            self._refresh_status()
            if result:
                self.show_toast(get_text("messages", "install_success").format("Discord PTB"))
            self.set_status("")

        self.run_async(do_install, on_complete)

    def _on_install_webcord(self, button):
        """Handle install WebCord button."""
        self._logger.info("[UI:Repair] Installing WebCord...")
        create_shortcut = self._switch_webcord_shortcut.get_active()
        self.set_status(get_text("status", "installing"))

        def do_install():
            self._discord_service.install_webcord(create_shortcut=create_shortcut)
            return True

        def on_complete(result):
            self._refresh_status()
            if result:
                self.show_toast(get_text("messages", "install_success").format("WebCord"))
            self.set_status("")

        self.run_async(do_install, on_complete)

    def _on_discord_action(self, button):
        """Handle Discord action button (install/launch)."""
        label = button.get_label()
        if label == get_text("buttons", "install"):
            self._do_install_discord()
        else:
            self._discord_service.launch_discord(DiscordVersion.STABLE)

    def _do_install_discord(self):
        """Install Discord stable."""
        self.set_status(get_text("status", "installing"))

        def do_install():
            self._discord_service.install_discord(DiscordVersion.STABLE)
            return True

        def on_complete(result):
            self._refresh_status()
            if result:
                self.show_toast(get_text("messages", "install_success").format("Discord"))
            self.set_status("")

        self.run_async(do_install, on_complete)

    def _on_discord_remove(self, button):
        """Handle Discord remove button."""
        self._confirm_remove("Discord", DiscordVersion.STABLE)

    def _on_ptb_action(self, button):
        """Handle PTB action button (install/launch)."""
        label = button.get_label()
        if label == get_text("buttons", "install"):
            self._do_install_ptb()
        else:
            self._discord_service.launch_discord(DiscordVersion.PTB)

    def _on_ptb_remove(self, button):
        """Handle PTB remove button."""
        self._confirm_remove("Discord PTB", DiscordVersion.PTB)

    def _on_webcord_action(self, button):
        """Handle WebCord action button (install/launch)."""
        label = button.get_label()
        if label == get_text("buttons", "install"):
            self._on_install_webcord(button)
        else:
            self._discord_service.launch_webcord()

    def _on_webcord_remove(self, button):
        """Handle WebCord remove button."""
        self._confirm_remove_webcord()

    def _confirm_remove(self, name: str, version: DiscordVersion):
        """Show remove confirmation dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self._window,
            heading=get_text("dialogs", "confirm_remove"),
            body=get_text("messages", "confirm_remove").format(name),
        )
        dialog.add_response("cancel", get_text("buttons", "cancel"))
        dialog.add_response("remove", get_text("buttons", "remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        self._pending_remove_version = version  # Store in instance variable (GTK4 compatible)
        dialog.connect("response", self._on_remove_confirmed)
        dialog.present()

    def _on_remove_confirmed(self, dialog, response):
        """Handle remove confirmation."""
        if response == "remove":
            version = self._pending_remove_version  # Use instance variable (GTK4 compatible)
            self.set_status(get_text("status", "removing"))

            def do_remove():
                installations = self._discord_service.get_installations()
                inst = installations.get(version)
                if inst:
                    self._discord_service.uninstall_discord(inst)
                return True

            def on_complete(result):
                self._refresh_status()
                if result:
                    self.show_toast(get_text("messages", "service_removed"))
                self.set_status("")

            self.run_async(do_remove, on_complete)

    def _confirm_remove_webcord(self):
        """Show WebCord remove confirmation dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self._window,
            heading=get_text("dialogs", "confirm_remove"),
            body=get_text("messages", "confirm_remove").format("WebCord"),
        )
        dialog.add_response("cancel", get_text("buttons", "cancel"))
        dialog.add_response("remove", get_text("buttons", "remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_webcord_remove_confirmed)
        dialog.present()

    def _on_webcord_remove_confirmed(self, dialog, response):
        """Handle WebCord remove confirmation."""
        if response == "remove":
            self.set_status(get_text("status", "removing"))

            def do_remove():
                self._discord_service.uninstall_webcord()
                return True

            def on_complete(result):
                self._refresh_status()
                if result:
                    self.show_toast(get_text("messages", "remove_success").format("WebCord"))
                self.set_status("")

            self.run_async(do_remove, on_complete)

    def _on_help(self, button):
        """Handle help button."""
        dialog = Adw.MessageDialog(
            transient_for=self._window,
            heading=get_text("help", "repair_title"),
            body=get_text("help", "repair_body"),
        )
        dialog.add_response("ok", get_text("buttons", "ok"))
        dialog.present()
