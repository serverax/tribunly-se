/**
 * Case OS app shell - inject layout, mobile nav, active route, case_id propagation.
 */
(function () {
  "use strict";

  var CASE_OS_PAGES = [
    "dashboard", "case-intake", "analysis", "my-case", "timeline", "deadlines",
    "evidence", "documents", "escalation", "advisor", "settings"
  ];

  var NAV_ITEMS = [
    { page: "dashboard", href: "/pages/dashboard.html", label: "Dashboard", short: "Home" },
    { page: "case-intake", href: "/pages/case-intake.html", label: "Case builder", short: "Build" },
    { page: "analysis", href: "/pages/analysis.html", label: "AI analysis", short: "AI" },
    { page: "my-case", href: "/pages/my-case.html", label: "My case", short: "Case" },
    { page: "timeline", href: "/pages/timeline.html", label: "Timeline", short: "Timeline" },
    { page: "deadlines", href: "/pages/deadlines.html", label: "Deadlines", short: "Dates" },
    { page: "evidence", href: "/pages/evidence.html", label: "Evidence hub", short: "Evidence" },
    { page: "documents", href: "/pages/documents.html", label: "Document engine", short: "Docs" },
    { page: "escalation", href: "/pages/escalation.html", label: "Escalation", short: "Escalate" },
    { page: "advisor", href: "/pages/advisor.html", label: "Advisor", short: "Advisor" },
    { page: "settings", href: "/pages/settings.html", label: "Settings", short: "More" }
  ];

  var BOTTOM_NAV = ["dashboard", "my-case", "timeline", "deadlines", "settings"];

  var PAGE_TITLES = {
    dashboard: "Dashboard",
    "case-intake": "Case builder",
    analysis: "AI analysis",
    "my-case": "My case",
    timeline: "Timeline",
    deadlines: "Deadlines",
    evidence: "Evidence hub",
    documents: "Document engine",
    escalation: "Escalation",
    advisor: "Advisor",
    settings: "Settings"
  };

  var shellWired = false;

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

  function navLink(item, compact) {
    var short = item.short || item.label;
    if (compact) {
      return (
        '<a href="' + item.href + '" data-nav-page="' + item.page + '">' +
        '<span aria-hidden="true">&#9679;</span><span>' + short + "</span></a>"
      );
    }
    return (
      '<a href="' + item.href + '" data-nav-page="' + item.page + '">' +
      '<span class="cos-nav-icon" aria-hidden="true">&#9679;</span>' +
      '<span class="cos-nav-label">' + item.label + "</span></a>"
    );
  }

  function injectShell(title) {
    if (document.getElementById("case-os-sidebar")) return;
    var mount = document.getElementById("case-os-main");
    if (!mount) return;

    var inner = mount.innerHTML;
    var sideNav = NAV_ITEMS.map(function (i) { return navLink(i, false); }).join("");
    var bottomNav = BOTTOM_NAV.map(function (page) {
      var item = NAV_ITEMS.filter(function (i) { return i.page === page; })[0];
      return item ? navLink(item, true) : "";
    }).join("");

    var shell = document.createElement("div");
    shell.className = "case-os-shell";
    shell.innerHTML =
      '<div id="case-os-overlay" class="case-os-overlay" hidden></div>' +
      '<aside id="case-os-sidebar" class="case-os-sidebar" aria-label="Case workspace navigation">' +
      '<div class="case-os-sidebar-head">' +
      '<a href="/" class="brand">lawapp</a>' +
      '<button type="button" class="case-os-sidebar-close" aria-label="Close case menu">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
      '<path d="M6 6l12 12M18 6 6 18"/></svg></button></div>' +
      '<nav class="case-os-nav" aria-label="Case sections">' + sideNav + "</nav>" +
      '<div class="case-os-sidebar-foot">Case OS workspace</div></aside>' +
      '<div class="case-os-main">' +
      '<header class="case-os-topbar">' +
      '<button type="button" class="case-os-menu-toggle" aria-controls="case-os-sidebar" ' +
      'aria-expanded="false" aria-label="Open case menu">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
      '<path d="M4 7h16M4 12h16M4 17h16"/></svg></button>' +
      '<h1 class="case-os-topbar-title">' + (title || "Case OS") + "</h1></header>" +
      '<main id="main" class="case-os-content"></main></div>' +
      '<nav class="case-os-bottom-nav" aria-label="Case quick navigation">' + bottomNav + "</nav>";

    shell.querySelector(".case-os-content").innerHTML = inner;
    mount.parentNode.replaceChild(shell, mount);

    if (!document.querySelector(".skip-link")) {
      var skip = document.createElement("a");
      skip.href = "#main";
      skip.className = "skip-link";
      skip.textContent = "Skip to content";
      document.body.insertBefore(skip, document.body.firstChild);
    }
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
      if (link.getAttribute("data-nav-page") === page) {
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
      if (
        href === "/pages/dashboard.html" ||
        href === "/pages/case-intake.html" ||
        href === "/pages/analysis.html"
      ) return;
      a.setAttribute("href", href.split("?")[0] + q);
    });
  }

  function wireShell() {
    if (shellWired) {
      highlightNav();
      propagateCaseId();
      return;
    }
    shellWired = true;

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
    if (document.getElementById("case-os-sidebar")) wireShell();
  }

  function init(opts) {
    opts = opts || {};
    var page = opts.page || activePage();
    var requireAuth = opts.requireAuth !== false;
    var title = opts.title || PAGE_TITLES[page] || "Case OS";

    return Promise.resolve().then(function () {
      if (requireAuth && window.LAWAPP_AUTH) {
        return LAWAPP_AUTH.ensureLoggedIn();
      }
      return true;
    }).then(function (ok) {
      if (!ok) return false;
      injectShell(title);
      wireShell();
      return true;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.CaseOSShell = {
    boot: boot,
    init: init,
    injectShell: injectShell,
    openSidebar: openSidebar,
    closeSidebar: closeSidebar,
    CASE_OS_PAGES: CASE_OS_PAGES,
    NAV_ITEMS: NAV_ITEMS,
  };
})();
