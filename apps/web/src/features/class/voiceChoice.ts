export const STUDENT_VOICES = ["felipe", "roberta", "mateo", "valeria"] as const;

export type StudentVoice = (typeof STUDENT_VOICES)[number];

export const DEFAULT_VOICE: StudentVoice = "valeria";
export const VOICE_STORAGE = "bb-student-voice";

const LABELS: Record<StudentVoice, { en: "voiceFelipe" | "voiceRoberta" | "voiceMateo" | "voiceValeria" }> = {
  felipe: { en: "voiceFelipe" },
  roberta: { en: "voiceRoberta" },
  mateo: { en: "voiceMateo" },
  valeria: { en: "voiceValeria" },
};

export function parseVoice(value: string | null | undefined): StudentVoice {
  const key = (value ?? "").trim().toLowerCase();
  return STUDENT_VOICES.find((voice) => voice === key) ?? DEFAULT_VOICE;
}

export function previewUrl(voice: StudentVoice): string {
  return `/voices/${voice}.mp3`;
}

export function readStoredVoice(): StudentVoice {
  if (typeof localStorage === "undefined") {
    return DEFAULT_VOICE;
  }
  try {
    return parseVoice(localStorage.getItem(VOICE_STORAGE));
  } catch {
    return DEFAULT_VOICE;
  }
}

export function storeVoice(voice: StudentVoice): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    localStorage.setItem(VOICE_STORAGE, voice);
  } catch {
    // Preference only. A blocked store must not block the class.
  }
}

export function voiceLabelKey(voice: StudentVoice): (typeof LABELS)[StudentVoice]["en"] {
  return LABELS[voice].en;
}
