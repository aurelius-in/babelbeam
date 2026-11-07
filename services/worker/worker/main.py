"""Worker process. Mock mode prints a banner and does not call providers."""

from __future__ import annotations

import asyncio
import sys

from babelbeam_runtime import Settings, simulated, validate_settings
from worker.providers import build_translator


async def run() -> None:
    settings = Settings()
    validate_settings(settings)
    translator = build_translator(
        provider_mode=settings.provider_mode,
        api_key=settings.openai_api_key,
        model=settings.openai_translation_model,
    )
    if simulated(settings):
        print(
            "SIMULATED MODE: the worker is not connected to speech, "
            "translation, or media providers.",
            flush=True,
        )
    else:
        print(
            "Live provider mode selected. No classroom pipeline is running in Phase 0.",
            flush=True,
        )
    print(f"translator={translator.name}", flush=True)
    while True:
        await asyncio.sleep(30)


def main() -> None:
    try:
        asyncio.run(run())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
