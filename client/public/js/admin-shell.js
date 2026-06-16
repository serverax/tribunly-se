/**
 * Admin control center shell: JWT admin gate + shared fetch.
 */
(function () {
  "use strict";

  var NAV = [
    { href: "/admin/dashboard.html", label: "Dashboard" },
    { href: "/admin/cases.html", label: "Cases" },
    { href: "/admin/ai-logs.html", label: "AI logs" },
    { href: "/admin/users.html", label: "Users" },
    { href: "/admin/system-health.html", label: "System health" },
    { href: "/admin/compliance.html", label: "Compliance" },
  ];

  function currentPage() {
    var path = location.pathname.split("/").pop() || "dashboard.html";
    return path;
  }

  function renderNav(active) {
    var nav = document.getElementById("admin-nav");
    if (!nav) return;
    nav.textContent = "";
    NAV.forEach(function (item) {
      var a = document.createElement("a");
      a.href = item.href;
      a.textContent = item.label;
      if (item.href.indexOf(active) >= 0) a.setAttribute("aria-current", "page");
      nav.appendChild(a);
    });
  }

  async function requireAdmin() {
    var ok = await window.LAWAPP_AUTH.ensureLoggedIn();
    if (!ok) return false;
    var user = await window.LAWAPP_AUTH.getCurrentUser();
    if (!user || !user.is_admin) {
      var denied = document.getElementById("admin-denied");
      var content = document.getElementById("admin-content");
      if (denied) denied.style.display = "block";
      if (content) content.style.display = "none";
      return false;
    }
    return true;
  }

  async function adminFetch(path) {
    var resp = await window.LAWAPP_AUTH.fetchWithAuth(path);
    if (!resp.ok) {
      var detail = "Request failed (" + resp.status + ")";
      try {
        var err = await resp.json();
        if (err.detail) detail = err.detail;
      } catch (_) { /* ignore */ }
      throw new Error(detail);
    }
    return resp.json();
  }

  async function init() {
    renderNav(currentPage());
    return requireAdmin();
  }

  window.LAWAPP_ADMIN = {
    init: init,
    fetch: adminFetch,
    renderNav: renderNav,
  };
})();
