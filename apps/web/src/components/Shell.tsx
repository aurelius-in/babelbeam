import { NavLink } from "react-router-dom";
import { useI18n, type Locale } from "../app/i18n";
import { Logo } from "./Logo/Logo";

export function SiteHeader() {
  const { t, locale, setLocale } = useI18n();

  return (
    <header className="site-header site-header-minimal">
      <NavLink to="/" className="brand-lockup" aria-label="BabelBeam">
        <Logo variant="light" size={140} decorative />
      </NavLink>
      <div className="lang-switch" role="group" aria-label={t("language")}>
        {(["en", "es"] as Locale[]).map((code) => (
          <button
            key={code}
            type="button"
            className={locale === code ? "lang-button active" : "lang-button"}
            aria-pressed={locale === code}
            onClick={() => setLocale(code)}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>
    </header>
  );
}
