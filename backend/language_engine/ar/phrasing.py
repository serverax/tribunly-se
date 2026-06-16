"""Formal Arabic legal phrasing (native Arabic, not EN translation)."""

from __future__ import annotations

from backend.language_engine.shared.types import LanguageNeutralAssessment, RenderedAssessment

_STRENGTH_LABELS = {
    "strong": "مؤشرات قوة على وجود مطالبة",
    "moderate": "قوة متوسطة للمطالبة",
    "weak": "مؤشرات ضعف في المطالبة",
    "uncertain": "القوة غير محددة بعد",
}

_CLAIM_HEADLINES = {
    "unfair_dismissal": "تقييم الفصل غير العادل",
    "constructive_dismissal": "تقييم الاستقالة الإجبارية",
    "discrimination": "تقييم التمييز في العمل",
    "unpaid_wages": "تقييم الأجور غير المدفوعة",
    "whistleblowing": "تقييم الإبلاغ عن المخالفات",
    "redundancy": "تقييم التسريح لأسباب اقتصادية",
}


def render_ar(assessment: LanguageNeutralAssessment) -> RenderedAssessment:
    strength = assessment.strength or "uncertain"
    summary = assessment.reasoning_summary
    if not summary and assessment.status == "ok":
        summary = (
            "استناداً إلى قاعدة القواعد القانونية والمصادر المسترجعة، "
            f"تم تقييم مسألة { _claim_ar(assessment.claim_type) } "
            f"في اختصاص { _jurisdiction_ar(assessment.jurisdiction) }."
        )
    elif not summary:
        summary = "يلزم توفير المزيد من الوقائع قبل إصدار تقييم قائم على مصادر موثقة."

    weaknesses = [_weakness_ar(w) for w in assessment.key_weaknesses]
    if not weaknesses and assessment.status != "ok":
        weaknesses = ["لا توجد أدلة كافية قائمة على مصادر موثقة لاستخلاص نتيجة واثقة."]

    employer_args = [_employer_arg_ar(a) for a in assessment.employer_arguments]
    next_step = assessment.recommended_next_step or (
        "راجع المصادر المذكورة وتحقق من التواريخ الجوهرية قبل تقديم مطالبة أمام المحكمة العمالية."
    )
    if assessment.recommended_next_step and _looks_english(assessment.recommended_next_step):
        next_step = (
            "راجع المصادر المذكورة وتحقق من التواريخ الجوهرية قبل تقديم مطالبة أمام المحكمة العمالية."
        )

    headline = _CLAIM_HEADLINES.get(
        assessment.claim_type,
        f"تقييم { _claim_ar(assessment.claim_type) }",
    )

    return RenderedAssessment(
        locale="ar",
        dir="rtl",
        reasoning_summary=summary if not _looks_english(summary) else _fallback_summary_ar(assessment),
        key_weaknesses=weaknesses,
        employer_arguments=employer_args,
        recommended_next_step=next_step,
        strength_label=_STRENGTH_LABELS.get(strength, _STRENGTH_LABELS["uncertain"]),
        headline=headline,
    )


def _claim_ar(claim_type: str) -> str:
    return _CLAIM_HEADLINES.get(claim_type, claim_type.replace("_", " "))


def _jurisdiction_ar(code: str) -> str:
    return {"EW": "إنجلترا وويلز", "SC": "اسكتلندا", "NI": "أيرلندا الشمالية"}.get(
        code.upper(), code
    )


def _weakness_ar(text: str) -> str:
    if _looks_english(text):
        return "نقطة ضعف محتملة تتطلب مزيداً من الأدلة."
    return text


def _employer_arg_ar(text: str) -> str:
    if _looks_english(text):
        return "حجة محتملة من جانب صاحب العمل."
    return text


def _looks_english(text: str) -> bool:
    if not text:
        return False
    ascii_letters = sum(1 for c in text if "a" <= c.lower() <= "z")
    return ascii_letters > len(text) * 0.4


def _fallback_summary_ar(assessment: LanguageNeutralAssessment) -> str:
    return (
        "استناداً إلى القواعد القانونية المحددة والمصادر المسترجعة من قاعدة البيانات، "
        f"تم إعداد تقييم أولي لمسألة { _claim_ar(assessment.claim_type) } "
        f"بمستوى قوة: { _STRENGTH_LABELS.get(assessment.strength, _STRENGTH_LABELS['uncertain']) }."
    )
