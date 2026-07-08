/**
 * Case OS app shell - inject layout, mobile nav, active route, case_id propagation.
 */
(function () {
  "use strict";

  var CASE_OS_PAGES = [
    "dashboard", "case-intake", "analysis", "workspace", "timeline", "deadlines",
    "evidence", "documents", "escalation", "advisor", "settings"
  ];

  var NAV_ITEMS = [
    { page: "dashboard", href: "/pages/dashboard.html", label: "Dashboard", short: "Home" },
    { page: "case-intake", href: "/pages/case-intake.html", label: "Case builder", short: "Build" },
    { page: "analysis", href: "/pages/analysis.html", label: "AI analysis", short: "AI" },
    { page: "workspace", href: "/pages/workspace.html", label: "My case", short: "Case" },
    { page: "timeline", href: "/pages/workspace.html#timeline", label: "Timeline", short: "Timeline" },
    { page: "deadlines", href: "/pages/deadlines.html", label: "Deadlines", short: "Dates" },
    { page: "evidence", href: "/pages/evidence.html", label: "Evidence hub", short: "Evidence" },
    { page: "documents", href: "/pages/documents.html", label: "Document engine", short: "Docs" },
    { page: "escalation", href: "/pages/escalation.html", label: "Escalation", short: "Escalate" },
    { page: "advisor", href: "/pages/advisor.html", label: "Advisor", short: "Advisor" },
    { page: "settings", href: "/pages/settings.html", label: "Settings", short: "More" }
  ];

  var BOTTOM_NAV = ["dashboard", "workspace", "timeline", "deadlines", "settings"];

  var PAGE_TITLES = {
    dashboard: "Dashboard",
    "case-intake": "Case builder",
    analysis: "AI analysis",
    workspace: "Case workspace",
    timeline: "Timeline",
    deadlines: "Deadlines",
    evidence: "Evidence hub",
    documents: "Document engine",
    escalation: "Escalation",
    advisor: "Advisor",
    settings: "Settings"
  };

  var shellWired = false;

  function betaFlagEnabled(flagName) {
    if (!window.LAWAPP_BETA_SCOPE || typeof window.LAWAPP_BETA_SCOPE.isEnabled !== "function") {
      return flagName === "handoffReferrals" ? false : true;
    }
    return LAWAPP_BETA_SCOPE.isEnabled(flagName);
  }

  function visibleNavItems() {
    return NAV_ITEMS.filter(function (item) {
      if (item.page === "escalation" && !betaFlagEnabled("handoffReferrals")) return false;
      return true;
    });
  }

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
    var navItems = visibleNavItems();
    var sideNav = navItems.map(function (i) { return navLink(i, false); }).join("");
    var bottomNav = BOTTOM_NAV.map(function (page) {
      var item = navItems.filter(function (i) { return i.page === page; })[0];
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
      '<h1 class="case-os-topbar-title">' + (title || "Case OS") + "</h1>" +
      '<div id="case-os-domain-badge" class="case-os-domain-badge" aria-live="polite"></div>' +
      '<div class="case-os-lang-switcher" role="group" aria-label="Language">' +
      '<button type="button" class="case-os-lang-btn" data-set-locale="en">EN</button>' +
      '<button type="button" class="case-os-lang-btn" data-set-locale="ar">AR</button>' +
      "</div></header>" +
      '<main id="main" class="case-os-content"></main>' +
      '<footer class="case-os-boundary boundary" role="contentinfo">' +
      '<p>This tool provides legal information, not legal advice, and does not create a solicitor-client relationship. ' +
      'Tribunal deadlines are strict - verify dates with ACAS or a qualified adviser before relying on them.</p>' +
      '</footer></div>' +
      '<nav class="case-os-bottom-nav" aria-label="Case quick navigation">' + bottomNav + "</nav>";

    shell.querySelector(".case-os-content").innerHTML = inner;
    mount.parentNode.replaceChild(shell, mount);
    injectBoundaryFooter();

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
        href === "/pages/analysis.html" ||
        href.indexOf("#") !== -1
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
    document.querySelectorAll("[data-set-locale]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var loc = btn.getAttribute("data-set-locale");
        if (window.LAWAPP_I18N && typeof LAWAPP_I18N.setLocale === "function") {
          LAWAPP_I18N.setLocale(loc);
        }
        document.querySelectorAll(".case-os-lang-btn").forEach(function (b) {
          b.classList.toggle("is-active", b.getAttribute("data-set-locale") === loc);
        });
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSidebar();
    });
    highlightNav();
    propagateCaseId();
    if (window.LawAppDomainBadge && typeof LawAppDomainBadge.refresh === "function") {
      LawAppDomainBadge.refresh();
    }
  }

  function injectBoundaryFooter() {
    if (document.getElementById("case-os-boundary-footer")) return;
    if (!document.body.classList.contains("case-os")) return;
    if (document.querySelector(".case-os-shell .case-os-boundary.boundary")) return;
    var footer = document.createElement("footer");
    footer.id = "case-os-boundary-footer";
    footer.className = "case-os-boundary";
    footer.setAttribute("role", "contentinfo");
    footer.innerHTML =
      "<p>lawapp is not a law firm and does not provide regulated legal advice. " +
      "Outputs are information only. We do not file claims or represent you at tribunal.</p>";
    document.body.appendChild(footer);
  }

  function boot() {
    if (!document.body.classList.contains("case-os")) return;
    if (document.getElementById("case-os-sidebar")) wireShell();
    injectBoundaryFooter();
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
      injectBoundaryFooter();
      if (window.LAWAPP_I18N) {
        return LAWAPP_I18N.init().then(function (loc) {
          document.querySelectorAll(".case-os-lang-btn").forEach(function (b) {
            b.classList.toggle("is-active", b.getAttribute("data-set-locale") === loc);
          });
          return true;
        });
      }
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
