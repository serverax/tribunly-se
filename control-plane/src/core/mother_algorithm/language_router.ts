/**
 * NestJS mirror of Python LanguageRouter: locale detection + FastAPI proxy header.
 */

import type { SupportedLocale } from '../i18n_contracts';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from '../i18n_contracts';

const ARABIC_SCRIPT = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/;

export function normalizeLocale(value?: string | null): SupportedLocale | null {
  if (!value) return null;
  const loc = value.trim().toLowerCase().split(',')[0].split('-')[0].split('_')[0];
  return (SUPPORTED_LOCALES as readonly string[]).includes(loc) ? (loc as SupportedLocale) : null;
}

export function detectArabicScript(text?: string | null): boolean {
  return Boolean(text && ARABIC_SCRIPT.test(text));
}

export function detectLanguage(options: {
  preferredLanguage?: string | null;
  acceptLanguage?: string | null;
  text?: string | null;
}): SupportedLocale {
  const pref = normalizeLocale(options.preferredLanguage);
  if (pref) return pref;

  if (options.acceptLanguage) {
    const first = options.acceptLanguage.split(',')[0]?.trim();
    const fromHeader = normalizeLocale(first);
    if (fromHeader) return fromHeader;
  }

  if (detectArabicScript(options.text)) return 'ar';
  return DEFAULT_LOCALE;
}

/** Headers to forward when proxying Python /assess with locale. */
export function assessProxyHeaders(locale: SupportedLocale): Record<string, string> {
  return {
    'Accept-Language': locale === 'ar' ? 'ar' : 'en-GB',
    'X-LawApp-Locale': locale,
  };
}
