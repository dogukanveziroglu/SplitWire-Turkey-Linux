"""DNS service path constants."""

from pathlib import Path

# Local configuration paths
LOCAL_CONFIG_DIR = Path.home() / ".config" / "splitwire" / "dns"
CONFIG_FILE = LOCAL_CONFIG_DIR / "config.json"
BACKUP_FILE = LOCAL_CONFIG_DIR / "backup.json"

# systemd-resolved paths
RESOLVED_CONF = Path("/etc/systemd/resolved.conf")
RESOLVED_CONF_DIR = Path("/etc/systemd/resolved.conf.d")
SPLITWIRE_RESOLVED_CONF = RESOLVED_CONF_DIR / "splitwire.conf"

# Network Manager paths (fallback)
NM_CONF_DIR = Path("/etc/NetworkManager/conf.d")
