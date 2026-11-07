from pathlib import Path
import re

for path in Path("services/backend/tests").rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    orig = text

    def add_name(match: re.Match[str]) -> str:
        body = match.group(1)
        if "display_name" in body:
            return match.group(0)
        return f'json={{"join_code": {body}, "display_name": "Ana"}}'

    text = re.sub(r'json=\{"join_code": ([^}]+)\}', add_name, text)
    text = re.sub(
        r'join_class\(([^,\)]+)\)',
        r'join_class(\1, display_name="Ana")',
        text,
    )
    text = re.sub(
        r'join_class\(([^,]+),\s*("[^"]+")\)',
        r'join_class(\1, \2, display_name="Ana")',
        text,
    )
    # Avoid double display_name if prior _open already had it inside multi-line json
    text = text.replace(
        'display_name": "Ana", "display_name": "Ana"',
        'display_name": "Ana"',
    )
    if text != orig:
        path.write_text(text, encoding="utf-8")
        print(path)
