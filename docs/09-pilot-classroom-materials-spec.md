# BabelBeam — Cursor Implementation Specification

**Source:** Product feedback from Tom's live catechesis/RCIA classroom pilot, November 2026  
**Audience:** Cursor coding agent working in the existing BabelBeam repository  
**Goal:** Implement a focused, reliable classroom experience and reusable bilingual post-class teaching materials without disrupting existing live translation.

## 0. Instructions to Cursor

1. Inspect the repository, architecture, current routes, models, persistence, authentication, deployment, and existing tests before editing. Do not assume frameworks, APIs, or existing feature names.
2. Produce a brief implementation plan identifying files, migrations, and risks, then implement in small testable increments. Reuse existing components and patterns.
3. Preserve current teacher start-class, student QR/code join, English-to-Spanish streaming captions/audio, glossary, and moderated questions. Do not regress latency or classroom reliability.
4. Keep the original transcript immutable. Never insert AI-generated content into a verbatim record. Separate recognized source speech, translations actually delivered, human corrections, and AI-enriched teaching material.
5. All newly generated teaching materials must be **drafts requiring instructor review** before student publication. Do not claim doctrinal accuracy without verified grounding and review.
6. Make all new AI features resilient to failure, retryable, and observable; do not block the live classroom stream on summarization or document generation.
7. If platform constraints prevent a feature (particularly background microphone operation), document and implement the best supported behavior rather than claiming it works.
8. Add appropriate tests and update user-facing help. At the end, report what was changed, what was tested, and anything requiring product decisions.

## 1. Pilot context and validated needs

Tom teaches a mixed-language Catholic catechesis/RCIA/confirmation class. Students include Spanish-speaking adults, bilingual students, cradle Catholics, and former Protestants. The app is already being used in actual classes. Tom reports that the translations appear useful and that a student can follow references to Bible passages quickly; however, this **does not prove** translation accuracy or comprehension. Some students are shy, rarely ask questions, and may already know the Catholic-specific material.

Tom's stated priorities:
- Stop having to touch/wiggle the phone periodically to prevent the lesson from stopping when the display locks.
- Save the complete lesson and what students actually received in translation.
- Automatically transform the lesson into a **structured outline/lesson plan in English and Spanish**.
- Lightly augment the lesson plan only to fill significant gaps, clarify assumed background knowledge, or improve stand-alone readability; preserve Tom's voice and teaching intent.
- Share lesson materials with absent students using a simple link.
- Offer an **optional, on-demand quiz**, not an automatic test after every lesson.
- Remove the unnecessary box around student captions and use much more of the screen.
- Make questions easy and welcoming; alert the teacher with a gentle sound and a highlighted question.
- Eventually test with additional teachers, including Chris Rose and a former Spanish-speaking student Tom knows, with permission.

## 2. Scope and priority

### P0 — Classroom reliability and readability

#### 2.1 Screen-lock and background audio/microphone behavior

**Problem:** Tom sets his device screen-lock delay to 10 minutes and manually touches the screen to keep BabelBeam working. Accidental locking can interrupt class.

**Required investigation and implementation:**
- Determine the exact device/OS/browser and whether Tom's issue concerns the **teacher's microphone capture**, the **student's audio playback**, or both. Test each separately on real devices.
- For supported foreground web sessions, use the Screen Wake Lock API with clear active/inactive status, re-acquisition after visibility changes when permitted, and graceful fallback/instructions when unsupported.
- Assess installable PWA behavior and mobile OS restrictions. An installed PWA does **not** guarantee microphone recording or audio playback with a locked screen.
- If reliable lock-screen teacher microphone capture is essential and not supported by the current web/PWA stack, design a native iOS/Android app or appropriate native wrapper with platform-compliant audio-session/background capabilities and explicit microphone permissions. Validate actual behavior before promising it.
- For student translated-audio playback, assess supported background media playback separately.
- Display clear status and recovery UX for paused capture, lost microphone permission, network interruption, and reconnect.
- Do not silently prevent a user's screen from locking without an understandable control; expose a teacher setting such as **Keep screen awake during class** where supported.

**Acceptance:** A 30-minute real-device test demonstrates uninterrupted supported behavior or clearly documents OS limitations and recovery. Test screen off, lock, app switch, incoming call, connectivity loss, and reconnect where feasible.

#### 2.2 Student screen redesign

**Problem:** Translated text is constrained inside a small bordered card and competes with menus.

**Requirements:**
- Remove the inner caption card/border and maximize usable viewport for translated text.
- Show large, high-contrast, responsive captions; support text scaling and accessibility.
- Prioritize only (a) live translated text, (b) an obvious listen/audio control, and (c) an easy-to-find **Ask a Question** control.
- Hide secondary navigation behind a compact, accessible menu; keep connection/translation state visible but unobtrusive.
- Preserve readable history/scroll behavior; avoid aggressive auto-scroll while a student is reviewing earlier captions.
- Support mobile safe areas, portrait/landscape, screen readers, and keyboard accessibility.
- Maintain simple Spanish-first student UX when Spanish is selected.

**Acceptance:** On common phone sizes, translated captions occupy most of the screen and remain legible; all primary actions are accessible without hunting through menus.

#### 2.3 Durable transcript and delivered-translation capture

**Problem:** Existing translated utterances may be discarded after delivery. Tom wants a full audit trail and materials for absent students.

**Requirements:**
- Persist each lesson/session and ordered segments with timestamps, speaker/source if available, recognized English text, target language, and **the exact Spanish text delivered** to the student. Store recognition/translation status, segment IDs, and optional model/version metadata for diagnostics.
- Preserve source speech recognition output as recorded; distinguish it from raw audio (do not imply audio is stored unless explicitly enabled).
- Keep corrections and enhanced versions separate; support instructor correction with revision history.
- Clearly label recognition uncertainty and gaps where detectable. Do not fabricate missing segments.
- Secure session storage with instructor/organization authorization, retention/deletion controls, and consent/notice workflow appropriate to classroom participants, including minors where applicable.
- Do not persist audio by default merely to satisfy text transcript requirements. Evaluate privacy, costs, and consent before enabling audio recording.
- Provide an instructor **Transcript** page with English and Spanish side-by-side or toggle views, timestamps, search, copy, and download.
- Ensure streaming translation continues if transcript persistence is temporarily unavailable: queue/retry with bounded buffering and alert the teacher about any unrecoverable gaps.

**Acceptance:** A lesson survives page refresh/restart; ordered source and delivered translation can be reviewed and exported; missing segments are flagged rather than silently concealed.

### P1 — Post-class teaching resources and participation

#### 2.4 Automatic bilingual lesson outline / lesson plan

**Trigger:** After a class ends, automatically generate a **draft** lesson outline/lesson plan from the saved source transcript. Make it accessible on the teacher dashboard. Use an async job with status, retry, and failure reporting; do not promise a fixed 10-second completion time.

**Required structure (editable):**
1. Lesson title, date, class/course, language, and overview.
2. Main topics grouped logically into numbered sections and bullets.
3. Key ideas and explanations actually covered.
4. Relevant Bible passages and theological terms **only when supported by the transcript or independently verified references**.
5. Brief recap / takeaways for absent students.
6. Optional discussion prompts or suggested follow-up, clearly identified as generated additions.
7. Source references to transcript timestamps/segments when practical.

**Languages:** Produce English and Spanish versions of the same reviewed lesson material. Allow the teacher to compare and edit both. Translation should preserve the meaning of approved content and glossary terminology.

**Augmentation:**
- Default to **minimal critical-gap filling**, not wholesale rewriting. Provide controls such as Off / Critical gaps only (default) / Light enhancement; optional 10% or 20% guidance is approximate, not a precise token guarantee.
- Explain missing prerequisites, assumptions from earlier lessons, or glaring omissions only where justified.
- Label AI-added material separately from what Tom actually taught. Do not silently insert it into a verbatim transcript.
- For Catholic teaching, ground proposed additions in approved/verified sources (e.g., Catechism, official Church sources) and provide citations where available. Never claim the model has verified access to every scholar or that its theological output is automatically correct.
- Require teacher approval of AI-added theological statements and the full plan before publication.

**Acceptance:** A completed session produces an editable English/Spanish draft, faithful to the actual lesson, with visibly distinguished supplemental content and review/publish controls.

#### 2.5 Lesson continuity across a multi-month course

- Group sessions into courses/cohorts; preserve lesson order.
- Allow the instructor to reference approved prior lesson summaries and course objectives when generating the next plan.
- Keep the retrieval scope limited to the correct course/organization and respect permissions.
- Mark prior-lesson context as background rather than something said in the current class.
- Avoid feeding entire raw course transcripts into every generation; use approved summaries and targeted retrieval.

**Acceptance:** A new lesson can clarify a concept established in an earlier session without falsely attributing it to today's transcript.

#### 2.6 Publish/share lesson resources

- Add a **Publish lesson** action after instructor review; generate a mobile-friendly hosted HTML page with a shareable link.
- Provide both English and Spanish views, an outline, and optional access to the transcript if the instructor explicitly allows it.
- Default to private/unpublished. Offer authenticated access or revocable unlisted links with appropriate access controls and expiration options; avoid exposing student questions or identifiable data by default.
- Provide a **Copy link** button and printable page styles. PDF export is a useful optional enhancement and need not be assumed to take minutes; simple text PDFs can generally be generated quickly.
- Support draft editing, versioning, unpublish/revoke, and delete according to retention policy.

**Acceptance:** Tom can review, publish, copy a link, and share a clean bilingual lesson page with an absent student; a revoked link no longer grants access.

#### 2.7 Optional on-demand quiz

**Trigger:** Teacher explicitly clicks **Generate Quiz** on a lesson. Do not auto-generate quizzes for every class.

- Generate an editable, low-pressure comprehension quiz from the approved lesson plan and/or transcript.
- Offer a small choice of question count and format (e.g., multiple choice, short answer, reflection/discussion).
- Include answer guidance for teacher review; support English and Spanish versions.
- Favor reflection and participation over punitive scoring; teacher controls whether and how students see it.
- Mark unsupported or potentially ambiguous questions for review; require teacher approval before sharing.

**Acceptance:** No quiz is created until requested. Teacher can review, edit, and optionally publish a bilingual quiz.

#### 2.8 Student question UX and teacher alerts

- Keep the **Ask a Question** button prominent in student view; confirm submission discreetly.
- Preserve the current moderated-question workflow and support Spanish submissions with teacher-facing translation as needed.
- On a new question, show a clear highlighted item in the teacher interface and play a **short, gentle optional notification sound** after user-enabled audio permissions/gesture requirements are satisfied.
- Provide mute/volume controls and accessible visual fallback; do not rely on sound alone.
- Consider optional theme sounds (bell/chime) as later polish, not a default religious gimmick.
- Do not automatically play a student's question aloud in class without teacher control.
- Allow teacher to acknowledge, answer, defer, or dismiss questions without making shy students feel singled out.

**Acceptance:** A question is easy to submit, visible to the teacher, and audibly indicated when sound is enabled; muted/unsupported audio still yields a clear visual alert.

### P2 — Pilot measurement, broader usability, and polish

#### 2.9 Translation quality validation

- Provide teacher/reviewer tools to inspect aligned recognized English and delivered Spanish segments.
- Support bilingual review by Naomi, Vanessa, or other volunteers **only with appropriate permission**; capture correction notes and sample-level ratings.
- Evaluate representative segments including theological terminology, Bible book names (e.g., Matthew/Mateo), references, longer explanations, and noisy speech.
- Measure transcription omissions, mistranslations, latency, and interruption rates. Do not invent a 90%+ accuracy figure or equate a student finding a Bible passage with full comprehension.
- Optionally add short, non-punitive comprehension checks to distinguish content understanding from system delivery.
- Respect the existing glossary for Latin/Greek/Hebrew/Catholic terminology and proper nouns; test glossary preservation in captions, audio, lesson plans, and quizzes.

#### 2.10 Additional pilot users and onboarding

- Keep onboarding simple for another teacher without Oliver present.
- Provide an in-app short guide: start class, invite students, manage questions, end class, review plan, publish.
- Gather explicit permission before involving new pilot users or using classroom content for demos.
- Potential future pilot contacts mentioned by Tom: experienced teacher **Chris Rose** and a former Spanish-speaking student who gave strong feedback. These are outreach leads, not product accounts to create automatically.

## 3. Suggested data model (adapt to existing architecture)

- `Course`: id, organization_id, instructor_id, title, languages, created_at.
- `ClassSession`: id, course_id, start/end times, state, transcript completeness, retention settings.
- `TranscriptSegment`: id, session_id, sequence, timestamps, speaker (optional), source_language, recognized_source_text, delivered_target_language, delivered_translation_text, processing metadata, status.
- `TranscriptCorrection`: id, segment_id, editor, corrected_text, language, reason, timestamp; immutable original remains intact.
- `LessonArtifact`: id, session_id, type (`outline`, `lesson_plan`, `quiz`), source_revision, status (`generating`, `draft`, `approved`, `published`, `failed`), English content, Spanish content, citations, AI additions, revisions, generated_at.
- `LessonPublication`: artifact_id, access policy, share token (stored securely), expiry, published_at, revoked_at.
- `StudentQuestion`: reuse existing schema, adding alert/acknowledgment metadata only as needed.

Prefer normalized models and existing DB conventions. Include indexes, idempotency, permissions, and migrations. Protect session data from cross-course and cross-tenant leakage.

## 4. Suggested teacher workflow

1. Start class; choose course; optionally enable **Keep screen awake** if supported.
2. Students join using existing QR/code and view nearly full-screen translated captions, audio control, and question button.
3. Persist recognized speech and actual delivered translation in real time, without slowing live translation.
4. Questions arrive with optional gentle sound and visual highlight; teacher moderates.
5. End class; async generation creates draft English/Spanish lesson outline/plan.
6. Teacher reviews the original transcript, checks translations, edits the plan, and accepts/rejects flagged AI additions.
7. Teacher optionally clicks **Generate Quiz** and reviews it.
8. Teacher publishes approved bilingual lesson resources and shares a revocable link.
9. Future classes can build on previously approved course material.

## 5. Quality, safety, and nonfunctional requirements

- **Latency:** Live captions/audio and question handling take priority over all post-processing jobs. Instrument end-to-end latency; preserve or improve current baseline rather than asserting an unmeasured target.
- **Reliability:** Reconnect logic, durable writes, retries, deduplication, and visible status for incomplete captures.
- **Privacy:** Notice/consent where required; protect student questions, transcripts, and links; set retention defaults; support deletion/export and least-privilege access.
- **Security:** Enforce server-side authentication/authorization on all artifacts and publish endpoints; prevent enumeration of unlisted links; sanitize HTML and generated content; apply rate limits and audit logs.
- **Accessibility:** Large type, contrast, screen readers, keyboard navigation, touch targets, non-audio alerts, reduced-motion support.
- **AI provenance:** Clearly label generated additions, citations, and source segments; no invented quotes or claims of doctrinal certainty.
- **Costs:** Async batch generation, bounded input, chunking/aggregation for long lessons, caching/versioning, observability, and cost monitoring.
- **Internationalization:** Avoid hard-coded English UI labels; preserve accents and scripture references; reuse glossary.

## 6. Required tests / acceptance checklist

- [ ] Existing start/join/live translation/audio/question flow remains functional.
- [ ] Mobile caption view removes the constrained inner box and uses available screen area.
- [ ] Screen wake-lock behavior tested on supported browsers; limitations documented.
- [ ] Native/background capture decision based on real OS tests, not assumption.
- [ ] Transcript segments persist in correct order and survive refresh/reconnect.
- [ ] Original recognized text and delivered translation remain separately auditable.
- [ ] Missing/corrupt segments are surfaced rather than invented.
- [ ] Lesson plan automatically generates after class, in English and Spanish.
- [ ] AI-added explanations are distinguished and require instructor approval.
- [ ] Course history is correctly scoped and used only when enabled.
- [ ] Publish action creates an accessible bilingual lesson page only after review.
- [ ] Link access control, revoke, and delete are tested.
- [ ] Quiz is generated only on explicit teacher request.
- [ ] Question alert works with visual-only fallback and mute option.
- [ ] Theological glossary and sample Bible references survive all transformations.
- [ ] Unauthorized users cannot retrieve transcripts or unpublished materials.
- [ ] Async AI failures do not interrupt live classroom translation.
- [ ] Tests, migration notes, and deployment steps are documented.

## 7. Product decisions to confirm, not silently assume

1. Which exact phones/OS versions do Tom and students use? Does lock-screen failure occur for teacher capture, student playback, or both?
2. Are transcript recordings text-only, or is opt-in audio recording required?
3. What notice/consent and retention period are appropriate for these classes?
4. Should English and Spanish lesson plans be generated immediately at class end, or only after the teacher corrects transcript errors? Recommended: automatic **draft**, then review.
5. Should shared lesson pages be restricted to class members or available via revocable unlisted link? Recommended: private by default.
6. What authoritative Catholic reference collection is available/licensed for grounding and citation?
7. Should student questions be included in shared materials? Recommended: exclude or anonymize by default.
8. Should quizzes be printable, interactive, or both? Recommended: start with teacher-reviewed printable/shareable content.

## 8. Suggested delivery order

**Milestone A:** Student caption redesign; question alerts; wake-lock investigation and supported web implementation.  
**Milestone B:** Durable source + delivered translation capture; instructor transcript review.  
**Milestone C:** Auto-generated bilingual outline/lesson plan; controlled minimal augmentation; teacher editing.  
**Milestone D:** Private-by-default publish/share pages; optional quiz generation; course continuity.  
**Milestone E:** Real-device lock/background validation and native app work if necessary; bilingual quality-review workflow; second-instructor pilot.

## 9. Definition of done

Tom can run a normal class without babysitting the display where technically supported, students see large distraction-free translated captions and can ask questions comfortably, and the completed class yields a **reviewable, accurate-as-recorded bilingual transcript plus an editable bilingual lesson outline**. Tom can approve and share that lesson with absent students and optionally generate a quiz. The product is explicit about technical limitations, translation uncertainty, privacy, and AI-added content.
