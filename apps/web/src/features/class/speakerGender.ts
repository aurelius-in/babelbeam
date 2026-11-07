export const SPEAKER_GENDERS = ["boy", "girl"] as const;

export type SpeakerGender = (typeof SPEAKER_GENDERS)[number];

export const DEFAULT_GENDER: SpeakerGender = "girl";
export const GENDER_STORAGE = "bb-student-gender";

export function genderAriaKey(gender: SpeakerGender): "genderMale" | "genderFemale" {
  return gender === "boy" ? "genderMale" : "genderFemale";
}

export function parseGender(value: string | null | undefined): SpeakerGender {
  const key = (value ?? "").trim().toLowerCase();
  if (key === "boy" || key === "male" || key === "m" || key === "hombre" || key === "masculino") {
    return "boy";
  }
  if (
    key === "girl" ||
    key === "female" ||
    key === "f" ||
    key === "mujer" ||
    key === "femenino"
  ) {
    return "girl";
  }
  return DEFAULT_GENDER;
}

export function readStoredGender(): SpeakerGender {
  if (typeof localStorage === "undefined") {
    return DEFAULT_GENDER;
  }
  try {
    return parseGender(localStorage.getItem(GENDER_STORAGE));
  } catch {
    return DEFAULT_GENDER;
  }
}

export function storeGender(gender: SpeakerGender): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    localStorage.setItem(GENDER_STORAGE, gender);
  } catch {
    // Preference only.
  }
}
