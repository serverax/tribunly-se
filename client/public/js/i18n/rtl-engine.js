/**
 * RTL layout engine for Arabic Case OS shell.
 */
(function () {
  "use strict";

  var ARABIC_FONT =
    '"Noto Naskh Arabic", "Segoe UI", Tahoma, Arial, sans-serif';

  function apply(locale) {
    var isRtl = locale === "ar";
    var html = document.documentElement;
    html.setAttribute("lang", locale);
    html.setAttribute("dir", isRtl ? "rtl" : "ltr");
    document.body.classList.toggle("is-rtl", isRtl);
    if (isRtl) {
      document.body.style.fontFamily = ARABIC_FONT;
    } else {
      document.body.style.fontFamily = "";
    }
  }

  window.LAWAPP_RTL = { apply: apply };
})();
