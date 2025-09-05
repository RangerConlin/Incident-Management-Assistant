"""Test package initialisation.

Pytest loads individual test modules as part of the ``tests`` package.  The
project source lives one directory level above this package which means the
modules are not automatically importable when running the tests in isolation.

To mirror the behaviour of the running application we explicitly append the
repository root to ``sys.path`` here.  This keeps the tests lightweight and
avoids repeating the path adjustment in every single test module.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root (one directory up from this file) to the Python path so
# that ``import ui`` and similar absolute imports succeed when the tests are
# executed in isolation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

