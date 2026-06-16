"""Map neutral rule / claim codes to locale-specific labels (not translation)."""

from __future__ import annotations

from typing import Any

EN_CLAIM_LABELS: dict[str, str] = {
    "unfair_dismissal": "Unfair dismissal",
    "unpaid_wages": "Unpaid wages",
    "discrimination": "Discrimination",
    "redundancy": "Redundancy",
    "wrongful_dismissal": "Wrongful dismissal",
    "constructive_dismissal": "Constructive dismissal",
    "out_of_scope": "Out of scope",
}

AR_CLAIM_LABELS: dict[str, str] = {
    "unfair_dismissal": "الفصل التعسفي",
    "unpaid_wages": "أجور غير مدفوعة",
    "discrimination": "تمييز",
    "redundancy": "تسريح لأسباب اقتصادية",
    "wrongful_dismissal": "إنهاء عقد مخالف للقانون",
    "constructive_dismissal": "الاستقالة القسرية",
    "out_of_scope": "خارج نطاق النظام",
}

EN_STRENGTH = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "uncertain": "Uncertain",
}

AR_STRENGTH = {
    "low": "ضعيف",
    "medium": "متوسط",
    "high": "قوي",
    "uncertain": "غير محدد",
}

EN_VIABILITY = {
    "yes": "Viable claim indicated",
    "no": "No viable claim indicated",
    "uncertain": "Viability uncertain",
}

AR_VIABILITY = {
    "yes": "توجد مؤشرات على وجود مطالبة قابلة للتقديم",
    "no": "لا توجد مؤشرات على مطالبة قابلة للتقديم",
    "uncertain": "قابلية المطالبة غير محددة",
}

EN_NEXT_STEP = {
    "free_diagnosis_only": "Continue with free diagnosis",
    "prepare_documents": "Prepare tribunal documents",
    "seek_solicitor": "Seek a qualified solicitor",
}

AR_NEXT_STEP = {
    "free_diagnosis_only": "متابعة التقييم المبدئي المجاني",
    "prepare_documents": "التحضير لوثائق المحكمة",
    "seek_solicitor": "استشارة محامٍ مؤهل",
}


def claim_label(claim_type: str, locale: str) -> str:
    table = AR_CLAIM_LABELS if locale == "ar" else EN_CLAIM_LABELS
    return table.get(claim_type or "", claim_type or "Unknown")


def strength_label(code: str, locale: str) -> str:
    table = AR_STRENGTH if locale == "ar" else EN_STRENGTH
    return table.get(code or "uncertain", code or "uncertain")


def viability_label(code: str | None, locale: str) -> str:
    table = AR_VIABILITY if locale == "ar" else EN_VIABILITY
    return table.get(code or "uncertain", table["uncertain"])


def next_step_label(code: str | None, locale: str) -> str:
    table = AR_NEXT_STEP if locale == "ar" else EN_NEXT_STEP
    return table.get(code or "free_diagnosis_only", table["free_diagnosis_only"])


def format_citations(citations: list[Any], locale: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for c in citations or []:
        if not isinstance(c, dict):
            continue
        cite = str(c.get("cite") or c.get("authority") or "")
        url = str(c.get("url") or "")
        if locale == "ar":
            out.append({"المرجع": cite, "الرابط": url})
        else:
            out.append({"cite": cite, "url": url})
    return out
