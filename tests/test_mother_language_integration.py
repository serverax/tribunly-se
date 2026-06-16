"""Mother controller language integration."""

from __future__ import annotations

from backend.core.control_plane.mother_controller import MotherController, MotherInput


def test_mother_applies_arabic_language_layer_on_factual_lane():
    ctrl = MotherController()
    out = ctrl.process(
        MotherInput(
            query="What is the time limit for unfair dismissal?",
            facts={"language": "ar"},
            jurisdiction="EW",
            use_model=False,
            locale="ar",
        )
    )
    body = out.to_dict()
    assert body.get("locale") == "ar"
    assert body.get("dir") == "rtl"
    assert "assessment_core" in body
    assert "rendered" in body
    lang_stages = [s for s in body.get("control_plane_stages", []) if s.get("stage") == "language_render"]
    assert lang_stages
    assert lang_stages[0].get("locale") == "ar"


def test_mother_arabic_script_fallback():
    ctrl = MotherController()
    out = ctrl.process(
        MotherInput(
            query="ما هو موعد التقادم للفصل التعسفي؟",
            facts={},
            jurisdiction="EW",
            use_model=False,
        )
    )
    body = out.to_dict()
    assert body.get("locale") == "ar"
    assert body.get("dir") == "rtl"
