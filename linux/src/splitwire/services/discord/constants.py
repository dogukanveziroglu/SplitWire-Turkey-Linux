"""Path, URL, and detection constants for the Discord service."""

from pathlib import Path

# Configuration paths
LOCAL_CONFIG_DIR = Path.home() / ".config" / "splitwire" / "discord"
CONFIG_FILE = LOCAL_CONFIG_DIR / "config.json"

# Discord paths
DISCORD_CONFIG_DIRS = {
    "stable": Path.home() / ".config" / "discord",
    "ptb": Path.home() / ".config" / "discordptb",
    "canary": Path.home() / ".config" / "discordcanary",
}

DISCORD_CACHE_DIRS = {
    "stable": Path.home() / ".cache" / "discord",
    "ptb": Path.home() / ".cache" / "discordptb",
    "canary": Path.home() / ".cache" / "discordcanary",
}

# Flatpak Discord paths
FLATPAK_DISCORD_IDS = {
    "stable": "com.discordapp.Discord",
    "ptb": "com.discordapp.DiscordPTB",
    "canary": "com.discordapp.DiscordCanary",
}

# Snap Discord names
SNAP_DISCORD_NAMES = {
    "stable": "discord",
    "ptb": "discord-ptb",
    "canary": "discord-canary",
}

# DEB package names
DEB_DISCORD_NAMES = {
    "stable": "discord",
    "ptb": "discord-ptb",
    "canary": "discord-canary",
}

# Binary names
DISCORD_BINARIES = {
    "stable": ["discord", "Discord"],
    "ptb": ["discord-ptb", "discordptb", "DiscordPTB"],
    "canary": ["discord-canary", "discordcanary", "DiscordCanary"],
}

# Download URLs
DISCORD_DOWNLOAD_URLS = {
    "stable": "https://discord.com/api/download?platform=linux&format=deb",
    "ptb": "https://discord.com/api/download/ptb?platform=linux&format=deb",
    "canary": "https://discord.com/api/download/canary?platform=linux&format=deb",
}

# WebCord
WEBCORD_FLATPAK_ID = "io.github.nickvision.webcord"
WEBCORD_APPIMAGE_URL = "https://github.com/nickvision/webcord/releases/latest"
