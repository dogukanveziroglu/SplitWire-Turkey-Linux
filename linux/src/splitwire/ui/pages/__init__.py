"""
SplitWire UI Pages.

Contains all application pages:
- MainPage: WireGuard/WireSock setup
- ByeDPIPage: ByeDPI proxy setup
- RepairPage: Discord repair tools
- AdvancedPage: Advanced service management
- SettingsPage: Application settings
"""

from .advanced_page import AdvancedPage
from .byedpi_page import ByeDPIPage
from .main_page import MainPage
from .repair_page import RepairPage
from .settings_page import SettingsPage

__all__ = [
    "AdvancedPage",
    "ByeDPIPage",
    "MainPage",
    "RepairPage",
    "SettingsPage",
]
