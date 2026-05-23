"""
AetherPDF Configuration Settings.

This module contains application-wide constants, default configuration values,
and settings for PDF rendering and UI geometry.
"""

# Application Metadata
APP_NAME: str = "AetherPDF"
APP_VERSION: str = "1.1.0"
GITHUB_REPO: str = "woodencatjskim/AetherPDF"
GITHUB_RELEASES_API: str = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Main UI Window Dimensions
DEFAULT_WINDOW_WIDTH: int = 1280
DEFAULT_WINDOW_HEIGHT: int = 850

# PDF Rendering Configuration
# 150 DPI is optimized for rapid rendering with high visual crispness.
DEFAULT_DPI: int = 150

# Zoom Limits and Ratios
ZOOM_STEP: float = 1.2
MIN_ZOOM: float = 0.1
MAX_ZOOM: float = 6.0
DEFAULT_ZOOM: float = 1.0

# Accent Palette Colors (for drawing/highlighting defaults)
DEFAULT_HIGHLIGHT_COLOR: str = "#00F0FF"  # Aurora Cyan
DEFAULT_TEXT_COLOR: str = "#FFFFFF"       # White
DEFAULT_FONT_SIZE: int = 12
DEFAULT_FONT_NAME: str = "Inter"
