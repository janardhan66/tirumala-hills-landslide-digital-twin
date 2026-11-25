"""Export backend-only integration status for safe frontend consumption."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import get_db
from src.backend_integration import export_backend_status


if __name__ == "__main__":
    print(json.dumps(export_backend_status(get_db()), indent=2, allow_nan=False))
