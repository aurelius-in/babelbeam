"""Generate one short sample per student voice so the owner can listen and approve.

Paid calls: one speech call per voice (four), one more with --baseline (the current
production voice without steering), and one transcription call per sample with --check.
Samples go to a gitignored folder. Output is limited to voice names, sizes, durations,
latencies, a pitch estimate, and the transcript of the fixed sample sentence.
"""

from __future__ import annotations

import argparse
import array
import concurrent.futures
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "backend"))

from app.voices import CLASS_VOICES, VOICE_IDS  # noqa: E402

OPENAI_BASE = "https://api.openai.com/v1"
STT_MODEL = "gpt-transcribe"
SENTENCE = "La paz sea con ustedes. Hoy vamos a hablar del bautismo."
PITCH_RATE = 8000
_ATTEMPTS = 2
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


@dataclass
class Sample:
    name: str
    provider_voice: str
    steered: bool
    path: str = ""
    status: int = 0
    tts_ms: int = 0
    bytes: int = 0
    codec: str = ""
    sample_rate: int = 0
    channels: int = 0
    bit_rate: int = 0
    duration_s: float = 0.0
    median_f0_hz: float = 0.0
    voiced_frames: int = 0
    words_per_second: float = 0.0
    transcript: str = ""
    languages: list[str] = field(default_factory=list)
    transcript_matches: bool = False
    word_errors: int = -1


def _key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set.")
    return key


def _post(client: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
    """One bounded retry for rate limits, server errors, and timeouts."""
    for attempt in range(_ATTEMPTS):
        try:
            response = client.post(url, **kwargs)  # type: ignore[arg-type]
        except httpx.TimeoutException:
            if attempt + 1 == _ATTEMPTS:
                raise
        else:
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt + 1 == _ATTEMPTS:
                return response
        time.sleep(1.5 + random.random())
    raise RuntimeError("unreachable")


def _speak(client: httpx.Client, model: str, sample: Sample, instructions: str, out: Path) -> None:
    payload: dict[str, str] = {
        "model": model,
        "voice": sample.provider_voice,
        "input": SENTENCE,
        "response_format": "mp3",
    }
    if instructions:
        payload["instructions"] = instructions
    started = time.perf_counter()
    response = _post(client, f"{OPENAI_BASE}/audio/speech", json=payload)
    sample.tts_ms = round((time.perf_counter() - started) * 1000)
    sample.status = response.status_code
    if response.status_code != 200 or not response.content:
        return
    target = out / f"{sample.name}.mp3"
    target.write_bytes(response.content)
    sample.path = str(target)
    sample.bytes = len(response.content)


def _probe(sample: Sample) -> None:
    binary = shutil.which("ffprobe")
    if binary is None or not sample.path:
        return
    result = subprocess.run(
        [
            binary,
            "-v", "error",
            "-show_entries",
            "format=duration,format_name,bit_rate:stream=codec_name,sample_rate,channels",
            "-of", "json",
            sample.path,
        ],
        capture_output=True,
        check=True,
        timeout=60,
        text=True,
    )
    info = json.loads(result.stdout)
    streams = info.get("streams") or [{}]
    stream = streams[0]
    fmt = info.get("format") or {}
    sample.codec = str(stream.get("codec_name") or "")
    sample.sample_rate = int(stream.get("sample_rate") or 0)
    sample.channels = int(stream.get("channels") or 0)
    sample.duration_s = round(float(fmt.get("duration") or 0.0), 3)
    sample.bit_rate = int(fmt.get("bit_rate") or 0)
    if sample.duration_s > 0:
        sample.words_per_second = round(len(SENTENCE.split()) / sample.duration_s, 2)


def _pcm(path: str) -> array.array[int]:
    binary = shutil.which("ffmpeg")
    if binary is None:
        raise SystemExit("ffmpeg is required for the pitch estimate.")
    result = subprocess.run(
        [binary, "-v", "error", "-i", path, "-ac", "1", "-ar", str(PITCH_RATE), "-f", "s16le", "-"],
        capture_output=True,
        check=True,
        timeout=60,
    )
    samples = array.array("h")
    samples.frombytes(result.stdout[: len(result.stdout) // 2 * 2])
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _pitch(sample: Sample) -> None:
    """Median F0 from normalized autocorrelation. A rough gender check, not an age measure."""
    if not sample.path:
        return
    signal = [float(value) for value in _pcm(sample.path)]
    frame, hop = 320, 160
    low_lag, high_lag = PITCH_RATE // 400, PITCH_RATE // 60
    frames = [signal[start : start + frame] for start in range(0, len(signal) - frame, hop)]
    energies = [sum(value * value for value in chunk) / frame for chunk in frames]
    if not energies:
        return
    loud = sorted(energies)[int(len(energies) * 0.9)]
    found: list[float] = []
    for chunk, energy in zip(frames, energies, strict=True):
        if energy < 0.2 * loud:
            continue
        scores: list[float] = []
        for lag in range(low_lag, high_lag + 1):
            head, tail = chunk[: frame - lag], chunk[lag:]
            power = sum(value * value for value in head) * sum(value * value for value in tail)
            scores.append(sum(a * b for a, b in zip(head, tail, strict=True)) / power**0.5)
        best = max(scores)
        if best < 0.6:
            continue
        for index in range(1, len(scores) - 1):
            score = scores[index]
            if score >= 0.85 * best and scores[index - 1] <= score >= scores[index + 1]:
                found.append(PITCH_RATE / (low_lag + index))
                break
    sample.voiced_frames = len(found)
    if found:
        sample.median_f0_hz = round(statistics.median(found), 1)


def _words(text: str) -> list[str]:
    lowered = unicodedata.normalize("NFC", text).casefold()
    return re.findall(r"[^\W_]+", lowered)


def _distance(first: list[str], second: list[str]) -> int:
    row = list(range(len(second) + 1))
    for i, word in enumerate(first, start=1):
        previous, row[0] = row[0], i
        for j, other in enumerate(second, start=1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (word != other))
    return row[-1]


def _transcribe(client: httpx.Client, sample: Sample) -> None:
    if not sample.path:
        return
    audio = Path(sample.path).read_bytes()
    response = _post(
        client,
        f"{OPENAI_BASE}/audio/transcriptions",
        files={"file": (f"{sample.name}.mp3", audio, "audio/mpeg")},
        data={"model": STT_MODEL},
    )
    if response.status_code != 200:
        sample.transcript = f"(transcription status {response.status_code})"
        return
    body = response.json()
    sample.transcript = " ".join(str(body.get("text") or "").split())
    detected = body.get("languages")
    if isinstance(detected, list):
        sample.languages = [
            str(item.get("code"))
            for item in detected
            if isinstance(item, dict) and item.get("code")
        ]
    sample.word_errors = _distance(_words(SENTENCE), _words(sample.transcript))
    sample.transcript_matches = sample.word_errors == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "voice-samples")
    parser.add_argument("--model", default="gpt-4o-mini-tts")
    parser.add_argument("--baseline", action="store_true", help="Also marin without steering")
    parser.add_argument("--check", action="store_true", help="Transcribe each sample")
    parser.add_argument("--show-text", action="store_true", help="Print the transcripts")
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[Sample, str]] = [
        (Sample(voice_id, CLASS_VOICES[voice_id].provider_voice, True),
         CLASS_VOICES[voice_id].instructions)
        for voice_id in VOICE_IDS
    ]
    if args.baseline:
        jobs.append((Sample("baseline-marin", "marin", False), ""))
    headers = {"Authorization": f"Bearer {_key()}"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers) as client:
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(_speak, client, args.model, sample, instructions, out)
                for sample, instructions in jobs
            ]
            for future in futures:
                future.result()
        wall_ms = round((time.perf_counter() - started) * 1000)
        for sample, _instructions in jobs:
            _probe(sample)
            _pitch(sample)
            if args.check:
                _transcribe(client, sample)
    samples = [sample for sample, _instructions in jobs]
    print(f"model={args.model} parallel_tts_wall_ms={wall_ms} samples={len(samples)}")
    for sample in samples:
        print(
            f"{sample.name:<15} voice={sample.provider_voice:<6} status={sample.status} "
            f"tts_ms={sample.tts_ms} bytes={sample.bytes} codec={sample.codec} "
            f"rate={sample.sample_rate} ch={sample.channels} kbps={sample.bit_rate // 1000} "
            f"duration_s={sample.duration_s} words_per_s={sample.words_per_second} "
            f"median_f0_hz={sample.median_f0_hz} voiced_frames={sample.voiced_frames} "
            f"transcript_matches={sample.transcript_matches} word_errors={sample.word_errors} "
            f"languages={'/'.join(sample.languages) or '-'}"
        )
        if args.show_text and sample.transcript:
            print(f"    transcript: {sample.transcript}")
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": args.model,
        "sentence": SENTENCE,
        "parallel_tts_wall_ms": wall_ms,
        "voices": {
            voice_id: {
                "provider_voice": CLASS_VOICES[voice_id].provider_voice,
                "instructions": CLASS_VOICES[voice_id].instructions,
            }
            for voice_id in VOICE_IDS
        },
        "samples": [asdict(sample) for sample in samples],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8")
    return 0 if all(sample.status == 200 for sample in samples) else 1


if __name__ == "__main__":
    sys.exit(main())
