import sys
from pathlib import Path

# Make the src/ package importable and locate fixtures dir.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES_DIR = ROOT / "fixtures"
