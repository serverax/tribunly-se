"""Arabic native legal phrasing templates (formal legal tone, RTL)."""

from __future__ import annotations

DISCLAIMER = (
    "هذه معلومات وتقييم منظم فقط. لا تُعد LawApp مكتب محاماة ولا تقدم مشورة قانونية."
)

HEADLINE_OK = "تقييم مطالبة العمل"
HEADLINE_BLOCKED = "تعذر إكمال التقييم"
HEADLINE_GROUNDING = "مصادر موثقة غير كافية"

WEAKNESS_TEMPLATES = {
    "missing_edt": "تاريخ انتهاء الخدمة الفعلي غير مذكور.",
    "short_service": "قد تكون مدة الخدمة أقل من فترة التأهل.",
    "procedure_gap": "قد لا يكون صاحب العمل اتبع إجراءات تأديبية كافية.",
    "evidence_thin": "الأدلة الداعمة تبدو محدودة.",
    "deadline_risk": "موعد التقادم يتطلب اهتماماً عاجلاً.",
}

EMPLOYER_ARGUMENT_TEMPLATES = {
    "conduct": "قد يستند صاحب العمل إلى السلوك والإجراءات التأديبية.",
    "capability": "قد يجادل صاحب العمل بوجود قصور في الأداء موثق.",
    "redundancy": "قد يجادل صاحب العمل بوجود ظروف تسريح حقيقية.",
    "some_other_substantial_reason": "قد يستند صاحب العمل إلى سبب جوهري آخر.",
}
