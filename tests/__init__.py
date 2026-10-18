"""Test package for Agent Bench.

Puts the repository root on ``sys.path`` so tests can import the ``common``,
``evaluation``, and ``scripts`` namespace packages without an editable install.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
