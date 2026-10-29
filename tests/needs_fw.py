"""Skip marker for tests that need the official Shelly ZIPs in fw/shelly.

Those ZIPs are not in the repository (Shelly's firmware is not ours to redistribute), so a fresh checkout, CI
included, has none. With them in place nothing is skipped.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import firmware  # noqa: E402

HAVE_FW = any(firmware.FW_DIR.glob("*/*/*.zip"))
needs_fw = unittest.skipUnless(HAVE_FW, "no official Shelly ZIPs in fw/shelly")
