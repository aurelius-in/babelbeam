import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useI18n } from "../../app/i18n";
import { courseIdFromTitle, storeCoursePref } from "./coursePref";
import { lessonSmsMessage, smsComposeUrl } from "./smsShare";
import {
  downloadTextFile,
  transcriptFilename,
  transcriptJson,
  transcriptPlainText,
} from "./transcriptExport";

type AugmentMode = "off" | "critical" | "light";

type CourseMemoryItem = {
  lesson_id?: string;
  title?: string;
  english?: string;
  ended_at?: string;
};

type CourseHistoryItem = {
  lesson_id?: string;
  course_title?: string;
  outline_status?: string;
  segment_count?: number;
  ended_at?: number | null;
};

type Segment = {
  id: string;
  t?: number;
  recognized_english?: string;
  delivered_spanish?: string;
  status?: string;
};

type AiAddition = {
  id: string;
  kind?: string;
  text_en?: string;
  text_es?: string;
  rationale?: string;
  accepted?: boolean;
};

type Lesson = {
  id: string;
  status?: string;
  course_id?: string;
  course_title?: string;
  segments?: Segment[];
  corrections?: { segment_id: string; language: string; corrected_text: string }[];
  quality_notes?: { segment_id: string; rating: number; note: string }[];
  gaps?: { reason?: string }[];
  outline?: {
    status?: string;
    augmentation?: AugmentMode;
    english?: string;
    spanish?: string;
    ai_additions?: AiAddition[];
    error?: string;
  };
  course_memory?: CourseMemoryItem[];
  course_history?: CourseHistoryItem[];
  quiz?: {
    status?: string;
    english?: string;
    spanish?: string;
    items?: { id: string; prompt_en?: string; prompt_es?: string; needs_review?: boolean }[];
    error?: string;
  } | null;
  publication?: {
    status?: string;
    share_path?: string;
    include_transcript?: boolean;
  };
  retention_days?: number;
};

const lessonKey = "bb-lesson-token";
const lessonIdKey = "bb-lesson-id";

function rememberLesson(id: string, token: string) {
  sessionStorage.setItem(lessonIdKey, id);
  sessionStorage.setItem(lessonKey, token);
  try {
    const raw = sessionStorage.getItem("bb-recent-lessons");
    const list = raw ? (JSON.parse(raw) as { id: string; token: string }[]) : [];
    const next = [{ id, token }, ...list.filter((item) => item.id !== id)].slice(0, 12);
    sessionStorage.setItem("bb-recent-lessons", JSON.stringify(next));
  } catch {
    // Best-effort only.
  }
}

export function rememberEndedLesson(id: string, token: string) {
  rememberLesson(id, token);
}

export function LessonReviewPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { lessonId: routeId } = useParams();
  const [params] = useSearchParams();
  const lessonId = routeId || sessionStorage.getItem(lessonIdKey) || "";
  const tokenFromQuery = params.get("token") || "";
  const [token, setToken] = useState(
    () => tokenFromQuery || sessionStorage.getItem(lessonKey) || "",
  );
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [note, setNote] = useState("");
  const [tab, setTab] = useState<"transcript" | "outline" | "quiz" | "share">("transcript");
  const [courseTitle, setCourseTitle] = useState("");
  const [outlineEn, setOutlineEn] = useState("");
  const [outlineEs, setOutlineEs] = useState("");
  const [aiAdditions, setAiAdditions] = useState<AiAddition[]>([]);
  const [busy, setBusy] = useState(false);
  const [smsPhone, setSmsPhone] = useState("");
  const [augmentation, setAugmentation] = useState<AugmentMode>("critical");

  useEffect(() => {
    if (tokenFromQuery && lessonId) {
      rememberLesson(lessonId, tokenFromQuery);
      setToken(tokenFromQuery);
    }
  }, [tokenFromQuery, lessonId]);

  async function load() {
    if (!lessonId || !token) {
      setNote(t("lessonMissing"));
      return;
    }
    const response = await fetch(`/api/v1/lessons/${encodeURIComponent(lessonId)}`, {
      headers: { "X-Lesson-Token": token },
    });
    if (!response.ok) {
      setNote(t("lessonMissing"));
      setLesson(null);
      return;
    }
    const body = (await response.json()) as Lesson;
    setLesson(body);
    setCourseTitle(body.course_title || "");
    setOutlineEn(body.outline?.english || "");
    setOutlineEs(body.outline?.spanish || "");
    setAiAdditions(body.outline?.ai_additions || []);
    const mode = body.outline?.augmentation;
    if (mode === "off" || mode === "critical" || mode === "light") {
      setAugmentation(mode);
    }
    setNote("");
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => {
      if (lesson?.outline?.status === "queued" || lesson?.outline?.status === "generating") {
        void load();
      }
    }, 2000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lessonId, token, lesson?.outline?.status]);

  const gaps = useMemo(() => lesson?.gaps?.length || 0, [lesson]);

  async function saveCourse() {
    if (!lesson) {
      return;
    }
    setBusy(true);
    try {
      const courseId = courseIdFromTitle(courseTitle);
      const response = await fetch(`/api/v1/lessons/${lesson.id}/course`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
        body: JSON.stringify({ course_id: courseId, course_title: courseTitle }),
      });
      if (response.ok) {
        const body = (await response.json()) as Lesson;
        setLesson(body);
        storeCoursePref(courseId, courseTitle);
        setNote(t("lessonSaved"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function saveOutline(approve: boolean) {
    if (!lesson) {
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/lessons/${lesson.id}/outline`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
        body: JSON.stringify({
          english: outlineEn,
          spanish: outlineEs,
          ai_additions: aiAdditions,
          approve,
        }),
      });
      if (response.ok) {
        const body = (await response.json()) as Lesson;
        setLesson(body);
        setNote(approve ? t("lessonApproved") : t("lessonSaved"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function regenerateOutline() {
    if (!lesson) {
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/lessons/${lesson.id}/outline`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
        body: JSON.stringify({ regenerate: true, augmentation }),
      });
      if (response.ok) {
        setLesson((await response.json()) as Lesson);
        setNote(t("lessonOutlineWorking"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function generateQuiz() {
    if (!lesson) {
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/lessons/${lesson.id}/quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
        body: JSON.stringify({ generate: true, count: 5 }),
      });
      if (response.ok) {
        setLesson((await response.json()) as Lesson);
        setTab("quiz");
        setNote(t("lessonQuizReady"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function publish(includeTranscript: boolean) {
    if (!lesson) {
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/lessons/${lesson.id}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
        body: JSON.stringify({ include_transcript: includeTranscript }),
      });
      if (response.ok) {
        setLesson((await response.json()) as Lesson);
        setTab("share");
        setNote(t("lessonPublished"));
      } else {
        setNote(t("lessonPublishNeedOutline"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function unpublish() {
    if (!lesson) {
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/lessons/${lesson.id}/unpublish`, {
        method: "POST",
        headers: { "X-Lesson-Token": token },
      });
      if (response.ok) {
        setLesson((await response.json()) as Lesson);
        setNote(t("lessonUnpublished"));
      }
    } finally {
      setBusy(false);
    }
  }

  function shareUrl(path: string): string {
    return `${window.location.origin}${path}`;
  }

  async function copyShare() {
    const path = lesson?.publication?.share_path;
    if (!path) {
      return;
    }
    const url = shareUrl(path);
    try {
      await navigator.clipboard.writeText(url);
      setNote(t("linkCopied"));
    } catch {
      setNote(url);
    }
  }

  async function ensurePublished(): Promise<string> {
    if (!lesson) {
      return "";
    }
    const existing = lesson.publication?.share_path;
    if (lesson.publication?.status === "published" && existing) {
      return shareUrl(existing);
    }
    const response = await fetch(`/api/v1/lessons/${lesson.id}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
      body: JSON.stringify({ include_transcript: false }),
    });
    if (!response.ok) {
      setNote(t("lessonPublishNeedOutline"));
      return "";
    }
    const body = (await response.json()) as Lesson;
    setLesson(body);
    const path = body.publication?.share_path || "";
    return path ? shareUrl(path) : "";
  }

  async function textShare() {
    setBusy(true);
    try {
      const url = await ensurePublished();
      if (!url) {
        return;
      }
      const message = lessonSmsMessage(url, courseTitle || lesson?.course_title || "");
      const href = smsComposeUrl(message, smsPhone);
      setNote(t("lessonTextOpened"));
      window.location.href = href;
    } finally {
      setBusy(false);
    }
  }

  async function rateSegment(segmentId: string, rating: number) {
    if (!lesson) {
      return;
    }
    const response = await fetch(`/api/v1/lessons/${lesson.id}/quality`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Lesson-Token": token },
      body: JSON.stringify({ segment_id: segmentId, rating, note: "" }),
    });
    if (response.ok) {
      setLesson((await response.json()) as Lesson);
    }
  }

  function downloadTranscript(kind: "txt" | "json") {
    if (!lesson) {
      return;
    }
    if (kind === "txt") {
      downloadTextFile(transcriptFilename(lesson, "txt"), transcriptPlainText(lesson), "text/plain");
    } else {
      downloadTextFile(
        transcriptFilename(lesson, "json"),
        transcriptJson(lesson),
        "application/json",
      );
    }
    setNote(t("lessonDownloaded"));
  }

  if (!lessonId || !token) {
    return (
      <main className="sheet class-sheet">
        <h1>{t("lessonTitle")}</h1>
        <p>{t("lessonMissing")}</p>
        <Link className="button button-primary" to="/app">
          {t("startClass")}
        </Link>
      </main>
    );
  }

  return (
    <main className="sheet class-sheet lesson-sheet">
      <header className="lesson-header">
        <div>
          <p className="kicker">{t("lessonKicker")}</p>
          <h1>{t("lessonTitle")}</h1>
          <p className="fine">
            {t("lessonRetention").replace("{days}", String(lesson?.retention_days || 90))}
          </p>
        </div>
        <button type="button" className="button button-quiet" onClick={() => navigate("/app")}>
          {t("startClass")}
        </button>
      </header>

      <label className="lesson-course">
        {t("lessonCourse")}
        <input value={courseTitle} onChange={(event) => setCourseTitle(event.target.value)} />
      </label>
      <button type="button" className="button" disabled={busy} onClick={() => void saveCourse()}>
        {t("lessonSaveCourse")}
      </button>
      {(lesson?.course_memory?.length || 0) > 0 ? (
        <section className="lesson-course-memory" aria-label={t("lessonCourseMemory")}>
          <p className="caption-label">{t("lessonCourseMemory")}</p>
          <ul className="lesson-memory-list">
            {(lesson?.course_memory || []).map((item) => (
              <li key={item.lesson_id || item.english}>
                <strong>{item.title || t("lessonOutline")}</strong>
                <p className="fine">{(item.english || "").slice(0, 280)}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : courseTitle.trim() ? (
        <p className="fine">{t("lessonCourseMemoryEmpty")}</p>
      ) : null}
      {(lesson?.course_history?.length || 0) > 0 ? (
        <section className="lesson-course-history" aria-label={t("lessonCourseHistory")}>
          <p className="caption-label">{t("lessonCourseHistory")}</p>
          <ul className="lesson-memory-list">
            {(lesson?.course_history || []).map((item) => (
              <li key={item.lesson_id}>
                {item.course_title || item.lesson_id} · {item.outline_status || "idle"} ·{" "}
                {item.segment_count || 0}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <nav className="lesson-tabs" aria-label={t("lessonTitle")}>
        {(
          [
            ["transcript", t("lessonTranscript")],
            ["outline", t("lessonOutline")],
            ["quiz", t("lessonQuiz")],
            ["share", t("lessonShare")],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "button button-primary" : "button"}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {gaps > 0 ? <p className="lesson-gap" role="status">{t("lessonGaps").replace("{count}", String(gaps))}</p> : null}
      {note ? <p role="status">{note}</p> : null}

      {tab === "transcript" ? (
        <section className="lesson-panel">
          <p className="fine">{t("lessonTranscriptHint")}</p>
          <div className="lesson-actions">
            <button type="button" className="button" onClick={() => downloadTranscript("txt")}>
              {t("lessonDownloadTxt")}
            </button>
            <button type="button" className="button" onClick={() => downloadTranscript("json")}>
              {t("lessonDownloadJson")}
            </button>
          </div>
          <ul className="lesson-segments">
            {(lesson?.segments || []).map((item) => (
              <li key={item.id} className="lesson-segment">
                <div className="lesson-bilingual">
                  <p>
                    <span className="caption-label">EN</span> {item.recognized_english}
                  </p>
                  <p>
                    <span className="caption-label">ES</span> {item.delivered_spanish}
                  </p>
                </div>
                <div className="lesson-segment-actions">
                  {[1, 2, 3, 4, 5].map((rating) => (
                    <button
                      key={rating}
                      type="button"
                      className="button button-quiet"
                      aria-label={`${t("lessonRate")} ${rating}`}
                      onClick={() => void rateSegment(item.id, rating)}
                    >
                      {rating}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {tab === "outline" ? (
        <section className="lesson-panel">
          <p className="fine">
            {t("lessonOutlineStatus")}: {lesson?.outline?.status || "idle"}
          </p>
          {lesson?.outline?.error ? <p role="status">{lesson.outline.error}</p> : null}
          <fieldset className="lesson-augment">
            <legend>{t("lessonAugmentLabel")}</legend>
            <p className="fine">{t("lessonAugmentHint")}</p>
            {(
              [
                ["off", t("lessonAugmentOff")],
                ["critical", t("lessonAugmentCritical")],
                ["light", t("lessonAugmentLight")],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="teacher-toggle">
                <input
                  type="radio"
                  name="lesson-augment"
                  checked={augmentation === value}
                  onChange={() => setAugmentation(value)}
                />
                <span>{label}</span>
              </label>
            ))}
          </fieldset>
          <div className="lesson-actions">
            <button type="button" className="button" disabled={busy} onClick={() => void regenerateOutline()}>
              {t("lessonRegenerate")}
            </button>
            <button type="button" className="button" disabled={busy} onClick={() => void saveOutline(false)}>
              {t("lessonSaveDraft")}
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={busy}
              onClick={() => void saveOutline(true)}
            >
              {t("lessonApprove")}
            </button>
          </div>
          <label>
            {t("lessonOutlineEn")}
            <textarea className="interpret-text" rows={12} value={outlineEn} onChange={(event) => setOutlineEn(event.target.value)} />
          </label>
          <label>
            {t("lessonOutlineEs")}
            <textarea className="interpret-text" rows={12} value={outlineEs} onChange={(event) => setOutlineEs(event.target.value)} />
          </label>
          {aiAdditions.length > 0 ? (
            <div className="lesson-ai">
              <p className="caption-label">{t("lessonAiAdditions")}</p>
              {aiAdditions.map((item, index) => (
                <label key={item.id} className="teacher-toggle">
                  <input
                    type="checkbox"
                    checked={Boolean(item.accepted)}
                    onChange={(event) => {
                      const next = aiAdditions.slice();
                      next[index] = { ...item, accepted: event.target.checked };
                      setAiAdditions(next);
                    }}
                  />
                  <span>
                    {item.text_en} / {item.text_es}
                  </span>
                </label>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "quiz" ? (
        <section className="lesson-panel">
          <p className="fine">{t("lessonQuizHint")}</p>
          <button type="button" className="button button-primary" disabled={busy} onClick={() => void generateQuiz()}>
            {t("lessonGenerateQuiz")}
          </button>
          {lesson?.quiz?.status ? (
            <p role="status">
              {t("lessonOutlineStatus")}: {lesson.quiz.status}
            </p>
          ) : null}
          {lesson?.quiz?.error ? <p role="status">{lesson.quiz.error}</p> : null}
          {lesson?.quiz?.items?.length ? (
            <ol className="lesson-quiz-list">
              {lesson.quiz.items.map((item) => (
                <li key={item.id}>
                  <p>{item.prompt_en}</p>
                  <p className="fine">{item.prompt_es}</p>
                  {item.needs_review ? <p className="lesson-gap">{t("lessonNeedsReview")}</p> : null}
                </li>
              ))}
            </ol>
          ) : null}
        </section>
      ) : null}

      {tab === "share" ? (
        <section className="lesson-panel">
          <p className="fine">{t("lessonShareHint")}</p>
          <div className="lesson-actions">
            <button type="button" className="button button-primary" disabled={busy} onClick={() => void publish(false)}>
              {t("lessonPublish")}
            </button>
            <button type="button" className="button" disabled={busy} onClick={() => void publish(true)}>
              {t("lessonPublishWithTranscript")}
            </button>
            <button type="button" className="button" disabled={busy} onClick={() => void unpublish()}>
              {t("lessonUnpublish")}
            </button>
            <button type="button" className="button" onClick={() => void copyShare()}>
              {t("copyLink")}
            </button>
          </div>
          <label className="lesson-course">
            {t("lessonTextPhone")}
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder={t("lessonTextPhoneHint")}
              value={smsPhone}
              onChange={(event) => setSmsPhone(event.target.value)}
            />
          </label>
          <p className="fine">{t("lessonTextHint")}</p>
          <button
            type="button"
            className="button button-primary"
            disabled={busy}
            onClick={() => void textShare()}
          >
            {t("lessonTextLink")}
          </button>
          {lesson?.publication?.share_path ? (
            <p>
              <Link to={lesson.publication.share_path}>{lesson.publication.share_path}</Link>
            </p>
          ) : null}
          {lesson?.publication?.status === "published" && lesson.publication.share_path ? (
            <button
              type="button"
              className="button"
              onClick={() => window.open(lesson.publication?.share_path, "_blank", "noopener")}
            >
              {t("lessonPrint")}
            </button>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}

export function ShareLessonPage() {
  const { t } = useI18n();
  const { shareToken = "" } = useParams();
  const [payload, setPayload] = useState<{
    course_title?: string;
    outline?: { english?: string; spanish?: string; ai_additions?: AiAddition[] };
    quiz?: { english?: string; spanish?: string } | null;
    transcript?: { english?: string; spanish?: string }[] | null;
    disclaimer?: string;
  } | null>(null);
  const [lang, setLang] = useState<"en" | "es">("es");
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const response = await fetch(`/api/v1/share/${encodeURIComponent(shareToken)}`);
      if (cancelled) {
        return;
      }
      if (!response.ok) {
        setMissing(true);
        return;
      }
      setPayload(await response.json());
    })();
    return () => {
      cancelled = true;
    };
  }, [shareToken]);

  if (missing) {
    return (
      <main className="sheet class-sheet">
        <h1>{t("lessonShareGone")}</h1>
      </main>
    );
  }

  if (!payload) {
    return (
      <main className="sheet class-sheet">
        <p role="status">{t("lessonLoading")}</p>
      </main>
    );
  }

  const outline = lang === "es" ? payload.outline?.spanish : payload.outline?.english;
  const quiz = lang === "es" ? payload.quiz?.spanish : payload.quiz?.english;

  return (
    <main className="sheet class-sheet share-sheet">
      <header className="lesson-header">
        <div>
          <p className="kicker">BabelBeam</p>
          <h1>{payload.course_title || t("lessonTitle")}</h1>
        </div>
        <div className="lang-switch" role="group" aria-label={t("language")}>
          <button type="button" className={lang === "en" ? "lang-button active" : "lang-button"} onClick={() => setLang("en")}>
            EN
          </button>
          <button type="button" className={lang === "es" ? "lang-button active" : "lang-button"} onClick={() => setLang("es")}>
            ES
          </button>
        </div>
      </header>
      <p className="how-actions no-print">
        <button type="button" className="button button-primary" onClick={() => window.print()}>
          {t("lessonPrint")}
        </button>
      </p>
      <article className="share-article">
        <pre className="share-body">{outline}</pre>
        {(payload.outline?.ai_additions || []).some((item) => item.accepted) ? (
          <section>
            <h2>{t("lessonAiAdditions")}</h2>
            <ul>
              {(payload.outline?.ai_additions || [])
                .filter((item) => item.accepted)
                .map((item) => (
                  <li key={item.id}>{lang === "es" ? item.text_es : item.text_en}</li>
                ))}
            </ul>
          </section>
        ) : null}
        {quiz ? (
          <section>
            <h2>{t("lessonQuiz")}</h2>
            <pre className="share-body">{quiz}</pre>
          </section>
        ) : null}
        {payload.transcript ? (
          <section>
            <h2>{t("lessonTranscript")}</h2>
            <ul className="lesson-segments">
              {payload.transcript.map((item, index) => (
                <li key={`${index}-${item.english}`}>
                  <p>{lang === "es" ? item.spanish : item.english}</p>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </article>
      <p className="legal-disclaimer">{payload.disclaimer || t("aiDisclaimer")}</p>
    </main>
  );
}
