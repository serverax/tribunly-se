/**
 * LawApp language service (UI strings + locale persistence).
 * Legal assessment text comes from the API (server-rendered), not client translation.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "lawapp_locale";
  var COOKIE_NAME = "lawapp_locale";
  var DEFAULT_LOCALE = "en";
  var SUPPORTED = ["en", "ar"];

  var _strings = {};
  var _locale = DEFAULT_LOCALE;

  function normalize(code) {
    if (!code) return null;
    var loc = String(code).toLowerCase().split(",")[0].split("-")[0];
    return SUPPORTED.indexOf(loc) !== -1 ? loc : null;
  }

  function readCookie() {
    var match = document.cookie.match(new RegExp("(?:^|; )" + COOKIE_NAME + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function writeCookie(loc) {
    document.cookie = COOKIE_NAME + "=" + encodeURIComponent(loc) + ";path=/;max-age=31536000;samesite=lax";
  }

  function detectBrowserLocale() {
    var langs = navigator.languages || [navigator.language || "en"];
    for (var i = 0; i < langs.length; i++) {
      var n = normalize(langs[i]);
      if (n) return n;
    }
    return DEFAULT_LOCALE;
  }

  function loadBundle(loc) {
    return fetch("/js/i18n/locales/" + loc + ".json")
      .then(function (r) {
        if (!r.ok) throw new Error("locale bundle missing");
        return r.json();
      })
      .then(function (json) {
        _strings = json || {};
        return _strings;
      });
  }

  function applyUiStrings() {
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (key && _strings[key]) {
        el.textContent = _strings[key];
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      if (key && _strings[key]) {
        el.setAttribute("placeholder", _strings[key]);
      }
    });
  }

  function getLocale() {
    return _locale;
  }

  function t(key, fallback) {
    return _strings[key] || fallback || key;
  }

  function setLocale(loc, opts) {
    opts = opts || {};
    var normalized = normalize(loc) || DEFAULT_LOCALE;
    _locale = normalized;
    localStorage.setItem(STORAGE_KEY, normalized);
    writeCookie(normalized);

    return loadBundle(normalized).then(function () {
      applyUiStrings();
      if (window.LAWAPP_RTL) {
        window.LAWAPP_RTL.apply(normalized);
      }
      if (!opts.skipServer && window.LAWAPP_AUTH && typeof LAWAPP_AUTH.fetchWithAuth === "function") {
        return LAWAPP_AUTH.fetchWithAuth("/api/i18n/locale", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ locale: normalized }),
        }).catch(function () { /* cookie is enough */ });
      }
      document.dispatchEvent(new CustomEvent("lawapp:locale-changed", { detail: { locale: normalized } }));
      return normalized;
    });
  }

  function init() {
    var stored = normalize(localStorage.getItem(STORAGE_KEY));
    var cookie = normalize(readCookie());
    _locale = stored || cookie || detectBrowserLocale();
    return loadBundle(_locale).then(function () {
      applyUiStrings();
      if (window.LAWAPP_RTL) {
        window.LAWAPP_RTL.apply(_locale);
      }
      return _locale;
    });
  }

  window.LAWAPP_I18N = {
    init: init,
    getLocale: getLocale,
    setLocale: setLocale,
    t: t,
    SUPPORTED: SUPPORTED,
  };
})();
