import type { SpeakerGender } from "./speakerGender";

/** Classic restroom-style man / woman silhouettes. Visible label is the button aria-label. */
export function GenderPersonIcon({ gender }: { gender: SpeakerGender }) {
  if (gender === "boy") {
    return (
      <svg
        className="gender-person-icon"
        viewBox="0 0 24 24"
        width="28"
        height="28"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="12" cy="4" r="2.45" fill="currentColor" />
        <path
          fill="currentColor"
          d="M6.8 8.35c0-.47.38-.85.85-.85h8.7c.47 0 .85.38.85.85v1.35c0 .47-.38.85-.85.85h-1.55V21c0 .55-.45 1-1 1h-2.2c-.55 0-1-.45-1-1v-5.4h-1.2V21c0 .55-.45 1-1 1H8.2c-.55 0-1-.45-1-1v-10.45H6.8c-.47 0-.85-.38-.85-.85V8.35z"
        />
      </svg>
    );
  }
  return (
    <svg
      className="gender-person-icon"
      viewBox="0 0 24 24"
      width="28"
      height="28"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="4" r="2.45" fill="currentColor" />
      <path
        fill="currentColor"
        d="M8.35 7.9c-.7 0-1.3.48-1.48 1.15L4.7 16.2c-.14.55.27 1.1.84 1.1h2.05l.7 3.95c.1.55.57.95 1.13.95h2.16c.56 0 1.03-.4 1.13-.95l.7-3.95h2.05c.57 0 .98-.55.84-1.1l-2.17-7.15c-.18-.67-.78-1.15-1.48-1.15H8.35z"
      />
    </svg>
  );
}
