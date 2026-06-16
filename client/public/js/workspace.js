/**
 * Case workspace: unified case operating environment.
 * Hash tabs: #timeline, #evidence, #notes, #documents, #analysis
 */
(function () {
  "use strict";

  var TABS = ["timeline", "evidence", "notes", "documents", "analysis"];
  var assessTimer = null;
  var state = {
    caseId: null,
    bundle: null,
    analysisLoading: false,
  };

  function $(id) { return document.getElementById(id); }

  function caseQuery() {
    return state.caseId ? "?case_id=" + encodeURIComponent(state.caseId) : "";
  }

  function setStrength(level) {
    var map = { high: 4, medium: 3, low: 2, uncertain: 1 };
    var n = map[level] || 0;
    document.querySelectorAll("#ws-strength-bars span").forEach(function (b, i) {
      b.className = i < n ? (n >= 3 ? "is-on" : "is-mid") : "";
    });
    $("ws-strength-label").textContent =
      { high: "Strong", medium: "Moderate", low: "Weak", uncertain: "Uncertain" }[level] || "-";
  }

  function formatDate(iso) {
    if (!iso) return "Not set";
    try {
      return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    } catch (_) {
      return iso;
    }
  }

  function activeTab() {
    var hash = (location.hash || "#analysis").replace("#", "");
    return TABS.indexOf(hash) >= 0 ? hash : "analysis";
  }

  function setTab(tab) {
    if (TABS.indexOf(tab) < 0) tab = "analysis";
    location.hash = tab;
    document.querySelectorAll(".workspace-tabs [data-tab]").forEach(function (el) {
      var on = el.getAttribute("data-tab") === tab;
      el.setAttribute("aria-current", on ? "true" : "false");
    });
    document.querySelectorAll(".workspace-tab-panel").forEach(function (panel) {
      panel.classList.toggle("is-active", panel.id === "panel-" + tab);
    });
    if (tab === "analysis") scheduleAnalysis();
  }

  function showError(msg) {
    $("ws-loading").style.display = "none";
    $("ws-error").style.display = "block";
    $("ws-error").textContent = msg;
  }

  function renderHeader(bundle) {
    var c = bundle.case || {};
    var assessment = c.assessment || {};
    var deadline = bundle.deadline || {};
    $("ws-status").textContent = c.status || "diagnosis";
    $("ws-deadline").textContent = formatDate(
      deadline.limitation_date || (assessment.deadline && assessment.deadline.limitation_date)
    );
    setStrength(assessment.strength);
    $("ws-claim-title").textContent = window.CaseEngine
      ? CaseEngine.formatClaimType(c.claim_type)
      : (c.claim_type || "Case").replace(/_/g, " ");
  }

  function renderTimeline(bundle) {
    var list = $("ws-timeline-list");
    list.textContent = "";
    var events = (bundle.timeline && bundle.timeline.events) || [];
    if (!events.length) {
      list.innerHTML = "<li class='cos-muted'>No timeline events yet.</li>";
      return;
    }
    events.forEach(function (ev) {
      var li = document.createElement("li");
      var title = document.createElement("strong");
      title.textContent = ev.title || ev.event_type || "Event";
      var meta = document.createElement("div");
      meta.className = "cos-muted";
      meta.textContent = (ev.event_date || "Date unknown") + (ev.source ? " · " + ev.source : "");
      li.append(title, meta);
      if (ev.description) {
        var desc = document.createElement("p");
        desc.style.margin = "0.35rem 0 0";
        desc.textContent = ev.description;
        li.appendChild(desc);
      }
      list.appendChild(li);
    });
  }

  function renderEvidence(bundle) {
    var list = $("ws-evidence-list");
    list.textContent = "";
    var uploads = (bundle.uploads && bundle.uploads.uploads) || [];
    if (!uploads.length) {
      list.innerHTML = "<li class='cos-muted'>No evidence uploaded.</li>";
      return;
    }
    uploads.forEach(function (u) {
      var li = document.createElement("li");
      li.innerHTML = "<strong>" + (u.original_filename || u.filename || "File") + "</strong>" +
        "<div class='cos-muted'>" + (u.created_at || "") + "</div>";
      list.appendChild(li);
    });
  }

  function renderNotes(bundle) {
    var list = $("ws-notes-list");
    list.textContent = "";
    var events = (bundle.timeline && bundle.timeline.events) || [];
    var notes = events.filter(function (e) {
      return e.event_type === "custom_user_event" && (e.source === "user_entered" || !e.source);
    });
    if (!notes.length) {
      list.innerHTML = "<li class='cos-muted'>No notes yet.</li>";
      return;
    }
    notes.forEach(function (n) {
      var li = document.createElement("li");
      li.innerHTML = "<strong>" + (n.title || "Note") + "</strong><p style='margin:.35rem 0 0'>" +
        (n.description || "") + "</p>";
      list.appendChild(li);
    });
  }

  function renderDocuments(bundle) {
    var list = $("ws-documents-list");
    list.textContent = "";
    if (!state.caseId) return;
    window.LAWAPP_AUTH.fetchWithAuth("/api/cases/" + encodeURIComponent(state.caseId) + "/documents")
      .then(function (r) { return r.ok ? r.json() : { documents: [] }; })
      .then(function (data) {
        var docs = data.documents || [];
        if (!docs.length) {
          list.innerHTML = "<li class='cos-muted'>No drafts yet. Generate from Documents.</li>";
          return;
        }
        docs.forEach(function (d) {
          var li = document.createElement("li");
          li.innerHTML = "<strong>" + (d.doc_type || "document").replace(/_/g, " ") + "</strong>" +
            "<div class='cos-muted'>" + (d.filename || "") + " · " + (d.created_at || "") + "</div>";
          list.appendChild(li);
        });
      })
      .catch(function () {
        list.innerHTML = "<li class='cos-muted'>Could not load documents.</li>";
      });
  }

  function renderAnalysisResult(data) {
    var assessment = (data && data.assessment) || data || {};
    $("ws-reasoning").textContent = assessment.reasoning_summary || assessment.summary || "No reasoning yet.";
    $("ws-risk").textContent = assessment.strength
      ? ("Strength: " + assessment.strength)
      : (assessment.risk_level || "Run analysis to see risk score.");
    $("ws-next-action").textContent = assessment.recommended_next_step
      || assessment.next_step
      || "Complete missing facts and review deadlines.";
    if (data && data.trace_id) {
      $("ws-trace-id").textContent = "Trace: " + data.trace_id;
    }
  }

  function scheduleAnalysis() {
    if (assessTimer) clearTimeout(assessTimer);
    assessTimer = setTimeout(runAnalysis, 600);
  }

  async function runAnalysis() {
    if (!state.caseId || state.analysisLoading) return;
    var c = (state.bundle && state.bundle.case) || {};
    var assessment = c.assessment || {};
    if (assessment.reasoning_summary) {
      renderAnalysisResult({ assessment: assessment, trace_id: c.trace_id });
    }
    var facts = c.facts || assessment.facts || {};
    var query = $("ws-analysis-query").value.trim() ||
      ("Review my " + (c.claim_type || "employment") + " case");
    state.analysisLoading = true;
    $("ws-analysis-status").textContent = "Analysing...";
    try {
      var result = await window.CaseEngine.runAssessment(query, facts, c.jurisdiction || "EW");
      renderAnalysisResult(result);
      $("ws-analysis-status").textContent = "Updated " + new Date().toLocaleTimeString("en-GB");
    } catch (e) {
      $("ws-analysis-status").textContent = e.message || "Analysis failed";
    } finally {
      state.analysisLoading = false;
    }
  }

  async function saveNote() {
    var title = $("ws-note-title").value.trim();
    var body = $("ws-note-body").value.trim();
    if (!title && !body) return;
    try {
      await window.CaseEngine.addTimelineEvent(state.caseId, {
        event_type: "custom_user_event",
        title: title || "Note",
        description: body,
        source: "user_entered",
      });
      $("ws-note-title").value = "";
      $("ws-note-body").value = "";
      state.bundle = await window.CaseEngine.loadCase(state.caseId);
      renderNotes(state.bundle);
    } catch (e) {
      $("ws-note-status").textContent = e.message || "Could not save note";
    }
  }

  async function uploadEvidence(files) {
    if (!files || !files.length || !window.LAWAPP_API || !window.LAWAPP_API.uploadFile) {
      $("ws-upload-status").textContent = "Upload requires API client.";
      return;
    }
    $("ws-upload-status").textContent = "Uploading...";
    try {
      for (var i = 0; i < files.length; i++) {
        await window.LAWAPP_API.uploadFile(state.caseId, files[i]);
      }
      state.bundle = await window.CaseEngine.loadCase(state.caseId);
      renderEvidence(state.bundle);
      $("ws-upload-status").textContent = "Upload complete.";
    } catch (e) {
      $("ws-upload-status").textContent = e.message || "Upload failed";
    }
  }

  function wireNav() {
    document.querySelectorAll(".workspace-tabs [data-tab]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        setTab(el.getAttribute("data-tab"));
      });
    });
    window.addEventListener("hashchange", function () { setTab(activeTab()); });
    $("ws-note-save").addEventListener("click", saveNote);
    $("ws-analysis-refresh").addEventListener("click", runAnalysis);
    $("ws-analysis-query").addEventListener("input", scheduleAnalysis);
    var fileInput = $("ws-evidence-file");
    fileInput.addEventListener("change", function () {
      uploadEvidence(fileInput.files);
      fileInput.value = "";
    });
  }

  function updateSidebarLinks() {
    var q = caseQuery();
    document.querySelectorAll("[data-ws-case-link]").forEach(function (a) {
      var base = a.getAttribute("data-ws-case-link");
      a.href = base + q;
    });
  }

  async function loadFirstCase() {
    var cases = await window.CaseEngine.listCases();
    if (!cases.length) throw new Error("No saved cases. Start from the story builder.");
    return cases[0].case_id;
  }

  async function init() {
    var ok = await window.LAWAPP_AUTH.ensureLoggedIn();
    if (!ok) return;
    wireNav();
    try {
      state.caseId = window.CaseEngine.getActiveCaseId();
      if (!state.caseId) state.caseId = await loadFirstCase();
      window.CaseEngine.setActiveCaseId(state.caseId);
      updateSidebarLinks();
      state.bundle = await window.CaseEngine.loadCase(state.caseId);
      $("ws-loading").style.display = "none";
      $("ws-workspace").style.display = "block";
      renderHeader(state.bundle);
      renderTimeline(state.bundle);
      renderEvidence(state.bundle);
      renderNotes(state.bundle);
      renderDocuments(state.bundle);
      setTab(activeTab());
    } catch (e) {
      showError(e.message || "Failed to load workspace");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
