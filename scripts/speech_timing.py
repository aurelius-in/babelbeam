"""Time BabelBeam speech stages with synthetic fixtures.

Output is limited to stage names, milliseconds, byte sizes, counts, and booleans.
Fixture audio is synthetic text read by an AI voice, never a classroom recording.
Generated audio is written outside the repository (see --out).

Paid calls: --make-fixtures (one TTS call per missing fixture), --local-stt (two
transcription calls), --prod-read (two interpret calls), --prod-class (one teacher
utterance per fixture sent). Nothing else contacts a paid provider.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

OPENAI_BASE = "https://api.openai.com/v1"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "marin"
STT_MODEL = "gpt-transcribe"

LINES: dict[str, str] = {
    "short": "Peace be with you. Today we will talk about the sacraments.",
    "long1": (
        "So, let us begin. The Koine Greek word mysterion can be translated into two "
        "different words in Latin, mysterium and sacramentum."
    ),
    "long2": (
        "When the early Church spoke about the mysteries of faith, it meant the saving "
        "actions of Christ that we meet in the liturgy, in the word of God, and in the "
        "life of the community, and that is why the Latin writers chose the word "
        "sacramentum for these signs."
    ),
    "long3": "Now, think quietly about your own baptism for a moment.",
}
EXPECTED_WORDS = {
    "short": ("peace", "sacraments"),
}
SPANISH_MARKERS = (" la ", " el ", " de ", " que ", " los ", " las ", "paz", "sacramento")


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _report(stage: str, ms: int | None, **extra: object) -> None:
    parts = " ".join(f"{key}={value}" for key, value in extra.items())
    timing = f"{ms:>6} ms" if ms is not None else "     - ms"
    print(f"{stage:<34} {timing} {parts}".rstrip(), flush=True)


def _looks_spanish(text: str) -> bool:
    lowered = f" {text.lower()} "
    return sum(marker in lowered for marker in SPANISH_MARKERS) >= 2


def _ffmpeg(args: list[str]) -> None:
    binary = shutil.which("ffmpeg")
    if binary is None:
        raise SystemExit("ffmpeg is required to build WAV fixtures.")
    subprocess.run(
        [binary, "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
        timeout=120,
    )


def _openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set.")
    return key


def make_fixtures(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {_openai_key()}"}
    with httpx.Client(timeout=60.0) as client:
        for name, text in LINES.items():
            target = out / f"{name}.mp3"
            if target.is_file():
                continue
            start = time.perf_counter()
            response = client.post(
                f"{OPENAI_BASE}/audio/speech",
                headers=headers,
                json={
                    "model": TTS_MODEL,
                    "voice": TTS_VOICE,
                    "input": text,
                    "response_format": "mp3",
                },
            )
            response.raise_for_status()
            target.write_bytes(response.content)
            _report(f"fixture_tts_{name}", _ms(start), bytes=len(response.content))
    _ffmpeg(
        [
            "-i", str(out / "short.mp3"),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(out / "short16k.wav"),
        ]
    )
    fmt = "aresample=48000,aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=mono"
    silences = (0.6, 1.0, 0.7, 1.5)
    inputs: list[str] = []
    for name in ("long1", "long2", "long3"):
        inputs += ["-i", str(out / f"{name}.mp3")]
    for seconds in silences:
        inputs += ["-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=mono"]
    chains = [f"[{index}:a]{fmt}[s{index}]" for index in range(7)]
    order = "[s3][s0][s4][s1][s5][s2][s6]"
    graph = ";".join(chains) + f";{order}concat=n=7:v=0:a=1[out]"
    _ffmpeg(
        [
            *inputs,
            "-filter_complex", graph,
            "-map", "[out]", "-c:a", "pcm_s16le",
            str(out / "long48k.wav"),
        ]
    )
    for name in ("short16k.wav", "long48k.wav"):
        _report(f"fixture_{name}", None, bytes=(out / name).stat().st_size)


def local_stt(out: Path, show_text: bool) -> None:
    headers = {"Authorization": f"Bearer {_openai_key()}"}
    with httpx.Client(timeout=60.0) as client:
        for name, media in (("short.mp3", "audio/mpeg"), ("short16k.wav", "audio/wav")):
            audio = (out / name).read_bytes()
            start = time.perf_counter()
            response = client.post(
                f"{OPENAI_BASE}/audio/transcriptions",
                headers=headers,
                files={"file": (name, audio, media)},
                data={"model": STT_MODEL},
            )
            elapsed = _ms(start)
            body = response.json() if response.status_code == 200 else {}
            text = str(body.get("text") or "")
            languages = [str(item.get("code")) for item in body.get("languages") or []]
            expected = EXPECTED_WORDS["short"]
            _report(
                f"local_stt_{name}",
                elapsed,
                status=response.status_code,
                bytes=len(audio),
                languages="/".join(languages) or "none",
                expected_words=f"{sum(word in text.lower() for word in expected)}/{len(expected)}",
                processing_ms=response.headers.get("openai-processing-ms", "?"),
            )
            if show_text:
                print(f"    synthetic transcript: {text}")


def _timed(
    client: httpx.Client, method: str, url: str, **kwargs: object
) -> tuple[httpx.Response, int]:
    start = time.perf_counter()
    response = client.request(method, url, **kwargs)  # type: ignore[arg-type]
    return response, _ms(start)


def prod_read(base: str, show_text: bool) -> None:
    with httpx.Client(timeout=60.0) as client:
        for index in range(3):
            response, elapsed = _timed(client, "GET", f"{base}/api/v1/health")
            _report(f"health_{index}", elapsed, status=response.status_code)
        for index in range(3):
            response, elapsed = _timed(
                client,
                "GET",
                f"{base}/api/v1/classes/feed",
                headers={"X-Class-Token": "timing-probe-not-a-token"},
            )
            _report(
                f"board_read_feed_404_{index}",
                elapsed,
                status=response.status_code,
                server_timing=response.headers.get("server-timing", "-"),
            )
        config, elapsed = _timed(client, "GET", f"{base}/api/v1/public/config")
        body_config = config.json() if config.status_code == 200 else {}
        billing = body_config.get("production_billing_enabled", "?")
        _report("public_config", elapsed, status=config.status_code, billing_enabled=billing)
        for include_audio in (False, True):
            response, elapsed = _timed(
                client,
                "POST",
                f"{base}/api/v1/interpret",
                json={
                    "text": LINES["short"],
                    "source_language": "en",
                    "target_language": "es",
                    "include_audio": include_audio,
                },
            )
            body = response.json() if response.status_code == 200 else {}
            spanish = str(body.get("translated_text") or "")
            audio_b64 = str(body.get("audio_base64") or "")
            _report(
                "interpret_text_and_tts" if include_audio else "interpret_text_only",
                elapsed,
                status=response.status_code,
                spanish=_looks_spanish(spanish),
                simulated=body.get("simulated"),
                audio_b64_chars=len(audio_b64),
                server_timing=response.headers.get("server-timing", "-"),
            )
            if show_text and not include_audio:
                print(f"    synthetic translation: {spanish}")


def prod_class(base: str, out: Path, names: list[str], parallel: bool, show_text: bool) -> None:
    with httpx.Client(timeout=90.0) as client:
        opened, elapsed = _timed(client, "POST", f"{base}/api/v1/classes")
        _report("class_start", elapsed, status=opened.status_code)
        if opened.status_code != 200:
            return
        teacher = {"X-Class-Token": str(opened.json()["teacher_token"])}
        joined, elapsed = _timed(
            client,
            "POST",
            f"{base}/api/v1/classes/join",
            json={"join_code": str(opened.json()["join_code"])},
        )
        _report("class_join", elapsed, status=joined.status_code)
        student = {"X-Class-Token": str(joined.json().get("student_token", ""))}
        try:
            _send_utterances(client, base, out, names, teacher, parallel, show_text)
            feed, elapsed = _timed(client, "GET", f"{base}/api/v1/classes/feed", headers=student)
            segments = feed.json().get("segments", []) if feed.status_code == 200 else []
            with_audio = sum(bool(item.get("audio_base64")) for item in segments)
            texts = [str(item.get("spanish_text") or "") for item in segments]
            _report(
                "student_feed",
                elapsed,
                status=feed.status_code,
                segments=len(segments),
                with_audio=with_audio,
                spanish=bool(texts) and all(_looks_spanish(text) for text in texts),
                payload_bytes=len(feed.content),
                server_timing=feed.headers.get("server-timing", "-"),
            )
            if show_text:
                for item, text in zip(segments, texts, strict=True):
                    print(f"    synthetic segment {item.get('seq', '-')}: {text}")
            cues, elapsed = _timed(client, "GET", f"{base}/api/v1/classes/cues", headers=teacher)
            _report("teacher_cues", elapsed, status=cues.status_code)
        finally:
            ended, elapsed = _timed(client, "POST", f"{base}/api/v1/classes/end", headers=teacher)
            _report("class_end", elapsed, status=ended.status_code)


def _send_utterances(
    client: httpx.Client,
    base: str,
    out: Path,
    names: list[str],
    teacher: dict[str, str],
    parallel: bool,
    show_text: bool,
) -> None:
    def send(index: int, name: str) -> None:
        audio = (out / name).read_bytes()
        media = "audio/wav" if name.endswith(".wav") else "audio/mpeg"
        headers = dict(teacher)
        headers["X-Line-Seq"] = str(index + 1)
        response, elapsed = _timed(
            client,
            "POST",
            f"{base}/api/v1/classes/utterance",
            headers=headers,
            files={"audio": (name, audio, media)},
        )
        body = response.json() if response.status_code == 200 else {}
        _report(
            f"teacher_utterance_{index + 1}_{name}",
            elapsed,
            status=response.status_code,
            upload_bytes=len(audio),
            spanish=_looks_spanish(str(body.get("spanish_text") or "")),
            audio_b64_chars=len(str(body.get("audio_base64") or "")),
            server_timing=response.headers.get("server-timing", "-"),
        )
        if show_text:
            print(f"    synthetic heard {index + 1}: {body.get('english_text')}")

    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(names)) as pool:
            futures = [pool.submit(send, index, name) for index, name in enumerate(names)]
            for future in futures:
                future.result()
        return
    for index, name in enumerate(names):
        send(index, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Folder for synthetic audio")
    parser.add_argument("--base", default="https://babelbeam.com")
    parser.add_argument("--make-fixtures", action="store_true")
    parser.add_argument("--local-stt", action="store_true")
    parser.add_argument("--prod-read", action="store_true")
    parser.add_argument("--prod-class", nargs="*", default=None, help="Fixture files to send")
    parser.add_argument("--parallel", action="store_true", help="Send class fixtures at once")
    parser.add_argument("--show-text", action="store_true", help="Print synthetic fixture text")
    args = parser.parse_args()
    if args.make_fixtures:
        make_fixtures(args.out)
    if args.local_stt:
        local_stt(args.out, args.show_text)
    if args.prod_read:
        prod_read(args.base.rstrip("/"), args.show_text)
    if args.prod_class is not None:
        names = args.prod_class or ["short.mp3"]
        prod_class(args.base.rstrip("/"), args.out, names, args.parallel, args.show_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
