"""I18n locale API tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.i18n_routes import router as i18n_router
from backend.core.control_plane.mother_controller import MotherController, MotherInput

i18n_app = FastAPI()
i18n_app.include_router(i18n_router)
client = TestClient(i18n_app)


def test_get_locale_default_en():
    r = client.get("/api/i18n/locale")
    assert r.status_code == 200
    body = r.json()
    assert body["locale"] in ("en", "ar")
    assert body["dir"] in ("ltr", "rtl")
    assert "en" in body["supported"]


def test_set_locale_cookie_ar():
    r = client.post("/api/i18n/locale", json={"locale": "ar"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["locale"] == "ar"
    assert body["dir"] == "rtl"
    assert "lawapp_locale" in r.cookies
    assert r.cookies["lawapp_locale"] == "ar"


def test_mother_assess_ar_locale_fields():
    out = MotherController().process(
        MotherInput(
            query="What is the time limit for unfair dismissal?",
            facts={},
            jurisdiction="EW",
            use_model=False,
            locale="ar",
        )
    )
    result = out.to_dict()
    assert result.get("locale") == "ar"
    assert result.get("dir") == "rtl"
    assert "assessment_core" in result


def test_mother_assess_en_has_assessment_core():
    out = MotherController().process(
        MotherInput(
            query="What is the time limit for unfair dismissal?",
            facts={},
            jurisdiction="EW",
            use_model=False,
            locale="en",
        )
    )
    result = out.to_dict()
    assert result.get("locale") == "en"
    assert "assessment_core" in result
