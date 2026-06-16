/**
 * Case OS app shell - mobile nav, active route, case_id query propagation.
 */
(function () {
  "use strict";

  var CASE_OS_PAGES = [
    "dashboard", "case-intake", "analysis", "my-case", "timeline", "deadlines",
    "evidence", "documents", "escalation", "advisor", "settings"
  ];

  function activePage() {
    return document.body.getAttribute("data-case-os-page") || "";
  }

  function caseQuery() {
    var id = window.CaseEngine && CaseEngine.getActiveCaseId();
    if (!id) {
      var p = new URLSearchParams(window.location.search);
      id = p.get("case_id");
    }
    return id ? "?case_id=" + encodeURIComponent(id) : "";
  }

  function openSidebar() {
    var sidebar = document.getElementById("case-os-sidebar");
    var overlay = document.getElementById("case-os-overlay");
    var toggle = document.querySelector(".case-os-menu-toggle");
    if (!sidebar || !overlay) return;
    sidebar.classList.add("is-open");
    overlay.hidden = false;
    overlay.classList.add("is-visible");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }

  function closeSidebar() {
    var sidebar = document.getElementById("case-os-sidebar");
    var overlay = document.getElementById("case-os-overlay");
    var toggle = document.querySelector(".case-os-menu-toggle");
    if (!sidebar || !overlay) return;
    sidebar.classList.remove("is-open");
    overlay.classList.remove("is-visible");
    overlay.hidden = true;
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
  }

  function highlightNav() {
    var page = activePage();
    document.querySelectorAll("[data-nav-page]").forEach(function (link) {
      var match = link.getAttribute("data-nav-page") === page;
      if (match) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  }

  function propagateCaseId() {
    var q = caseQuery();
    if (!q) return;
    document.querySelectorAll(".case-os-nav a, .case-os-bottom-nav a").forEach(function (a) {
      var href = a.getAttribute("href");
      if (!href || href.indexOf("case_id=") !== -1) return;
      if (href.indexOf("/pages/") === -1) return;
      if (href === "/pages/dashboard.html" || href === "/pages/case-intake.html" || href === "/pages/analysis.html") return;
      a.setAttribute("href", href.split("?")[0] + q);
    });
  }

  function wireShell() {
    var toggle = document.querySelector(".case-os-menu-toggle");
    var closeBtn = document.querySelector(".case-os-sidebar-close");
    var overlay = document.getElementById("case-os-overlay");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var sidebar = document.getElementById("case-os-sidebar");
        if (sidebar && sidebar.classList.contains("is-open")) closeSidebar();
        else openSidebar();
      });
    }
    if (closeBtn) closeBtn.addEventListener("click", closeSidebar);
    if (overlay) overlay.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSidebar();
    });
    highlightNav();
    propagateCaseId();
  }

  function boot() {
    if (!document.body.classList.contains("case-os")) return;
    wireShell();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.CaseOSShell = {
    boot: boot,
    openSidebar: openSidebar,
    closeSidebar: closeSidebar,
    CASE_OS_PAGES: CASE_OS_PAGES,
  };
})();
