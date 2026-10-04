"""Shelly Gen3 OTA packaging: wrap an ESPHome app image into an official-style OTA ZIP."""

from pathlib import Path

__version__ = "0.1.0"  # SemVer; 0.x = experimental. Keep CHANGELOG.md in step.

MODULE_DIR = Path(__file__).resolve().parent.parent
