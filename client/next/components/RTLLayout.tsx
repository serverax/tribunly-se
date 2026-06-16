"use client";

import type { ReactNode } from "react";
import { useLanguage } from "@/app/language/LanguageProvider";

export function RTLLayout({ children }: { children: ReactNode }) {
  const { direction } = useLanguage();
  return (
    <div dir={direction} className={direction === "rtl" ? "font-arabic" : undefined}>
      {children}
    </div>
  );
}
