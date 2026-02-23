"""
Constants for the blockcheck service.

Includes test targets for different scan modes.
"""

from pathlib import Path

ZAPRET_INSTALL_DIR = Path("/opt/zapret")
BLOCKCHECK_SCRIPT = ZAPRET_INSTALL_DIR / "blockcheck.sh"
BLOCKCHECK_LOG = Path.home() / ".config" / "splitwire" / "zapret" / "blockcheck.log"
BLOCKCHECK_RESULTS = Path.home() / ".config" / "splitwire" / "zapret" / "blockcheck_results.json"

# Quick scan targets (minimal, fast)
QUICK_TARGETS = [
    "discord.com",
    "rutracker.org",
]

# Standard scan targets
STANDARD_TARGETS = [
    "discord.com",
    "discord.gg",
    "discordapp.com",
    "rutracker.org",
    "4pda.ru",
    "twitter.com",
]

# Full scan targets (comprehensive)
FULL_TARGETS = [
    "discord.com",
    "discord.gg",
    "discordapp.com",
    "discord.media",
    "rutracker.org",
    "4pda.ru",
    "twitter.com",
    "x.com",
    "pornhub.com",
    "youtube.com",
    "instagram.com",
    "facebook.com",
    "linkedin.com",
]
