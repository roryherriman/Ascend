import os
import sys
from pathlib import Path

# Run Qt headless during tests unless the developer explicitly wants a visible window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
