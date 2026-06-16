/** Shared multi-native language contracts (not translation). */

export type SupportedLocale = "en" | "ar";

export const SUPPORTED_LOCALES: SupportedLocale[] = ["en", "ar"];
export const DEFAULT_LOCALE: SupportedLocale = "en";

export type TextDirection = "ltr" | "rtl";

export interface LanguageNeutralAssessmentCore {
  schema_version?: string;
  language_neutral?: boolean;
  status: string;
  claim_type: string;
  jurisdiction: string;
  strength?: string;
  has_viable_claim?: boolean | string | null;
  reasoning_summary?: string;
  key_weaknesses?: string[];
  employer_arguments?: string[];
  recommended_next_step?: string;
  citations?: Array<{ cite?: string; url?: string; rule_key?: string }>;
  rule_keys?: string[];
  deadline?: Record<string, unknown> | null;
  trace_id?: string;
}

export interface RenderedAssessmentPayload {
  locale: SupportedLocale;
  dir: TextDirection;
  direction?: TextDirection;
  headline: string;
  reasoning_summary: string;
  key_weaknesses: string[];
  employer_arguments: string[];
  recommended_next_step: string;
  strength_label: string;
  formatted?: Record<string, unknown>;
}

export interface AssessResponseWithLanguage {
  assessment_core: LanguageNeutralAssessmentCore;
  rendered: RenderedAssessmentPayload;
  locale: SupportedLocale;
  dir: TextDirection;
  direction?: TextDirection;
  [key: string]: unknown;
}

export interface LocaleInfo {
  code: SupportedLocale;
  label: string;
  direction: TextDirection;
  native: boolean;
}

export function isRtl(locale: SupportedLocale): boolean {
  return locale === "ar";
}

export function localeDirection(locale: SupportedLocale): TextDirection {
  return isRtl(locale) ? "rtl" : "ltr";
}
