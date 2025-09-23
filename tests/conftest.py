from __future__ import annotations

import os

# Qt widgets require a platform plugin.  Offscreen avoids libGL dependencies
# inside the test container.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
