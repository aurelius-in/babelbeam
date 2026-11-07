import { Link, Navigate } from "react-router-dom";
import { useI18n } from "../../app/i18n";
import { ClassStudentPanel, ClassTeacherPanel } from "../class/ClassPanels";

export function PricingPage() {
  return <Navigate to="/" replace />;
}

export { InstallPage } from "./InstallPage";

export function HowToPage() {
  const { t } = useI18n();
  return (
    <main className="sheet how-sheet">
      <p className="kicker">{t("howKicker")}</p>
      <h1>{t("teachOnce")}</h1>
      <p className="lede">{t("teachOnceBody")}</p>
      <ol className="steps how-steps">
        <li>
          <span>01</span>
          <h3>{t("stepSpeak")}</h3>
          <p>{t("stepSpeakBody")}</p>
          <p>{t("stepSpeakWake")}</p>
        </li>
        <li>
          <span>02</span>
          <h3>{t("stepInterpret")}</h3>
          <p>{t("stepInterpretBody")}</p>
        </li>
        <li>
          <span>03</span>
          <h3>{t("stepFollow")}</h3>
          <p>{t("stepFollowBody")}</p>
          <p>{t("stepFollowLesson")}</p>
        </li>
      </ol>

      <section className="teach-guide" aria-labelledby="teach-guide-heading">
        <h2 id="teach-guide-heading">{t("teachGuideTitle")}</h2>
        <p className="lede">{t("teachGuideBody")}</p>
        <ol className="steps how-steps">
          <li>
            <span>01</span>
            <h3>{t("teachGuide1")}</h3>
            <p>{t("teachGuide1Body")}</p>
          </li>
          <li>
            <span>02</span>
            <h3>{t("teachGuide2")}</h3>
            <p>{t("teachGuide2Body")}</p>
          </li>
          <li>
            <span>03</span>
            <h3>{t("teachGuide3")}</h3>
            <p>{t("teachGuide3Body")}</p>
          </li>
          <li>
            <span>04</span>
            <h3>{t("teachGuide4")}</h3>
            <p>{t("teachGuide4Body")}</p>
          </li>
        </ol>
      </section>

      <p className="promise">{t("promise")}</p>
      <p className="legal-disclaimer">{t("constraints")}</p>
      <p className="how-actions">
        <Link className="button button-primary" to="/install">
          {t("classAppCta")}
        </Link>
        <Link className="start-class-cta start-class-cta-compact" to="/app">
          <span className="start-class-cta-label">{t("startClass")}</span>
          <span className="start-class-cta-beam" aria-hidden="true" />
        </Link>
      </p>
    </main>
  );
}

export function JoinPage() {
  return (
    <main className="sheet class-sheet student-sheet">
      <ClassStudentPanel />
    </main>
  );
}

export function LoginPage() {
  return <Navigate to="/app" replace />;
}

export function HelpPage() {
  return <Navigate to="/how" replace />;
}

export function DashboardPage() {
  return (
    <main className="sheet class-sheet teacher-sheet">
      <ClassTeacherPanel />
    </main>
  );
}
