/**
 * fetchWithAuth - thin wrapper for Case OS modules.
 * Canonical implementation lives on LAWAPP_AUTH (cookie auth).
 */
(function () {
  "use strict";
  window.fetchWithAuth = function (url, options) {
    if (!window.LAWAPP_AUTH || typeof window.LAWAPP_AUTH.fetchWithAuth !== "function") {
      return Promise.reject(new Error("LAWAPP_AUTH not loaded"));
    }
    return window.LAWAPP_AUTH.fetchWithAuth(url, options);
  };
})();
