"""Shelly OTA packaging (Gen2/Gen3/Gen4): wrap an ESPHome app image into an official-style OTA ZIP."""

from pathlib import Path

__version__ = "0.3.0"  # SemVer; 0.x = experimental. Keep CHANGELOG.md in step.

MODULE_DIR = Path(__file__).resolve().parent.parent
