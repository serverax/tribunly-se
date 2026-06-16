/**
 * CaseEngineProvider - case state, timeline, evidence, AI output.
 * localStorage cache + API sync via LAWAPP_API / fetchWithAuth.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "lawapp_active_case_id";
  var CACHE_PREFIX = "lawapp_case_cache_";

  function safeParse(raw) {
    try { return JSON.parse(raw); } catch (_) { return null; }
  }

  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent("case-engine:" + name, { detail: detail || {} }));
  }

  var CaseEngine = {
    _cache: {},

    getActiveCaseId: function () {
      var params = new URLSearchParams(window.location.search);
      var fromUrl = params.get("case_id");
      if (fromUrl) {
        localStorage.setItem(STORAGE_KEY, fromUrl);
        return fromUrl;
      }
      return localStorage.getItem(STORAGE_KEY) || null;
    },

    setActiveCaseId: function (caseId) {
      if (caseId) localStorage.setItem(STORAGE_KEY, caseId);
      else localStorage.removeItem(STORAGE_KEY);
      emit("case-changed", { caseId: caseId });
    },

    getCached: function (caseId) {
      if (this._cache[caseId]) return this._cache[caseId];
      var raw = localStorage.getItem(CACHE_PREFIX + caseId);
      if (raw) {
        this._cache[caseId] = safeParse(raw);
        return this._cache[caseId];
      }
      return null;
    },

    setCache: function (caseId, data) {
      this._cache[caseId] = data;
      try {
        localStorage.setItem(CACHE_PREFIX + caseId, JSON.stringify(data));
      } catch (_) { /* quota */ }
    },

    clearCache: function (caseId) {
      delete this._cache[caseId];
      localStorage.removeItem(CACHE_PREFIX + caseId);
    },

    /**
     * Load full case bundle from API.
     */
    loadCase: async function (caseId) {
      if (!caseId) throw new Error("case_id required");
      var api = window.LAWAPP_API;
      var auth = window.LAWAPP_AUTH;

      var caseData, deadline, uploads, bundle, timeline, escalation;

      if (api && typeof api.getCase === "function") {
        caseData = await api.getCase(caseId);
        deadline = await api.getDeadline(caseId).catch(function () { return null; });
        uploads = await api.getUploads(caseId).catch(function () { return { uploads: [] }; });
        bundle = await api.getBundle(caseId).catch(function () { return { bundle_generated: false }; });
        timeline = await api.getTimeline(caseId).catch(function () { return null; });
        escalation = await api.getEscalation(caseId).catch(function () { return null; });
      } else if (auth) {
        var base = "";
        var fetchJson = async function (path) {
          var r = await auth.fetchWithAuth(base + path);
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        };
        caseData = await fetchJson("/cases/" + caseId);
        deadline = await auth.fetchWithAuth(base + "/cases/" + caseId + "/deadline")
          .then(function (r) { return r.ok ? r.json() : null; });
        uploads = await auth.fetchWithAuth(base + "/cases/" + caseId + "/uploads")
          .then(function (r) { return r.ok ? r.json() : { uploads: [] }; });
        bundle = await auth.fetchWithAuth(base + "/cases/" + caseId + "/bundle")
          .then(function (r) { return r.ok ? r.json() : { bundle_generated: false }; });
        timeline = await auth.fetchWithAuth(base + "/cases/" + caseId + "/timeline")
          .then(function (r) { return r.ok ? r.json() : null; });
        escalation = await auth.fetchWithAuth(base + "/cases/" + caseId + "/escalation")
          .then(function (r) { return r.ok ? r.json() : null; });
      } else {
        throw new Error("No API client available");
      }

      var bundleData = {
        case: caseData,
        deadline: deadline,
        uploads: uploads,
        bundle: bundle,
        timeline: timeline,
        escalation: escalation,
        loadedAt: new Date().toISOString(),
      };
      this.setCache(caseId, bundleData);
      emit("case-loaded", { caseId: caseId, data: bundleData });
      return bundleData;
    },

    listCases: async function () {
      if (window.LAWAPP_API && window.LAWAPP_API.listCases) {
        var out = await window.LAWAPP_API.listCases();
        return out.cases || out;
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/cases");
      if (!r.ok) throw new Error("Failed to list cases");
      var data = await r.json();
      return data.cases || [];
    },

    createCase: async function (payload) {
      var body = {
        claim_type: payload.claim_type || "unfair_dismissal",
        jurisdiction: payload.jurisdiction || "EW",
        assessment: payload.assessment || {},
        key_dates: payload.key_dates || {},
        facts: payload.facts || null,
        recommended_next_step: payload.recommended_next_step || null,
      };
      if (window.LAWAPP_API && window.LAWAPP_API.createCaseFromAssessment) {
        return window.LAWAPP_API.createCaseFromAssessment(body);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error("Case create failed");
      var created = await r.json();
      if (created.case_id) this.setActiveCaseId(created.case_id);
      return created;
    },

    runAssessment: async function (query, facts, jurisdiction) {
      if (window.LAWAPP_API && window.LAWAPP_API.runAssessment) {
        return window.LAWAPP_API.runAssessment(query, facts, jurisdiction);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          facts: facts || {},
          jurisdiction: jurisdiction || "EW",
          use_model: true,
        }),
      });
      if (!r.ok) throw new Error("Assessment failed");
      return r.json();
    },

    runClaimAssessment: async function (facts) {
      if (window.LAWAPP_API && window.LAWAPP_API.featuresClaimAssessment) {
        return window.LAWAPP_API.featuresClaimAssessment(facts);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/api/features/claim-assessment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ facts: facts }),
      });
      if (!r.ok) throw new Error("Claim assessment failed");
      return r.json();
    },

    calculateDeadline: async function (params) {
      if (window.LAWAPP_API && window.LAWAPP_API.toolsDeadline) {
        return window.LAWAPP_API.toolsDeadline(params);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/api/tools/deadline-calculator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!r.ok) throw new Error("Deadline calculation failed");
      return r.json();
    },

    addTimelineEvent: async function (caseId, event) {
      if (window.LAWAPP_API && window.LAWAPP_API.addTimelineEvent) {
        return window.LAWAPP_API.addTimelineEvent(caseId, event);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/cases/" + caseId + "/timeline/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
      });
      if (!r.ok) throw new Error("Timeline event failed");
      this.clearCache(caseId);
      return r.json();
    },

    uploadEvidence: async function (caseId, file) {
      if (window.LAWAPP_API && window.LAWAPP_API.uploadFile) {
        return window.LAWAPP_API.uploadFile(caseId, file);
      }
      throw new Error("Upload requires LAWAPP_API");
    },

    submitReferral: async function (payload) {
      if (window.LAWAPP_API && window.LAWAPP_API.submitHandoffLead) {
        return window.LAWAPP_API.submitHandoffLead(payload);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/handoff/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error("Referral failed");
      return r.json();
    },

    formatClaimType: function (type) {
      if (!type) return "Employment claim";
      var map = {
        unfair_dismissal: "Unfair dismissal",
        unpaid_wages: "Unpaid wages",
        wrongful_dismissal: "Wrongful dismissal",
        redundancy: "Redundancy",
      };
      return map[type] || String(type).replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    },

    strengthPercent: function (strength) {
      var m = { high: 78, medium: 52, low: 28, uncertain: 40 };
      return m[strength] || 40;
    },

    urgencyClass: function (urgency) {
      if (urgency === "expired") return "expired";
      if (urgency === "due_within_7" || urgency === "due_within_14") return "urgent";
      if (urgency === "due_within_30") return "warning";
      return "safe";
    },

    _liveTimer: null,
    _liveAbort: null,

    /**
     * Debounced live assessment for case builder (calls POST /assess).
     */
    liveAssess: function (facts, opts) {
      opts = opts || {};
      var self = this;
      var delay = opts.delayMs != null ? opts.delayMs : 800;
      return new Promise(function (resolve, reject) {
        if (self._liveTimer) clearTimeout(self._liveTimer);
        if (self._liveAbort) {
          try { self._liveAbort.abort(); } catch (_) {}
        }
        self._liveTimer = setTimeout(async function () {
          self._liveTimer = null;
          var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
          self._liveAbort = controller;
          try {
            var query = (facts && facts.brief_facts) || "Live case preview";
            var body = {
              query: query,
              facts: facts || {},
              jurisdiction: (facts && facts.jurisdiction) || "EW",
              use_model: opts.useModel !== false,
            };
            var resp;
            if (window.LAWAPP_AUTH) {
              resp = await window.LAWAPP_AUTH.fetchWithAuth("/assess", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
                signal: controller ? controller.signal : undefined,
              });
            } else {
              resp = await fetch("/assess", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify(body),
                signal: controller ? controller.signal : undefined,
              });
            }
            if (!resp.ok) throw new Error("Assessment HTTP " + resp.status);
            var data = await resp.json();
            emit("live-assessment", { facts: facts, result: data });
            resolve(data);
          } catch (err) {
            if (err && err.name === "AbortError") return;
            reject(err);
          } finally {
            self._liveAbort = null;
          }
        }, delay);
      });
    },

    getTimeline: async function (caseId) {
      if (window.LAWAPP_API && window.LAWAPP_API.getTimeline) {
        return window.LAWAPP_API.getTimeline(caseId);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/cases/" + caseId + "/timeline");
      if (!r.ok) throw new Error("Timeline fetch failed");
      return r.json();
    },

    getEscalation: async function (caseId) {
      if (window.LAWAPP_API && window.LAWAPP_API.getEscalation) {
        return window.LAWAPP_API.getEscalation(caseId);
      }
      var r = await window.LAWAPP_AUTH.fetchWithAuth("/cases/" + caseId + "/escalation");
      if (!r.ok) throw new Error("Escalation fetch failed");
      return r.json();
    },
  };

  window.CaseEngine = CaseEngine;
})();
