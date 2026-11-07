import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { codeFromQuery } from "../lib/joinCode";
import en from "../locales/en.json";
import es from "../locales/es.json";

const catalogs = { en, es } as const;

export type Locale = keyof typeof catalogs;
export type MessageKey = keyof typeof en;

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function initialLocale(): Locale {
  if (typeof window === "undefined") {
    return "en";
  }
  const params = new URLSearchParams(window.location.search);
  if (window.location.pathname === "/join" && codeFromQuery(params.get("code")).length === 6) {
    return "es";
  }
  return "en";
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(initialLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key) => catalogs[locale][key],
    }),
    [locale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useI18n(): LocaleContextValue {
  const value = useContext(LocaleContext);
  if (!value) {
    throw new Error("useI18n must be used within LocaleProvider");
  }
  return value;
}
