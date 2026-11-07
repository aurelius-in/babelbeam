# Provider/dependency verification record
Prepared from official documentation on October 15, 2026. Documentation review is not an account-level capability test.

| Component | Candidate / design choice | Locked version | Actual smoke test | Notes |
| --- | --- | --- | --- | --- |
| Frontend | React 19 / TypeScript 5.7 / Vite 6.1 | package-lock from `npm install` on 2026-10-15 | `npm test`, `npm run build` passed locally | Not a device install test. |
| Backend | FastAPI 0.115.6 / Pydantic 2.10.6 / SQLAlchemy 2.0.36 / Alembic 1.14.1 | Pinned in `services/backend/requirements.txt` | `pytest` and offline Alembic SQL passed | Database migration was not applied. |
| Media | LiveKit Cloud + JS/Python RTC SDKs | Pending | Not run | Separate room types; test token revocation. |
| STT | gpt-transcribe for a finished utterance. gpt-live-transcribe remains the realtime candidate and was not called. | Speech-to-text guide and model page checked 2026-10-15. File route `POST /v1/audio/transcriptions`. | Production class on 2026-10-15: an English MP3 fixture returned Spanish `La paz sea contigo.` and one shared `audio/mpeg`. A Spanish MP3 fixture returned English `Thank you. Peace be with you too.` for the teacher only. | This host does not keep a realtime transcription socket. Empty recognition returns an error and does not invent text. |
| Text translation | gpt-5.4-mini-2026-03-17 | Snapshot confirmed on the model page 2026-10-15 | 200 from `POST /v1/responses` with `store` false, `reasoning.effort` none, `tool_choice` none. Public `POST /api/v1/interpret` returned `La paz sea contigo.` | No tools. Input is untrusted and is not logged. |
| TTS | gpt-4o-mini-tts | Alias on the speech guide and model page checked 2026-10-24. Default snapshot listed there: gpt-4o-mini-tts-2025-12-15. The page marks this model deprecated with a January 6, 2027 shutdown. The documented `instructions` parameter is used for student Spanish personas and for teacher-side English question voices. | Local samples on 2026-10-24: Felipe `cedar`, Roberta `sage`, Mateo `verse`, Valeria `marin`, all 200 `audio/mpeg`. Production line on 2026-10-24 synthesized Felipe and Mateo once each for the same Spanish line. Teacher English question playback (2026-10-24 owner update): boy uses Mateo provider `verse` with young-man English steering; girl uses Valeria provider `marin` with young-woman English steering. Not marketed or steered as child voices. | No ElevenLabs, Azure, or Google credentials exist on the project. Age is steered by instructions, not a documented age field. Synthetic voices only. |
| Billing | Stripe subscription-level 14-day free trial at 1499 USD cents | Pending API/SDK pin | Not run | Checkout is not connected. Do not confuse with paid/item-level trial-offer APIs. |
| Identity | Supabase email OTP | Pending | Not run | Per-request isolated auth clients. |
| Database/cache | PostgreSQL / ephemeral Redis | Pending | Not run | Private network; no transcript persistence. |

Record official source URL, package version, model ID/snapshot, account capability, configured region, retention review, rate limits, output format, voice, verified rate card date, and failure behavior. Tests may incur provider costs; obtain approval before spending beyond a small agreed test budget.

---
