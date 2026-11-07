import { Link } from "react-router-dom";
import { useI18n } from "../../app/i18n";
import { Logo } from "../../components/Logo/Logo";

export function LandingPage() {
  const { t } = useI18n();

  return (
    <main className="home-main">
      <section className="hero hero-simple" aria-label="BabelBeam">
        <Logo variant="light" size={340} className="hero-brand" />
        <Link className="start-class-cta" to="/app">
          <span className="start-class-cta-label">{t("startClass")}</span>
          <span className="start-class-cta-beam" aria-hidden="true" />
        </Link>
        <Link className="how-link" to="/how">
          {t("navHow")}
        </Link>
      </section>
    </main>
  );
}
