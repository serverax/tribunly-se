"use client";

import { useLanguage } from "@/app/language/LanguageProvider";
import { Button } from "@/components/ui/button";

export function LanguageSwitcher() {
  const { locale, setLocale } = useLanguage();

  return (
    <div className="flex items-center gap-1 rounded-md border border-border p-0.5" role="group" aria-label="Language">
      <Button
        type="button"
        size="sm"
        variant={locale === "en" ? "default" : "ghost"}
        onClick={() => void setLocale("en")}
        aria-pressed={locale === "en"}
      >
        EN
      </Button>
      <Button
        type="button"
        size="sm"
        variant={locale === "ar" ? "default" : "ghost"}
        onClick={() => void setLocale("ar")}
        aria-pressed={locale === "ar"}
      >
        العربية
      </Button>
    </div>
  );
}
