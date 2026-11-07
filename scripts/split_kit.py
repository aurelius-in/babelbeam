"""Split the concatenated Cursor kit into repository files. One-shot helper."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\local\_babelbeam_hold\BabelBeam_Cursor_Master_Instructions.md")


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    parts = re.split(r"\n*<!-- Source: (.+?) -->\n*", text)
    if len(parts) < 3:
        raise SystemExit("No source markers found")
    # parts[0] is the kit preamble. Fold it into START_HERE.
    preamble = parts[0].strip() + "\n\n"
    for name, body in zip(parts[1::2], parts[2::2], strict=True):
        body = body.strip() + "\n"
        if name == "START_HERE.md" and preamble:
            body = preamble + body
        if name == "docs/SOURCES.md":
            body = body.split("\n## Appendix:", 1)[0].rstrip() + "\n"
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
