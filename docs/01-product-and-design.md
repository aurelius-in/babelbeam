# 01 - Product, installation, screens, and design

## 1. Purpose and scope
BabelBeam helps a parish run one shared class across English and Spanish. The teacher remains responsible for the lesson. Students listen through their own headphones, read large captions, and request a speaking turn. Support catechesis, sacramental preparation classes, adult formation, and Bible study. Do not imply that every student is a catechumen; the general student label is appropriate for multiple ministries.

The first customer scenario is Tom Louie's religious education classroom at Our Lady of Victory in Seaside, Oregon. Use his name or parish as a public endorsement only with permission. A development seed organization is not an endorsement or an authenticated production account.

### Required in the first usable release
- English -> Spanish live audio and text, with clear processing/connection states.
- One shared output stream for a class.
- Approved Latin, Greek, and Hebrew words protected inside translated explanations.
- Spanish -> English student questions, one teacher-approved student at a time.
- Teacher and student views within one app.
- QR and manually entered class-code joining.
- Installation from the website with an app icon and standalone display.
- 14-day trial, explicit automatic renewal consent, $14.99/month billing, self-service cancellation. Checkout is not connected yet.
- Tom's complimentary organization, free student participation, usage controls, privacy safeguards, and bilingual help.

### Exclude until separately approved
App Store/Play Store publication, offline cloud translation, locked-screen reliability claims, unmoderated group microphones, video, confession or pastoral counseling, certified-translation claims, voice cloning, church-approval seals, lesson-generating agents, a vector database, fine-tuning, annual pricing, automatic paid overages, per-student billing, and a referral-payment scheme.

## 2. Installation and trial journey
Build an HTTPS PWA on `babelbeam.com`. Manifest: stable `id`, `name: BabelBeam`, `short_name: BabelBeam`, `start_url: /app`, `scope: /`, `display: standalone`, approved theme/background colors, 192px and 512px icons, and a maskable icon with safe padding. Serve a separate Apple touch icon. Generate icons from a clean approved icon asset rather than shrinking the entire wordmark.

On supporting browsers, offer installation using the available browser install event. Do not assume `beforeinstallprompt` exists everywhere. Provide platform-appropriate Add to Home Screen instructions on iPhone/iPad and a browser fallback. Installation must be optional for guest students. Reference installation behavior: [S2].

The free download is the same app as the paid product. Do not create separate free/paid binaries or license checks stored solely on the phone. Installing or uninstalling does not start, reset, cancel, or renew a subscription.

Journey: landing page -> install/open -> choose Teach or Join a class -> verified teacher login -> renewal terms -> Stripe Checkout collects payment method -> trial activates -> microphone/playback setup -> start teaching. Students take the Join path and never enter this billing flow.

An unsigned visitor may view marketing, a clearly labeled prerecorded demonstration, installation help, and pricing without a card. Do not offer unauthenticated live AI processing through the marketing demo.

The server is authoritative for trial start/end and paid access. The 14-day window begins when Stripe creates the completed trial subscription, not when a file is downloaded or a browser first opens the site. Renewals are calendar months managed by Stripe, not another 14-day application timer. A welcome screen shows the actual renewal date/time and account timezone.

## 3. Routes and screens
| Route | Required experience |
| --- | --- |
| `/` | Premium parish-focused landing page, product story, three-step use, honest pricing, Start free trial, Join a class. |
| `/install` | Device-specific installation help, open-in-browser fallback, distinction between installing and activating trial. |
| `/pricing` | $0 during 14 days, then $14.99/month; card required once checkout exists; automatic renewal, cancellation, included allowance, free students. Checkout is not connected yet. |
| `/login` | Email + one-time-code login for adults who administer classes. |
| `/app` | Role/account-aware dashboard; trial/paid/complimentary state; primary Start Class button. |
| `/app/onboarding` | Organization name, language direction, adult/minor classroom setup, device check, glossary. |
| `/app/classes/new` | Lesson name, approved glossary version, listener setting, privacy notice, microphone test. |
| `/app/classes/:id` | Live catechist console, hand queue, connection health, controls, usage. |
| `/join` and `/join/:code` | Join entry or opaque invite, accessible name field/pseudonym, notices, Join and Listen. |
| `/listen/:sessionId` | Student Spanish audio/captions, text size, raise hand, speaking permission, reconnect status. |
| `/app/glossaries` | Import/edit/review/version terms, with pronunciation test and approval controls. |
| `/app/billing` | Renewal date, allowance, cancellation, payment update, invoices, no forced contact. |
| `/app/settings` | Organization and account settings, language, device preferences, logout, deletion request. |
| `/help`, `/terms`, `/privacy` | Readable customer help and reviewed policies. No invented legal approval. |
| `/admin` | Optional owner-only operational UI; protected complimentary grants and aggregate metrics, never classroom content. |

All interactive controls must be wired. A disabled action explains why. A live indicator requires actual source/media/translation health, not merely an open page.

## 4. Catechist workflow
1. Sign in. Select a lesson and approved glossary. Show account access and remaining classroom time before the class starts.
2. Connect the headset using the phone's operating-system settings. Test microphone level and a short playback sample. The app must not require pairing students' phones to the teacher's phone.
3. Tap Start Class. Backend validates access, creates rooms, assigns a worker, checks readiness, and returns the join code/QR. Do not label the class Live before the translation path is ready.
4. Show English source captions, Spanish final captions, mic level, listening student count, hand queue, active speaker, and explicit Ready/Listening/Translating/Audio delayed/Reconnecting states.
5. Approve one question. Teacher speech processing pauses during the student turn. Teacher hears the interpreted English question privately. Teacher resumes to answer in English; the class receives Spanish.
6. Pause for a break or End Class. End closes capture/output and invalidates tokens; leaving a tab must not keep a billable lecture running forever.

Place Pause, microphone state, and End Class where they cannot be confused. Require one confirmation for ending a live class, not for every ordinary teaching action. Display class codes large enough to read from the front of a room.

## 5. Student workflow
1. Scan the class QR or enter its short code. Enter an optional temporary display name, with a neutral generated alias available. Do not request email, age/date of birth, phone number, church membership, or payment details by default.
2. Review the applicable privacy/AI notice. For approved minor sessions, enforce the approved consent/admission workflow before connecting to third-party media; a generic checkbox is not a substitute.
3. Tap **Unirse y escuchar**. This explicit interaction starts playback. Microphone permission is not required to listen.
4. Listen through the student's own headphones; read Spanish captions; adjust text size; turn audio off locally without stopping the class.
5. Tap **Levantar la mano**. Wait for teacher approval. Only after approval show **Tocar para hablar**; only the student's tap requests/activates the microphone.
6. Ask in Spanish. Tap **Terminar mi turno** or use the time-limited turn completion flow. Typed questions use the same queue and moderation, not a separate unrestricted chat.

Essential strings: `Conectando`, `Escuchando`, `Traducción en curso`, `Audio retrasado`, `Reconectando`, `La clase está en pausa`, `La clase ha terminado`, `Micrófono activado`, and `Voz generada por IA. La traducción puede contener errores.`

Display a persistent mic-active indicator and a clear stop control. Do not auto-enable the mic when a teacher approves or after reconnect. Spanish captions must use actual accents; keep translations in structured English/Spanish locale files, not scattered conditional strings.

## 6. Visual system
Use the approved two-B monogram and beam. `assets/reference/approved-logo-showcase.png` is the source concept, not a production-ready transparent asset. Do not ship a showcase canvas or a white rectangular patch in the header.

Required assets: `logo-light.svg`, `logo-dark.svg`, `icon.svg`, monochrome variant, PNG exports, maskable app icons, favicon, Apple touch icon. Preserve the approved shape and wordmark character. A dark-surface logo needs a white/ice wordmark with cyan Beam and a legible icon; provide genuine alpha/vector transparency. Do not apply `filter: invert`, use CSS multiply as a substitute for transparency, or leave pale alpha fringes. Inspect at 24px, 48px, and header size against both light and dark backgrounds.

Use `design/tokens.css`: deep midnight canvas, layered navy surfaces, cyan light accents, muted warm-metal trim sparingly, off-white headings, readable cool-gray body. The product is welcoming and modern, not a nightclub or a luxury jewelry advertisement. Subtle architectural arches/light can suggest a parish setting, but no fabricated church crest or clerical endorsement.

Use a readable sans-serif such as Inter, self-hosted through an approved licensed build dependency. A restrained serif may be used for editorial marketing headings, not control labels. Do not copy font binaries from this kit; none are included.

Whitespace, clear hierarchy, modest 12-20px card radii, thin borders, limited gradients, no repeated glass boxes around logos. Classroom controls use 44px or larger touch targets, visible focus, icons plus text, and no color-only status. Support reduced motion, keyboard navigation, screen readers, 200% text zoom, portrait phones, and accessible dark/light themes. Target WCAG 2.2 AA and test contrast rather than asserting compliance.

Marketing may be dark by default. The listening screen should also offer a high-contrast light reading mode and captions from 18px through 32px. Do not make each incoming caption force a screen reader to interrupt continuously; offer a deliberate live announcement mode.

## 7. Customer-facing promises
Use: "Your words. Their language." / "Teach the faith. Keep everyone in the conversation." / "Start a class. Share the code. Be understood."

Do not use: "perfect translation", "instant with zero delay", "unlimited" without a funded approved policy, "works offline", "Church approved", or "end-to-end encrypted so nobody can access speech". The server must process speech.

Explain ordinary constraints in setup, not as hidden footnotes: internet required; phone screen remains open/unlocked in the first supported profile; translation may contain errors; synthesized voice; headphones recommended; the catechist reviews key terms and clarifies uncertain translations.

---
