# Multi-Language Architecture v1 (Multi-Native Legal AI)

**Date:** 16 June 2026  
**Branch:** `release/lawapp-clean-snapshot`  
**Mode:** Multi-native (NOT translation)

## Principle

| Layer | Behaviour |
|-------|-----------|
| Rules DB | Language-neutral SQL (`rule_key`, thresholds) |
| RAG / GraphRAG | Same corpus, same retrieval, language-neutral |
| Brain / Mother | Single governed pipeline → **assessment_core** |
| Language engine | Independent **native phrasing** per locale (EN, AR) |
| Frontend | UI strings from bundles; legal text from API **rendered** |

Third-party translation APIs are forbidden for legal assessment output.

## Folder tree (Python + Next + TS)

```
backend/
  core/
    mother_algorithm/
      language_router.py      # detectLanguage + route (mirror of TS)
      orchestrator.py         # attach_language_layer helper
    control_plane/
      mother_controller.py    # language_render stage after govern
  language_engine/
    base_interface.py
    router.py                 # render_assessment(), validate_locale_consistency()
    integration.py
    shared/
      types.py                # LanguageNeutralAssessment, RenderedAssessment
      detector.py             # resolve_locale, Arabic script fallback
      legal_types.py
      reasoning_schema.py
      rule_mapper.py
    en/
      phrasing.py, prompts.py, formatter.py, engine.py, legal_templates.py
    ar/
      phrasing.py             # formal Arabic native tone
      prompts.py              # SYSTEM + unfairDismissal + explanationStyle (Arabic)
      formatter.py, engine.py, legal_templates.py
  api/
    i18n_routes.py            # /api/i18n/locale, /render, /detect, /prompts/{locale}
    main.py                   # POST /assess + language field

control-plane/src/core/mother_algorithm/
  language_router.ts          # detectLanguage + assessProxyHeaders

shared/
  i18n_contracts.ts
  types/i18n.ts
  constants/locales.ts

client/next/
  app/
    layout.tsx                # LanguageProvider + RTLLayout
    page.tsx                  # CaseForm demo
    language/
      LanguageProvider.tsx, useLanguage.ts, rtl_handler.ts
  components/
    CaseForm.tsx, ResultView.tsx, LanguageSwitcher.tsx, RTLLayout.tsx
  styles/
    rtl.css, themes.ts

client/public/js/i18n/
  language-service.js
  rtl-engine.js
  locales/en.json, ar.json

tests/
  test_language_router.py
  test_arabic_engine_native_keys.py
  test_mother_language_integration.py

db/migrations/
  085_user_preferences_locale.sql
```

## API contract

**POST /assess** accepts `language: "en"|"ar"` and `Accept-Language`.

Response includes:

```json
{
  "assessment_core": { "claim_type": "unfair_dismissal", "rule_keys": ["..."] },
  "rendered": {
    "locale": "ar",
    "dir": "rtl",
    "headline": "تقييم الفصل غير العادل",
    "reasoning_summary": "...",
    "formatted": { "الملخص": "...", "نقاط_الضعف": [] }
  },
  "locale": "ar",
  "dir": "rtl"
}
```

## Arabic prompts path

`backend/language_engine/ar/prompts.py` — native Arabic `SYSTEM_PROMPT`, `UNFAIR_DISMISSAL_PROMPT`, `EXPLANATION_STYLE`.

## Verification

```bash
pytest tests/test_language_router.py tests/test_arabic_engine_native_keys.py tests/test_mother_language_integration.py -q
docker compose up -d backend
curl -s -H "Accept-Language: ar" -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"query":"Do I have a claim?","language":"ar","facts":{"edt":"2025-10-01","service_start_date":"2019-01-01"},"use_model":false}'
cd client/next && npm run build
```
