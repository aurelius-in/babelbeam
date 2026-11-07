"""Write the FastAPI schema for the checked-in contract."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "packages" / "contracts" / "openapi.json"


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {DESTINATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
