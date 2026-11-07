/** Short teacher alert when a new student question arrives. Browser-only. */

const SOUND_PREF_KEY = "bb-question-sound";

let context: AudioContext | null = null;
const memoryPrefs = new Map<string, string>();

function readPref(key: string): string | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem(key);
    }
  } catch {
    // Fall through to memory.
  }
  return memoryPrefs.get(key) ?? null;
}

function writePref(key: string, value: string): void {
  memoryPrefs.set(key, value);
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Memory map still holds the value for this session.
  }
}

export function readQuestionSoundPref(): boolean {
  return readPref(SOUND_PREF_KEY) !== "0";
}

export function storeQuestionSoundPref(enabled: boolean): void {
  writePref(SOUND_PREF_KEY, enabled ? "1" : "0");
}

export function playQuestionDing(options?: { muted?: boolean }): void {
  if (options?.muted || !readQuestionSoundPref()) {
    return;
  }
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) {
      return;
    }
    context ??= new AudioCtx();
    const now = context.currentTime;
    const gain = context.createGain();
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.28);
    gain.connect(context.destination);
    const first = context.createOscillator();
    first.type = "sine";
    first.frequency.setValueAtTime(880, now);
    first.connect(gain);
    first.start(now);
    first.stop(now + 0.14);
    const second = context.createOscillator();
    second.type = "sine";
    second.frequency.setValueAtTime(1174.7, now + 0.12);
    second.connect(gain);
    second.start(now + 0.12);
    second.stop(now + 0.28);
    void context.resume();
  } catch {
    // Autoplay or AudioContext limits must not break the class console.
  }
}
