"""Test configuration.

The test suite is the ONLY thing permitted to substitute a gateway. Unit
tests must not depend on network access or on the developer holding
credentials — but that permission is granted here, explicitly and in one
visible place, rather than being a silent fallback inside the product.
"""

from __future__ import annotations

import os

os.environ.setdefault("WINBACK_ALLOW_FAKE_GATEWAY", "1")
