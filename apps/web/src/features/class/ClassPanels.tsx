import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toDataURL } from "qrcode";
import { useI18n } from "../../app/i18n";
import {
  codeFromQuery,
  formatJoinCode,
  joinUrl,
  listenerLabel,
} from "../../lib/joinCode";
import { startMicCapture, type MicCapture } from "./micCapture";
import { createLineOrder, createUploadGate, lineHeaders } from "./lineOrder";
import {
  emptyQueue,
  expirePending,
  ingest,
  knownIds,
  markPlayed,
  markPlaying,
  nextStep,
  skipToLatest,
  type FeedSegment,
  type PlaybackQueue,
} from "./playbackQueue";
import { rememberLine, type ContextLine } from "./phraseContext";
import { startTeacherCapture, type CapturedUtterance, type TeacherCapture } from "./teacherCapture";
import { readStoredVoice, storeVoice, type StudentVoice } from "./voiceChoice";
import { GenderPersonIcon } from "./GenderPersonIcon";
import {
  SPEAKER_GENDERS,
  genderAriaKey,
  readStoredGender,
  storeGender,
  type SpeakerGender,
} from "./speakerGender";
import {
  playQuestionDing,
  readQuestionSoundPref,
  storeQuestionSoundPref,
} from "./questionDing";
import {
  createWakeLockController,
  isClassAppRuntime,
  readKeepAwakePref,
  type WakeLockController,
  type WakeLockState,
} from "./wakeLock";
import { courseIdFromTitle, readCoursePref, storeCoursePref } from "../lessons/coursePref";
import { rememberEndedLesson } from "../lessons/LessonReview";
import { silentWavDataUrl } from "./wav";

const FEED_POLL_MS = 1000;
const MAX_PARALLEL_UPLOADS = 3;

type CueHandling = "open" | "deferred" | "dismissed";

type Cue = {
  id: string;
  english_text: string;
  audio_base64?: string;
  audio_content_type?: string;
  kind?: string;
  student_name?: string;
  speaker_gender?: string;
  listened?: boolean;
  handling?: CueHandling;
  created_at?: number;
};

type Spoken = {
  status?: string;
  reason?: string;
  seq?: number | null;
  spanish_text?: string;
  english_text?: string;
  audio_base64?: string;
  audio_content_type?: string;
  text?: string;
  audio_available?: boolean;
};

const teacherKey = "bb-teacher-token";
const studentKey = "bb-student-token";

function clipUrl(body: { audio_base64?: string; audio_content_type?: string }): string {
  if (!body.audio_base64 || !body.audio_content_type) {
    return "";
  }
  return `data:${body.audio_content_type};base64,${body.audio_base64}`;
}

function replyObjectUrl(body: { audio_base64?: string; audio_content_type?: string }): string {
  if (!body.audio_base64) {
    return "";
  }
  const contentType = body.audio_content_type || "audio/mpeg";
  try {
    const binary = atob(body.audio_base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return URL.createObjectURL(new Blob([bytes], { type: contentType }));
  } catch {
    return "";
  }
}

export function ClassTeacherPanel() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [code, setCode] = useState("");
  const [line, setLine] = useState("");
  const [questions, setQuestions] = useState<Cue[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [selectedQuestion, setSelectedQuestion] = useState<Cue | null>(null);
  const [replyBlocked, setReplyBlocked] = useState(false);
  const knownQuestionIdsRef = useRef<Set<string>>(new Set());
  const [spanish, setSpanish] = useState("");
  const [heard, setHeard] = useState("");
  const [cueText, setCueText] = useState("");
  const [audioSrc, setAudioSrc] = useState("");
  const [ended, setEnded] = useState(false);
  const [booting, setBooting] = useState(true);
  const [sending, setSending] = useState(false);
  const [micOn, setMicOn] = useState(false);
  const [note, setNote] = useState("");
  const [listeners, setListeners] = useState(0);
  const [qrSrc, setQrSrc] = useState("");
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [replySrc, setReplySrc] = useState("");
  const [typeOpen, setTypeOpen] = useState(false);
  const [keepAwake, setKeepAwake] = useState(readKeepAwakePref);
  const [wakeState, setWakeState] = useState<WakeLockState>(() =>
    typeof navigator !== "undefined" && "wakeLock" in navigator ? "inactive" : "unsupported",
  );
  const [questionSound, setQuestionSound] = useState(readQuestionSoundPref);
  const [questionAlert, setQuestionAlert] = useState(false);
  const [micNeedsResume, setMicNeedsResume] = useState(false);
  const playerRef = useRef<HTMLAudioElement | null>(null);
  const replyRef = useRef<HTMLAudioElement | null>(null);
  const wakeRef = useRef<WakeLockController | null>(null);
  const replyUrlRef = useRef("");
  const micRef = useRef<TeacherCapture | null>(null);
  const tokenRef = useRef("");
  const bootRef = useRef(false);
  const orderRef = useRef(createLineOrder());
  const gateRef = useRef(createUploadGate(MAX_PARALLEL_UPLOADS));
  const shownSeqRef = useRef(0);
  const contextRef = useRef<ContextLine[]>([]);
  tokenRef.current = token;

  function replaceReplySrc(src: string) {
    if (replyUrlRef.current) {
      URL.revokeObjectURL(replyUrlRef.current);
      replyUrlRef.current = "";
    }
    if (!src) {
      setReplySrc("");
      return;
    }
    replyUrlRef.current = src;
    setReplySrc(src);
  }

  function hearReply() {
    const player = replyRef.current;
    if (!player) {
      return;
    }
    const pending = player.play();
    if (pending) {
      void pending
        .then(() => setReplyBlocked(false))
        .catch(() => setReplyBlocked(true));
    }
  }

  function stopMic() {
    micRef.current?.stop();
    micRef.current = null;
    setMicOn(false);
    setMicNeedsResume(false);
  }

  async function applyStoredCourse(lessonId: string, lessonToken: string) {
    const pref = readCoursePref();
    if (!pref.course_title || !lessonId || !lessonToken) {
      return;
    }
    const courseId = pref.course_id || courseIdFromTitle(pref.course_title);
    try {
      await fetch(`/api/v1/lessons/${encodeURIComponent(lessonId)}/course`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-Lesson-Token": lessonToken,
        },
        body: JSON.stringify({ course_id: courseId, course_title: pref.course_title }),
      });
      storeCoursePref(courseId, pref.course_title);
    } catch {
      // Course continuity is best-effort; class still runs.
    }
  }

  async function setQuestionHandling(
    cueId: string,
    handling: "deferred" | "dismissed" | "open" | "heard",
  ) {
    try {
      const response = await fetch("/api/v1/classes/questions/handling", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Class-Token": token },
        body: JSON.stringify({ cue_id: cueId, handling }),
      });
      if (!response.ok) {
        return;
      }
      const body = (await response.json()) as {
        unread_count?: number;
        handling?: CueHandling;
        listened?: boolean;
      };
      setQuestions((current) =>
        current.map((cue) =>
          cue.id === cueId
            ? {
                ...cue,
                handling: body.handling || (handling === "heard" ? cue.handling : handling),
                listened: body.listened ?? true,
              }
            : cue,
        ),
      );
      if (typeof body.unread_count === "number") {
        setUnreadCount(body.unread_count);
      }
      if (selectedQuestion?.id === cueId && (handling === "deferred" || handling === "dismissed")) {
        setSelectedQuestion(null);
        setCueText("");
        replaceReplySrc("");
      }
    } catch {
      // Visual list still updates on next poll.
    }
  }

  async function playSrc(src: string) {
    if (!src) {
      return;
    }
    replyRef.current?.pause();
    setAudioSrc(src);
    const player = playerRef.current;
    if (!player) {
      return;
    }
    player.src = src;
    try {
      await player.play();
    } catch {
      // The controls stay available when the browser blocks autoplay.
    }
  }

  async function afterStudentFacing(body: Spoken, sourceEnglish = "") {
    setSpanish(body.spanish_text ?? "");
    if (sourceEnglish) {
      setHeard(sourceEnglish);
    } else if (body.english_text) {
      setHeard(body.english_text);
    }
    const src = clipUrl(body);
    if (micRef.current) {
      // Student phones play the class voice. Playing it here too would feed the open mic.
      return;
    }
    await playSrc(src);
  }

  function classGone() {
    stopMic();
    setNote(t("classGone"));
  }

  function showLine(body: Spoken, seq: number, sourceEnglish = ""): Promise<void> | undefined {
    if (seq < shownSeqRef.current) {
      return undefined;
    }
    shownSeqRef.current = seq;
    const english = sourceEnglish || body.english_text || "";
    const spanish = body.spanish_text || "";
    if (english || spanish) {
      contextRef.current = rememberLine(contextRef.current, english, spanish);
    }
    return afterStudentFacing(body, english);
  }

  async function uploadUtterance(utterance: CapturedUtterance) {
    const current = tokenRef.current;
    if (!current) {
      return;
    }
    const outgoing = orderRef.current.begin();
    try {
      await gateRef.current.run(async () => {
        if (tokenRef.current !== current) {
          return;
        }
        const form = new FormData();
        form.append("audio", utterance.blob, "speech.wav");
        form.append("context", JSON.stringify(contextRef.current));
        form.append("mode", "clean");
        const response = await fetch("/api/v1/classes/utterance", {
          method: "POST",
          headers: { "X-Class-Token": current, ...lineHeaders(outgoing) },
          body: form,
        });
        if (response.status === 404 || response.status === 409) {
          classGone();
          return;
        }
        if (!response.ok) {
          setNote(t("micFailed"));
          return;
        }
        const body = (await response.json()) as Spoken;
        if (body.status === "skipped") {
          setNote(t(body.reason === "not_english" ? "heardSpanish" : "fillerSkipped"));
          return;
        }
        setNote("");
        await showLine(body, outgoing.seq, body.english_text ?? "");
      });
    } catch {
      setNote(t("micFailed"));
    } finally {
      orderRef.current.end(outgoing.seq);
    }
  }

  async function start() {
    setNote("");
    setBooting(true);
    try {
      const response = await fetch("/api/v1/classes", { method: "POST" });
      if (!response.ok) {
        setNote(t("interpretFailed"));
        return;
      }
      const body = (await response.json()) as {
        join_code?: string;
        teacher_token?: string;
        lesson_id?: string;
        lesson_token?: string;
      };
      if (!body.join_code || !body.teacher_token) {
        setNote(t("interpretFailed"));
        return;
      }
      sessionStorage.setItem(teacherKey, body.teacher_token);
      orderRef.current.reset();
      shownSeqRef.current = 0;
      contextRef.current = [];
      knownQuestionIdsRef.current = new Set();
      setQuestions([]);
      setUnreadCount(0);
      setInboxOpen(false);
      setSelectedQuestion(null);
      setTypeOpen(false);
      setMicNeedsResume(false);

      setToken(body.teacher_token);
      setCode(body.join_code);
      setEnded(false);
      setSpanish("");
      setHeard("");
      setCueText("");
      setAudioSrc("");
      replaceReplySrc("");
      setListeners(0);
      setConfirmEnd(false);
      if (body.lesson_id && body.lesson_token) {
        void applyStoredCourse(body.lesson_id, body.lesson_token);
      }
    } catch {
      setNote(t("interpretFailed"));
    } finally {
      setBooting(false);
    }
  }

  async function sendText(text: string): Promise<boolean> {
    if (!text || !token) {
      return false;
    }
    setSending(true);
    setNote("");
    const outgoing = orderRef.current.begin();
    try {
      const response = await fetch("/api/v1/classes/line", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Class-Token": token, ...lineHeaders(outgoing) },
        body: JSON.stringify({ text, context: contextRef.current, mode: "clean" }),
      });
      if (response.status === 404) {
        classGone();
        return false;
      }
      if (!response.ok) {
        setNote(t("interpretFailed"));
        return false;
      }
      await showLine((await response.json()) as Spoken, outgoing.seq, text);
      return true;
    } catch {
      setNote(t("interpretFailed"));
      return false;
    } finally {
      orderRef.current.end(outgoing.seq);
      setSending(false);
    }
  }

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = line.trim();
    if (!text) {
      return;
    }
    const ok = await sendText(text);
    if (ok) {
      setLine("");
    }
  }

  async function toggleMic() {
    if (micRef.current) {
      stopMic();
      return;
    }
    setNote("");
    setMicNeedsResume(false);
    try {
      micRef.current = await startTeacherCapture((utterance) => {
        void uploadUtterance(utterance);
      });
      setMicOn(true);
    } catch (error) {
      const unsupported = error instanceof Error && error.message === "unsupported";
      setNote(t(unsupported ? "micFailed" : "micDenied"));
      setMicOn(false);
    }
  }

  useEffect(() => {
    function onVisibility() {
      if (document.visibilityState !== "visible") {
        return;
      }
      if (!micOn) {
        return;
      }
      const capture = micRef.current;
      if (!capture || !capture.isAlive()) {
        micRef.current = null;
        setMicOn(false);
        setMicNeedsResume(true);
        setNote(t("micNeedsResume"));
      }
      if (keepAwake && wakeState === "inactive") {
        setNote(t("wakeNeedsAttention"));
      }
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [micOn, keepAwake, wakeState, t]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(joinUrl(window.location.origin, code));
      setNote(t("linkCopied"));
    } catch {
      setNote(t("linkCopyFailed"));
    }
  }

  async function end() {
    stopMic();
    if (!token) {
      return;
    }
    let lessonId = "";
    let lessonToken = "";
    try {
      const response = await fetch("/api/v1/classes/end", {
        method: "POST",
        headers: { "X-Class-Token": token },
      });
      if (response.ok) {
        const body = (await response.json()) as { lesson_id?: string; lesson_token?: string };
        lessonId = body.lesson_id || "";
        lessonToken = body.lesson_token || "";
      }
    } catch {
      // Still leave the live console if the network drops after end.
    }
    sessionStorage.removeItem(teacherKey);
    replaceReplySrc("");
    setEnded(true);
    setToken("");
    setCode("");
    setConfirmEnd(false);
    if (lessonId && lessonToken) {
      rememberEndedLesson(lessonId, lessonToken);
      navigate(`/lessons/${encodeURIComponent(lessonId)}?token=${encodeURIComponent(lessonToken)}`, {
        replace: true,
      });
      return;
    }
    navigate("/", { replace: true });
  }

  useEffect(() => {
    if (bootRef.current) {
      return;
    }
    bootRef.current = true;
    void start();
  }, []);

  useEffect(() => {
    const controller = createWakeLockController(setWakeState);
    wakeRef.current = controller;
    return () => {
      controller.dispose();
      wakeRef.current = null;
    };
  }, []);

  useEffect(() => {
    const controller = wakeRef.current;
    if (!controller) {
      return;
    }
    void controller.setEnabled(Boolean(token) && keepAwake);
  }, [token, keepAwake]);

  useEffect(() => {
    if (!code) {
      setQrSrc("");
      return undefined;
    }
    let cancelled = false;
    void toDataURL(joinUrl(window.location.origin, code), {
      errorCorrectionLevel: "M",
      margin: 2,
      width: 280,
      color: { dark: "#071b28", light: "#ffffff" },
    })
      .then((value) => {
        if (!cancelled) {
          setQrSrc(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setQrSrc("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  async function openQuestion(item: Cue) {
    setSelectedQuestion(item);
    setCueText(item.english_text);
    setInboxOpen(true);
    setNote("");
    setReplyBlocked(false);
    playerRef.current?.pause();
    const player = replyRef.current;
    try {
      const response = await fetch(`/api/v1/classes/questions/${encodeURIComponent(item.id)}`, {
        headers: { "X-Class-Token": token },
      });
      if (!response.ok) {
        setNote(t("questionPlayFailed"));
        return;
      }
      const body = (await response.json()) as { cue?: Cue };
      const full = body.cue ?? item;
      setSelectedQuestion(full);
      setCueText(full.english_text || item.english_text);
      const url = replyObjectUrl(full);
      if (!url) {
        replaceReplySrc("");
        setNote(t("questionNoAudio"));
      } else {
        replaceReplySrc(url);
        if (player) {
          player.src = url;
          try {
            await player.play();
            setReplyBlocked(false);
          } catch {
            setReplyBlocked(true);
            setNote(t("tapToHearReply"));
          }
        } else {
          setReplyBlocked(true);
        }
      }
    } catch {
      setNote(t("questionPlayFailed"));
    }
    if (!item.listened) {
      try {
        const response = await fetch("/api/v1/classes/questions/heard", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Class-Token": token },
          body: JSON.stringify({ cue_id: item.id }),
        });
        if (response.ok) {
          const body = (await response.json()) as { unread_count?: number };
          setQuestions((current) =>
            current.map((cue) => (cue.id === item.id ? { ...cue, listened: true } : cue)),
          );
          if (typeof body.unread_count === "number") {
            setUnreadCount(body.unread_count);
          } else {
            setUnreadCount((count) => Math.max(0, count - 1));
          }
        }
      } catch {
        // Replay still works if the listened flag did not save.
      }
    }
  }

  useEffect(() => {
    if (!token) {
      return undefined;
    }
    let stopped = false;
    let running = false;

    async function poll() {
      if (running || stopped) {
        return;
      }
      running = true;
      try {
        const response = await fetch("/api/v1/classes/cues", {
          headers: { "X-Class-Token": token },
        });
        if (!response.ok || stopped) {
          return;
        }
        const body = (await response.json()) as {
          cues?: Cue[];
          listener_count?: number;
          unread_count?: number;
        };
        if (typeof body.listener_count === "number") {
          setListeners(body.listener_count);
        }
        const next = body.cues ?? [];
        let fresh = 0;
        for (const item of next) {
          if (!knownQuestionIdsRef.current.has(item.id)) {
            knownQuestionIdsRef.current.add(item.id);
            if (!item.listened) {
              fresh += 1;
            }
          }
        }
        if (fresh > 0) {
          playQuestionDing({ muted: !questionSound });
          setQuestionAlert(true);
        }
        setQuestions(next);
        if (typeof body.unread_count === "number") {
          setUnreadCount(body.unread_count);
        } else {
          setUnreadCount(next.filter((item) => !item.listened).length);
        }
      } finally {
        running = false;
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      micRef.current?.stop();
      micRef.current = null;
      if (replyUrlRef.current) {
        URL.revokeObjectURL(replyUrlRef.current);
        replyUrlRef.current = "";
      }
    };
  }, [token, questionSound]);

  useEffect(() => {
    const player = replyRef.current;
    if (!replySrc || !player) {
      return;
    }
    const pending = player.play();
    if (pending) {
      void pending.catch(() => undefined);
    }
  }, [replySrc]);

  useEffect(() => {
    if (!micOn) {
      return undefined;
    }
    // While this device plays any clip, the microphone is held so playback is never sent as speech.
    function sync() {
      const playing = Array.from(document.querySelectorAll("audio")).some(
        (element) => !element.paused && !element.ended,
      );
      micRef.current?.setHold(playing);
    }
    const events = ["play", "playing", "pause", "ended", "emptied"];
    events.forEach((name) => document.addEventListener(name, sync, true));
    sync();
    return () => {
      events.forEach((name) => document.removeEventListener(name, sync, true));
    };
  }, [micOn]);

  if (!token) {
    return (
      <div className="teacher-boot" role="status">
        {booting ? <p className="teacher-boot-status">{t("startingClass")}</p> : null}
        {!booting && ended ? <p>{t("classEndedNote")}</p> : null}
        {!booting && note ? <p>{note}</p> : null}
        {!booting ? (
          <div className="teacher-boot-actions">
            <button type="button" className="button button-primary" onClick={() => void start()}>
              {t("startClass")}
            </button>
            <Link className="how-link" to="/">
              BabelBeam
            </Link>
          </div>
        ) : null}
        <p className="legal-disclaimer">{t("aiDisclaimer")}</p>
      </div>
    );
  }

  return (
    <div className="teacher-live">
      <header className="teacher-menubar">
        <p
          className={listeners > 0 ? "listener-pill" : "listener-pill listener-pill-empty"}
          role="status"
        >
          {listenerLabel(listeners, t("listenersNone"), t("listenersOne"), t("listenersMany"))}
        </p>
        <div className="teacher-menubar-corner">
          <button
            type="button"
            className={[
              "question-badge",
              unreadCount > 0 || questionAlert ? "has-unread" : "",
              questionAlert ? "question-badge-alert" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-label={t("questionInbox")}
            aria-expanded={inboxOpen}
            onClick={() => {
              setQuestionAlert(false);
              setInboxOpen((open) => !open);
            }}
          >
            <span className="question-badge-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
                <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
              </svg>
            </span>
            {unreadCount > 0 ? <span className="question-badge-count">{unreadCount}</span> : null}
          </button>
          {inboxOpen ? (
            <div className="question-inbox-popover" role="region" aria-label={t("questionInbox")}>
              <p className="caption-label">{t("questionInbox")}</p>
              <p className="teacher-inbox-hint">{t("questionInboxHint")}</p>
              {questions.length === 0 ? <p className="fine">{t("questionInboxEmpty")}</p> : null}
              <ul className="question-list">
                {questions.map((item) => (
                  <li key={item.id} className="question-list-item">
                    <button
                      type="button"
                      className={
                        item.listened || item.handling === "deferred" || item.handling === "dismissed"
                          ? "button button-line"
                          : "button button-line button-unread"
                      }
                      onClick={() => void openQuestion(item)}
                    >
                      <strong>{item.student_name || t("student")}</strong>
                      {!item.listened && item.handling !== "deferred" && item.handling !== "dismissed" ? (
                        <span className="new-tag">{t("questionNew")}</span>
                      ) : null}
                      {item.handling === "deferred" ? (
                        <span className="new-tag">{t("questionDeferred")}</span>
                      ) : null}
                      {item.handling === "dismissed" ? (
                        <span className="new-tag">{t("questionDismissed")}</span>
                      ) : null}
                      <span className="question-preview">{item.english_text}</span>
                    </button>
                    <div className="question-item-actions">
                      {item.handling === "deferred" || item.handling === "dismissed" ? (
                        <button
                          type="button"
                          className="button button-quiet"
                          onClick={() => void setQuestionHandling(item.id, "open")}
                        >
                          {t("questionReopen")}
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="button button-quiet"
                            onClick={() => void setQuestionHandling(item.id, "deferred")}
                          >
                            {t("questionDefer")}
                          </button>
                          <button
                            type="button"
                            className="button button-quiet"
                            onClick={() => void setQuestionHandling(item.id, "dismissed")}
                          >
                            {t("questionDismiss")}
                          </button>
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </header>

      {cueText || replySrc || replyBlocked || selectedQuestion ? (
        <div className="teacher-question-sheet private-cue">
          {selectedQuestion ? (
            <p className="caption-label">
              {t("questionFrom")} {selectedQuestion.student_name || t("student")}
            </p>
          ) : (
            <p className="caption-label">{t("teacherOnly")}</p>
          )}
          {cueText ? <p role="status">{cueText}</p> : null}
          <audio
            ref={replyRef}
            controls
            playsInline
            preload="auto"
            src={replySrc || undefined}
            aria-label={t("tapToHearReply")}
          />
          {replySrc || replyBlocked ? (
            <button type="button" className="button button-primary" onClick={hearReply}>
              {t("tapToHearReply")}
            </button>
          ) : null}
          {selectedQuestion ? (
            <div className="lesson-actions">
              <button
                type="button"
                className="button"
                onClick={() => void setQuestionHandling(selectedQuestion.id, "deferred")}
              >
                {t("questionDefer")}
              </button>
              <button
                type="button"
                className="button"
                onClick={() => void setQuestionHandling(selectedQuestion.id, "dismissed")}
              >
                {t("questionDismiss")}
              </button>
            </div>
          ) : null}
        </div>
      ) : (
        <audio ref={replyRef} playsInline preload="auto" hidden aria-hidden="true" />
      )}

      <section className="teacher-join" aria-label={t("classCodeLabel")}>
        {qrSrc ? (
          <div className="qr-card">
            <img src={qrSrc} width={200} height={200} alt={t("qrAlt")} />
          </div>
        ) : null}
        <p className="join-code" aria-label={code}>
          {formatJoinCode(code)}
        </p>
        <p className="teacher-script">{t("classLiveHint")}</p>
        <button type="button" className="button button-quiet" onClick={() => void copyLink()}>
          {t("copyLink")}
        </button>
      </section>

      <section className="teacher-controls">
        <div className="teacher-caption">
          <p className="caption-label">{t("studentsReceive")}</p>
          <p className="caption-live" role="status">
            {spanish || t("waitingForLine")}
          </p>
          {heard ? <p className="sent-line">{heard}</p> : null}
        </div>

        <button
          type="button"
          className={micOn ? "button button-primary button-mic is-live" : "button button-primary button-mic"}
          onClick={() => void toggleMic()}
        >
          {micOn ? t("micStop") : t("micStart")}
        </button>
        {micOn ? <p className="teacher-mic-note" role="status">{t("micOnTeacher")}</p> : null}
        {micNeedsResume ? (
          <p className="teacher-mic-note lesson-gap" role="status">
            {t("micNeedsResume")}
          </p>
        ) : null}

        <label className="teacher-toggle">
          <input
            type="checkbox"
            checked={keepAwake}
            onChange={(event) => setKeepAwake(event.target.checked)}
          />
          <span>{t("keepAwake")}</span>
        </label>
        <p className="teacher-wake-note fine" role="status">
          {wakeState === "active"
            ? isClassAppRuntime()
              ? t("keepAwakeClassApp")
              : t("keepAwakeActive")
            : wakeState === "unsupported"
              ? t("keepAwakeUnsupported")
              : wakeState === "blocked"
                ? t("keepAwakeBlocked")
                : keepAwake
                  ? t("keepAwakeInactive")
                  : t("keepAwakeOff")}
        </p>
        <p className="fine">{t("keepAwakeLimit")}</p>
        {!isClassAppRuntime() ? (
          <Link className="button button-primary" to="/install">
            {t("classAppCta")}
          </Link>
        ) : null}

        <label className="teacher-toggle">
          <input
            type="checkbox"
            checked={questionSound}
            onChange={(event) => {
              const enabled = event.target.checked;
              storeQuestionSoundPref(enabled);
              setQuestionSound(enabled);
            }}
          />
          <span>{t("questionSound")}</span>
        </label>

        <button
          type="button"
          className="button button-quiet"
          aria-expanded={typeOpen}
          onClick={() => setTypeOpen((open) => !open)}
        >
          {t("classLineLabel")}
        </button>
        {typeOpen ? (
          <form className="teacher-type-form" onSubmit={(event) => void send(event)}>
            <label className="visually-hidden" htmlFor="teacher-line">
              {t("classLineLabel")}
            </label>
            <textarea
              id="teacher-line"
              className="interpret-text"
              value={line}
              maxLength={400}
              onChange={(event) => setLine(event.target.value)}
            />
            <button className="button" type="submit" disabled={sending || line.trim().length === 0}>
              {sending ? t("interpretWorking") : t("sendLine")}
            </button>
          </form>
        ) : null}

        <audio
          ref={playerRef}
          controls
          playsInline
          className="teacher-class-audio"
          src={audioSrc || undefined}
          aria-label={t("studentsReceive")}
        />

        {confirmEnd ? (
          <div className="end-confirm">
            <p>{t("endConfirm")}</p>
            <button type="button" className="button button-danger" onClick={() => void end()}>
              {t("endNow")}
            </button>
            <button type="button" className="button" onClick={() => setConfirmEnd(false)}>
              {t("keepClass")}
            </button>
          </div>
        ) : (
          <button type="button" className="button button-danger button-end" onClick={() => setConfirmEnd(true)}>
            {t("endClass")}
          </button>
        )}
        {note ? <p role="status">{note}</p> : null}
      </section>
      <p className="legal-disclaimer">{t("aiDisclaimer")}</p>
    </div>
  );
}

export function ClassStudentPanel() {
  const { t, setLocale } = useI18n();
  const [params] = useSearchParams();
  const linkedCode = codeFromQuery(params.get("code"));
  const [code, setCode] = useState(linkedCode);
  const [token, setToken] = useState("");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("live");
  const [queue, setQueue] = useState<PlaybackQueue>(emptyQueue);
  const [tick, setTick] = useState(0);
  const [gone, setGone] = useState(false);
  const [micOn, setMicOn] = useState(false);
  const [hearHint, setHearHint] = useState(false);
  const [voice] = useState<StudentVoice>(readStoredVoice);
  const [gender, setGender] = useState<SpeakerGender>(readStoredGender);
  const [displayName, setDisplayName] = useState("");
  const [followLive, setFollowLive] = useState(true);
  const micRef = useRef<MicCapture | null>(null);
  const playerRef = useRef<HTMLAudioElement | null>(null);
  const captionsRef = useRef<HTMLDivElement | null>(null);
  const tokenRef = useRef("");
  const queueRef = useRef<PlaybackQueue>(queue);
  const clipUrlRef = useRef("");
  const playingIdRef = useRef("");
  const unlockedRef = useRef(false);
  tokenRef.current = token;
  queueRef.current = queue;

  function unlockPlayer() {
    const player = playerRef.current;
    if (!player || unlockedRef.current) {
      return;
    }
    unlockedRef.current = true;
    player.src = silentWavDataUrl();
    const attempt = player.play();
    if (attempt) {
      void attempt.catch(() => {
        unlockedRef.current = false;
      });
    }
  }

  function finishClip() {
    const id = playingIdRef.current;
    if (!id) {
      return;
    }
    playingIdRef.current = "";
    if (clipUrlRef.current) {
      URL.revokeObjectURL(clipUrlRef.current);
      clipUrlRef.current = "";
    }
    setQueue((current) => markPlayed(current, id));
  }

  function catchUp() {
    playerRef.current?.pause();
    finishClip();
    setQueue((current) => skipToLatest(current));
  }

  useEffect(() => {
    if (linkedCode.length === 6) {
      setLocale("es");
    }
  }, [linkedCode, setLocale]);

  function stopMic() {
    micRef.current?.stop();
    micRef.current = null;
    setMicOn(false);
  }

  async function uploadSpeech(blob: Blob, contentType: string) {
    const current = tokenRef.current;
    if (!current) {
      return;
    }
    setNote("");
    try {
      const form = new FormData();
      form.append("audio", blob, contentType.includes("mp4") ? "speech.mp4" : "speech.webm");
      form.append(
        "context",
        JSON.stringify(
          queueRef.current.lines.slice(-3).map((line) => ({ english: "", spanish: line.text })),
        ),
      );
      form.append("mode", "clean");
      const response = await fetch("/api/v1/classes/student-utterance", {
        method: "POST",
        headers: { "X-Class-Token": current },
        body: form,
      });
      if (response.status === 409) {
        setNote(t("studentBusy"));
        return;
      }
      if (!response.ok) {
        setNote(t("micFailed"));
        return;
      }
      const body = (await response.json()) as Spoken;
      if (body.status === "skipped") {
        setNote(t("fillerSkippedStudent"));
        return;
      }
      setNote(t("studentSent"));
    } catch {
      setNote(t("micFailed"));
    }
  }

  async function toggleMic() {
    if (micRef.current) {
      stopMic();
      return;
    }
    setNote("");
    try {
      micRef.current = await startMicCapture((blob, contentType) => {
        void uploadSpeech(blob, contentType);
      });
      setMicOn(true);
    } catch (error) {
      const unsupported = error instanceof Error && error.message === "unsupported";
      setNote(t(unsupported ? "micFailed" : "micDenied"));
      setMicOn(false);
    }
  }

  async function join(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    unlockPlayer();
    setNote("");
    const name = displayName.trim();
    if (!name) {
      setNote(t("nameRequired"));
      return;
    }
    const response = await fetch("/api/v1/classes/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        join_code: code.trim(),
        voice,
        display_name: name,
        gender,
      }),
    });
    if (response.status === 400) {
      setNote(t("nameRequired"));
      return;
    }
    if (!response.ok) {
      setNote(t("joinMissing"));
      return;
    }
    const body = (await response.json()) as { student_token?: string };
    if (!body.student_token) {
      setNote(t("joinMissing"));
      return;
    }
    sessionStorage.setItem(studentKey, body.student_token);
    storeVoice(voice);
    storeGender(gender);
    setToken(body.student_token);
    setNote("");
  }

  function chooseGender(next: SpeakerGender) {
    setGender(next);
    storeGender(next);
  }

  function genderPicker() {
    return (
      <div className="gender-icon-row" role="radiogroup" aria-label={t("genderPicker")}>
        {SPEAKER_GENDERS.map((option) => {
          const selected = gender === option;
          return (
            <button
              key={option}
              type="button"
              className={selected ? "gender-icon-button active" : "gender-icon-button"}
              role="radio"
              aria-checked={selected}
              aria-label={t(genderAriaKey(option))}
              onClick={() => chooseGender(option)}
            >
              <GenderPersonIcon gender={option} />
            </button>
          );
        })}
      </div>
    );
  }

  useEffect(() => {
    const player = playerRef.current;
    if (!player || !token) {
      return;
    }
    const step = nextStep(queue, Date.now());
    if (step.kind !== "play" || !step.line.clip) {
      return;
    }
    const id = step.line.id;
    const url = replyObjectUrl({
      audio_base64: step.line.clip.base64,
      audio_content_type: step.line.clip.contentType,
    });
    if (!url) {
      setQueue((current) => markPlayed(current, id));
      return;
    }
    if (clipUrlRef.current) {
      URL.revokeObjectURL(clipUrlRef.current);
    }
    clipUrlRef.current = url;
    playingIdRef.current = id;
    setQueue((current) => markPlaying(current, id));
    player.src = url;
    const attempt = player.play();
    if (attempt) {
      void attempt.then(() => setHearHint(false)).catch(() => setHearHint(true));
    }
  }, [queue, tick, token]);

  useEffect(() => {
    if (!token) {
      return undefined;
    }
    let stopped = false;
    let running = false;
    let first = true;
    let timer = 0;

    function halt() {
      stopped = true;
      window.clearInterval(timer);
    }

    async function poll() {
      if (running || stopped) {
        return;
      }
      running = true;
      try {
        const have = knownIds(queueRef.current).join(",");
        const query = first ? "v=2&first=1" : `v=2&have=${encodeURIComponent(have)}`;
        const response = await fetch(`/api/v1/classes/feed?${query}`, {
          headers: { "X-Class-Token": token },
        });
        if (stopped) {
          return;
        }
        if (response.status === 404) {
          setGone(true);
          halt();
          return;
        }
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as { status?: string; segments?: FeedSegment[] };
        if (body.status) {
          setStatus(body.status);
        }
        const history = first;
        first = false;
        const now = Date.now();
        setQueue((current) => expirePending(ingest(current, body.segments ?? [], now, history), now));
        if (body.status === "ended") {
          halt();
        }
      } catch {
        // A dropped request is retried on the next poll.
      } finally {
        running = false;
        setTick((value) => value + 1);
      }
    }

    void poll();
    timer = window.setInterval(() => void poll(), FEED_POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      micRef.current?.stop();
      micRef.current = null;
    };
  }, [token]);

  useEffect(() => {
    if (!token || !followLive) {
      return;
    }
    const scroller = captionsRef.current;
    if (!scroller) {
      return;
    }
    scroller.scrollTop = scroller.scrollHeight;
  }, [token, followLive, queue.lines.length, tick]);

  function onCaptionScroll() {
    const scroller = captionsRef.current;
    if (!scroller) {
      return;
    }
    const distance = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
    setFollowLive(distance < 80);
  }

  if (!token) {
    return (
      <div className="stack-form student-join">
        <h1>{t("joinTitle")}</h1>
        <form className="stack-form" onSubmit={(event) => void join(event)}>
          {linkedCode.length === 6 ? <p className="fine">{t("codeReady")}</p> : null}
          <label>
            {t("classCode")}
            <input
              name="code"
              inputMode="numeric"
              autoComplete="off"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </label>
          <label className="join-name-field">
            {t("displayName")}
            <div className="join-name-row">
              <input
                name="displayName"
                className="join-name-input"
                autoComplete="nickname"
                maxLength={40}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                required
              />
              {genderPicker()}
            </div>
          </label>
          <button className="button button-primary" type="submit">
            {t("joinSubmit")}
          </button>
        </form>
        {note ? <p role="status">{note}</p> : null}
        <p className="legal-disclaimer">{t("aiDisclaimer")}</p>
      </div>
    );
  }

  const needsHear =
    hearHint || queue.lines.some((item) => item.audio === "ready" || item.audio === "playing");

  return (
    <div className="student-live">
      <div className="student-live-bar">
        <p className="student-status-pill" role="status">
          {gone
            ? t("classGoneStudent")
            : status === "ended"
              ? t("classEndedNote")
              : t("studentListening")}
        </p>
        <details className="student-more">
          <summary>{t("studentMore")}</summary>
          <p className="legal-disclaimer">{t("aiDisclaimer")}</p>
          {!followLive ? (
            <button
              type="button"
              className="button button-quiet"
              onClick={() => {
                setFollowLive(true);
                const scroller = captionsRef.current;
                if (scroller) {
                  scroller.scrollTop = scroller.scrollHeight;
                }
              }}
            >
              {t("captionFollowLive")}
            </button>
          ) : null}
        </details>
      </div>

      <div
        className="student-captions"
        ref={captionsRef}
        onScroll={onCaptionScroll}
        aria-live="polite"
        aria-relevant="additions"
      >
        {queue.lines.length === 0 ? (
          <p className="student-caption-live">{t("joinWaiting")}</p>
        ) : null}
        {queue.lines.map((item, index) => (
          <p
            key={item.id}
            className={
              index === queue.lines.length - 1 ? "student-caption-live" : "student-caption-past"
            }
          >
            {item.text}
          </p>
        ))}
      </div>

      <div className="student-dock">
        {queue.behind ? (
          <button type="button" className="button" onClick={catchUp}>
            {t("audioCatchUp")}
          </button>
        ) : null}
        {needsHear ? (
          <button
            type="button"
            className="button button-primary"
            onClick={() => {
              unlockPlayer();
              setHearHint(false);
              const player = playerRef.current;
              if (player) {
                void player.play().catch(() => setHearHint(true));
              }
              setTick((value) => value + 1);
            }}
          >
            {t("tapToHear")}
          </button>
        ) : null}
        <button
          type="button"
          className={micOn ? "button button-primary student-ask is-live" : "button button-primary student-ask"}
          onClick={() => void toggleMic()}
        >
          {micOn ? t("studentStop") : t("studentSpeak")}
        </button>
        {micOn ? <p role="status">{t("micOn")}</p> : null}
        {note ? <p role="status">{note}</p> : null}
      </div>

      <audio
        ref={playerRef}
        controls
        playsInline
        className="student-audio"
        aria-label={t("studentsReceive")}
        onEnded={finishClip}
        onError={finishClip}
      />
    </div>
  );
}
