"""
SplitWire GTK4/Libadwaita Application.

Main application class that initializes the GUI and manages
the application lifecycle.
"""

import logging
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from splitwire.core import (
    get_config_manager,
    init_language_manager,
)
from splitwire.ui.window import SplitWireWindow

logger = logging.getLogger(__name__)


class SplitWireApp(Adw.Application):
    """Main GTK4/Libadwaita application for SplitWire-Turkey.

    Attributes:
        window: The main application window instance.
    """

    def __init__(self) -> None:
        """Initialize the application, actions, and signals."""
        super().__init__(
            application_id="com.splitwire.turkey",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self.window: SplitWireWindow | None = None
        self._config = None
        self._debug = False

        # Set application name
        GLib.set_application_name("SplitWire-Turkey")
        GLib.set_prgname("splitwire")

        # Connect signals
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

        # Setup actions
        self._setup_actions()

    def _setup_actions(self):
        """Setup application actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)

        # Preferences action
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.on_preferences)
        self.add_action(preferences_action)
        self.set_accels_for_action("app.preferences", ["<Control>comma"])

    def do_startup(self) -> None:
        """Called when the application starts."""
        Adw.Application.do_startup(self)

        # Initialize core systems
        self._init_core_systems()

        # Load CSS if available
        self._load_css()

    def _init_core_systems(self):
        """Initialize core systems (config, language, logging)."""
        try:
            logger.info("SplitWire-Turkey starting...")

            # Initialize config
            self._config = get_config_manager()
            config = self._config.load()
            logger.info(
                "Config loaded: theme=%s, language=%s",
                config.theme,
                config.language,
            )

            # Initialize language (config stores strings, not enums)
            init_language_manager(language=config.language)
            logger.info("Language initialized: %s", config.language)

            # Apply theme
            self._apply_theme(config.theme)

        except (OSError, ValueError, KeyError, TypeError) as e:
            sys.stderr.write(f"Error initializing core systems: {e}\n")

    def _apply_theme(self, theme: str):
        """Apply the specified theme."""
        style_manager = Adw.StyleManager.get_default()

        if theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:  # system
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _load_css(self):
        """Load custom CSS styles."""
        css_provider = Gtk.CssProvider()

        # Custom CSS for the application
        css = b"""
        /* SplitWire-Turkey Custom Styles */

        /* Status indicators */
        .status-running {
            color: #4CAF50;
        }

        .status-stopped {
            color: #9E9E9E;
        }

        .status-error {
            color: #F44336;
        }

        /* Remove buttons */
        .destructive-action {
            background-color: #8B0000;
            color: white;
        }

        .destructive-action:hover {
            background-color: #b83737;
        }

        /* Logo container */
        .logo-container {
            padding: 16px;
        }

        /* Service status row */
        .service-status-row {
            padding: 8px 16px;
        }

        /* Page title */
        .page-title {
            font-size: 18px;
            font-weight: bold;
        }

        /* Action button */
        .action-button {
            min-height: 48px;
            min-width: 280px;
            font-weight: bold;
        }

        /* Toggle row */
        .toggle-row {
            padding: 8px 0;
        }

        /* Help button */
        .help-button {
            min-width: 32px;
            min-height: 32px;
            border-radius: 16px;
        }

        /* Preset editor */
        .preset-editor {
            font-family: monospace;
            min-height: 80px;
        }
        """

        css_provider.load_from_data(css)

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def on_activate(self, _app):
        """Called when the application is activated."""
        if not self.window:
            self.window = SplitWireWindow(application=self)

        self.window.present()
        logger.info("Main window presented")

    def on_shutdown(self, _app):
        """Called when the application is shutting down."""
        logger.info("SplitWire-Turkey shutting down...")

        # Save config
        if self._config:
            try:
                self._config.save()
            except (OSError, ValueError, TypeError) as e:
                logger.error("Error saving config: %s", e)

    def on_quit(self, _action, _param):
        """Handle quit action."""
        self.quit()

    def on_about(self, _action, _param):
        """Show about dialog."""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name="SplitWire-Turkey",
            application_icon="com.splitwire.turkey",
            developer_name="SplitWire Team",
            version="1.0.0",
            website="https://github.com/dogukanveziroglu/SplitWire-Turkey",
            issue_url="https://github.com/dogukanveziroglu/SplitWire-Turkey/issues",
            copyright="2024 SplitWire Team",
            license_type=Gtk.License.MIT_X11,
            developers=[
                "Dogukan Veziroglu",
            ],
            comments=(
                "Manages network traffic routing with "
                "privacy-preserving configurations.\n\n"
                "Provides WireGuard VPN, Zapret packet "
                "processing, ByeDPI proxy, "
                "and Discord repair tools."
            ),
        )
        about.present()

    def on_preferences(self, _action, _param):
        """Show preferences (navigate to settings page)."""
        if self.window:
            self.window.navigate_to_settings()

    def set_theme(self, theme: str) -> None:
        """Set the application theme and save to config.

        Args:
            theme: Theme name ("light", "dark", or "system").
        """
        self._apply_theme(theme)

        # Save to config
        if self._config:
            config = self._config.load()
            config.theme = theme  # Store as string, not enum
            self._config.save()

    def set_language(self, language: str) -> None:
        """Set the application language and refresh the UI.

        Args:
            language: Language code (tr, en, ru, es).
        """
        from splitwire.core import set_language

        set_language(language)

        # Save to config
        if self._config:
            config = self._config.load()
            config.language = language  # Store as string, not enum
            self._config.save()

        # Refresh UI
        if self.window:
            self.window.refresh_translations()

    def show_notification(
        self,
        title: str,
        body: str,
        priority: Gio.NotificationPriority = (Gio.NotificationPriority.NORMAL),
    ) -> None:
        """Show a desktop notification.

        Args:
            title: Notification title text.
            body: Notification body text.
            priority: Notification urgency level.
        """
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_priority(priority)
        self.send_notification(None, notification)

    def show_toast(self, message: str, timeout: int = 3) -> None:
        """Show a toast message in the main window.

        Args:
            message: Toast text to display.
            timeout: Auto-dismiss time in seconds.
        """
        if self.window:
            self.window.show_toast(message, timeout)


def main():
    """Main entry point for the application."""
    app = SplitWireApp()
    return app.run(sys.argv)
