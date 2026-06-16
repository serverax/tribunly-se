export type SupportedLocale = "en" | "ar";

export function applyRtlDocument(locale: SupportedLocale): void {
  const dir = locale === "ar" ? "rtl" : "ltr";
  const lang = locale === "ar" ? "ar" : "en-GB";
  document.documentElement.dir = dir;
  document.documentElement.lang = lang;
  document.body.classList.toggle("rtl", dir === "rtl");
}

export function assessHeaders(locale: SupportedLocale): HeadersInit {
  return {
    "Content-Type": "application/json",
    "Accept-Language": locale === "ar" ? "ar" : "en-GB",
  };
}
