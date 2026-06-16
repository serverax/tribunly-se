/**
 * Domain pack badge for Case OS (domain-agnostic shell).
 * Fetches /api/domains and shows active domain + coming-soon stubs.
 */
(function () {
  "use strict";

  var cached = null;

  function fetchDomains() {
    if (cached) return Promise.resolve(cached);
    if (!window.LAWAPP_API || !window.LAWAPP_API.listDomains) {
      return Promise.resolve(null);
    }
    return window.LAWAPP_API.listDomains().then(function (data) {
      cached = data;
      return data;
    }).catch(function () {
      return null;
    });
  }

  function renderBadge(container, data) {
    if (!container || !data) return;
    var active = data.active_domain || "employment";
    var domains = data.domains || [];
    var current = domains.filter(function (d) { return d.code === active; })[0];
    var label = current ? current.title : active;
    var status = current ? current.status : "unknown";
    var html =
      '<span class="domain-badge domain-badge--' + status + '" title="Active law domain pack">' +
      label +
      "</span>";
    var stubs = domains.filter(function (d) {
      return d.code !== active && (d.status === "stub" || d.status === "unavailable");
    });
    if (stubs.length) {
      html += '<span class="domain-badge domain-badge--soon" title="Future domains (not available)">+' +
        stubs.length + " coming soon</span>";
    }
    container.innerHTML = html;
  }

  function mount() {
    var topbar = document.querySelector(".case-os-topbar");
    if (!topbar || document.getElementById("case-os-domain-badge")) return;
    var slot = document.createElement("div");
    slot.id = "case-os-domain-badge";
    slot.className = "case-os-domain-badge";
    slot.setAttribute("aria-live", "polite");
    var title = topbar.querySelector(".case-os-topbar-title");
    if (title && title.nextSibling) {
      topbar.insertBefore(slot, title.nextSibling);
    } else {
      topbar.appendChild(slot);
    }
    fetchDomains().then(function (data) {
      renderBadge(slot, data);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }

  window.LawAppDomainBadge = { refresh: function () { cached = null; mount(); } };
})();
