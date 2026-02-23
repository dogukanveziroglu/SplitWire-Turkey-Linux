"""
Constants for the split tunnel service.

Known application paths and configuration paths.
"""

from pathlib import Path

# cgproxy configuration
# Use SplitWire's own config directory and service
CGPROXY_CONFIG_DIR = Path("/etc/splitwire")
CGPROXY_CONFIG_FILE = CGPROXY_CONFIG_DIR / "cgproxy.json"
CGPROXY_SERVICE = "splitwire-cgproxy.service"

# Local configuration
LOCAL_CONFIG_DIR = Path.home() / ".config" / "splitwire"
APPS_CONFIG_FILE = LOCAL_CONFIG_DIR / "tunneled_apps.json"

# Known application paths - Linux equivalents of Windows apps
KNOWN_APPS: dict[str, list[str]] = {
    # Discord
    "discord": [
        "/usr/share/discord/Discord",
        "/usr/bin/discord",
        "/opt/discord/Discord",
        "/snap/discord/current/usr/share/discord/Discord",
        "/var/lib/flatpak/app/com.discordapp.Discord"
        "/current/active/files/discord/Discord",
    ],
    "discord-ptb": [
        "/usr/share/discord-ptb/DiscordPTB",
        "/usr/bin/discord-ptb",
    ],
    "discord-canary": [
        "/usr/share/discord-canary/DiscordCanary",
        "/usr/bin/discord-canary",
    ],
    # Browsers
    "firefox": [
        "/usr/lib/firefox/firefox",
        "/usr/bin/firefox",
        "/snap/firefox/current/usr/lib/firefox/firefox",
    ],
    "chrome": [
        "/opt/google/chrome/google-chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ],
    "chromium": [
        "/usr/lib/chromium-browser/chromium-browser",
        "/usr/bin/chromium-browser",
        "/snap/chromium/current/usr/lib/chromium-browser/chromium-browser",
    ],
    "brave": [
        "/opt/brave.com/brave/brave-browser",
        "/usr/bin/brave-browser",
    ],
    "vivaldi": [
        "/opt/vivaldi/vivaldi",
        "/usr/bin/vivaldi",
    ],
    "opera": [
        "/usr/lib/x86_64-linux-gnu/opera/opera",
        "/usr/bin/opera",
    ],
    "edge": [
        "/opt/microsoft/msedge/msedge",
        "/usr/bin/microsoft-edge",
    ],
    # Communication
    "telegram": [
        "/opt/telegram/Telegram",
        "/usr/bin/telegram-desktop",
        "/snap/telegram-desktop/current/bin/Telegram",
    ],
    "signal": [
        "/opt/Signal/signal-desktop",
        "/usr/bin/signal-desktop",
    ],
    "slack": [
        "/usr/lib/slack/slack",
        "/usr/bin/slack",
        "/snap/slack/current/usr/lib/slack/slack",
    ],
    # Gaming
    "steam": [
        "/usr/lib/steam/steam",
        "/usr/bin/steam",
        "/snap/steam/current/usr/lib/steam/steam",
    ],
    # Media
    "spotify": [
        "/usr/share/spotify/spotify",
        "/usr/bin/spotify",
        "/snap/spotify/current/usr/share/spotify/spotify",
    ],
}

# Browser app names for the "include browsers" option
BROWSER_APPS = [
    "firefox", "chrome", "chromium", "brave",
    "vivaldi", "opera", "edge",
]
