"""Root conftest — ensure custom_components is importable."""

import sys
from pathlib import Path

# Add custom components to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Add Home Assistant core tests to path for test fixtures
sys.path.insert(0, "/workspaces/core")
