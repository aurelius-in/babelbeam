"""Report live-provider prerequisites. Does not call a provider unless explicitly accepted."""

from __future__ import annotations

import os
import sys

REQUIRED = ("OPENAI_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


def main() -> int:
    print("Provider check does not prove a classroom translation.")
    print("A live call can spend money. Set BB_PROVIDER_CHECK_ACCEPT_COST=1 to opt in.")
    missing = [name for name in REQUIRED if not os.environ.get(name, "").strip()]
    if missing:
        print("Missing: " + ", ".join(missing))
    if os.environ.get("BB_PROVIDER_CHECK_ACCEPT_COST") != "1":
        print("No provider endpoint was contacted.")
        return 2
    if missing:
        print("Refusing the live check until the missing values are set.")
        return 2
    print("Credential presence was acknowledged. Phase 0 still has no live speech call.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
