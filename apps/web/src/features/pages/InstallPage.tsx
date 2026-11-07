import { Link } from "react-router-dom";
import { useI18n } from "../../app/i18n";
import { isClassAppRuntime } from "../class/wakeLock";

const ANDROID_APK = "/downloads/babelbeam-class.apk";
const ANDROID_RELEASE =
  "https://github.com/aurelius-in/babelbeam/releases/latest/download/babelbeam-class.apk";

/** Public TestFlight invite URL once Apple review/build is ready. Empty until set. */
const IOS_TESTFLIGHT_URL = "";

export function InstallPage() {
  const { t } = useI18n();
  const inClassApp = isClassAppRuntime();
  const hasTestFlight = IOS_TESTFLIGHT_URL.length > 0;

  return (
    <main className="sheet how-sheet install-sheet">
      <p className="kicker">{t("installKicker")}</p>
      <h1>{t("installClassAppTitle")}</h1>
      <p className="lede">{t("installClassAppBody")}</p>

      {inClassApp ? (
        <p className="promise" role="status">
          {t("installAlreadyInApp")}
        </p>
      ) : (
        <>
          <section className="install-class-app">
            <h2>{t("installAndroidTitle")}</h2>
            <p>{t("installAndroidBody")}</p>
            <ol className="steps how-steps">
              <li>
                <span>01</span>
                <h3>{t("installAndroidStep1")}</h3>
                <p>{t("installAndroidStep1Body")}</p>
              </li>
              <li>
                <span>02</span>
                <h3>{t("installAndroidStep2")}</h3>
                <p>{t("installAndroidStep2Body")}</p>
              </li>
              <li>
                <span>03</span>
                <h3>{t("installAndroidStep3")}</h3>
                <p>{t("installAndroidStep3Body")}</p>
              </li>
            </ol>
            <p className="how-actions install-download-row">
              <a className="button button-primary" href={ANDROID_APK} download="babelbeam-class.apk">
                {t("installDownloadAndroid")}
              </a>
              <a className="button" href={ANDROID_RELEASE}>
                {t("installDownloadAndroidAlt")}
              </a>
            </p>
            <p className="fine">{t("installAndroidSideload")}</p>
          </section>

          <section className="install-ios">
            <h2>{t("installIosAppTitle")}</h2>
            <p>{hasTestFlight ? t("installIosAppBodyReady") : t("installIosAppBody")}</p>
            {hasTestFlight ? (
              <>
                <ol className="steps how-steps">
                  <li>
                    <span>01</span>
                    <h3>{t("installIosTfStep1")}</h3>
                    <p>{t("installIosTfStep1Body")}</p>
                  </li>
                  <li>
                    <span>02</span>
                    <h3>{t("installIosTfStep2")}</h3>
                    <p>{t("installIosTfStep2Body")}</p>
                  </li>
                  <li>
                    <span>03</span>
                    <h3>{t("installIosTfStep3")}</h3>
                    <p>{t("installIosTfStep3Body")}</p>
                  </li>
                </ol>
                <p className="how-actions install-download-row">
                  <a className="button button-primary" href={IOS_TESTFLIGHT_URL}>
                    {t("installDownloadIos")}
                  </a>
                </p>
              </>
            ) : (
              <>
                <p className="fine">{t("installIosPending")}</p>
                <ol className="steps how-steps">
                  <li>
                    <span>01</span>
                    <h3>{t("installIosTitle")}</h3>
                    <p>{t("installIos1")}</p>
                  </li>
                  <li>
                    <span>02</span>
                    <h3>{t("installIos2")}</h3>
                    <p>{t("installIos3")}</p>
                  </li>
                  <li>
                    <span>03</span>
                    <h3>{t("installIos4")}</h3>
                    <p>{t("installAfter")}</p>
                  </li>
                </ol>
              </>
            )}
          </section>
        </>
      )}

      <section>
        <h2>{t("installLimitsTitle")}</h2>
        <p>{t("installLimitsBody")}</p>
      </section>

      <p className="how-actions">
        <Link className="start-class-cta start-class-cta-compact" to="/app">
          <span className="start-class-cta-label">{t("startClass")}</span>
          <span className="start-class-cta-beam" aria-hidden="true" />
        </Link>
      </p>
    </main>
  );
}
