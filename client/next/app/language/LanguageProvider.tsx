"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { applyRtlDocument, type SupportedLocale } from "./rtl_handler";

const STORAGE_KEY = "lawapp_locale";
const SUPPORTED: SupportedLocale[] = ["en", "ar"];

type LanguageContextValue = {
  locale: SupportedLocale;
  direction: "ltr" | "rtl";
  setLocale: (locale: SupportedLocale) => Promise<void>;
  t: (key: string, fallback?: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

async function loadStrings(locale: SupportedLocale): Promise<Record<string, string>> {
  const res = await fetch(`/js/i18n/locales/${locale}.json`);
  if (!res.ok) return {};
  return res.json();
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<SupportedLocale>("en");
  const [strings, setStrings] = useState<Record<string, string>>({});

  const direction = locale === "ar" ? "rtl" : "ltr";

  const applyLocale = useCallback(async (next: SupportedLocale) => {
    const normalized = SUPPORTED.includes(next) ? next : "en";
    setLocaleState(normalized);
    localStorage.setItem(STORAGE_KEY, normalized);
    document.cookie = `lawapp_locale=${normalized};path=/;max-age=31536000;samesite=lax`;
    applyRtlDocument(normalized);
    const bundle = await loadStrings(normalized);
    setStrings(bundle);
    try {
      await fetch("/api/i18n/locale", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: normalized }),
      });
    } catch {
      /* cookie is sufficient */
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as SupportedLocale | null;
    const initial = stored && SUPPORTED.includes(stored) ? stored : "en";
    void applyLocale(initial);
  }, [applyLocale]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      locale,
      direction,
      setLocale: applyLocale,
      t: (key, fallback) => strings[key] ?? fallback ?? key,
    }),
    [locale, direction, applyLocale, strings],
  );

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
