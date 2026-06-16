/* ============================================================================
   lawapp  -  api-client.js
   Single source of truth for every browser → backend fetch call.

   SECURITY MODEL:
   - JWT tokens stored in httpOnly cookies (set by /api/auth/*)
   - All requests send credentials: 'include' automatically
   - No localStorage-based token storage (see auth.js for session management)
   - 401/403 redirects to login immediately

   IMPORTANT (BEHAVIOUR CONSTITUTION §6): every function here maps to a backend
   route that ACTUALLY EXISTS. Verified endpoints include:
     - POST /api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/refresh
     - POST /api/auth/{google,microsoft,apple,linkedin}
     - GET /api/auth/me
     - POST /cases, GET /cases, GET /cases/{id}, PUT /cases/{id}
     - POST /cases/{id}/uploads, GET /cases/{id}/uploads
     - POST /cases/{id}/uploads/{id}/extract
     - POST /cases/{id}/bundle/generate, GET /cases/{id}/bundle
     - POST /assess (assessment pipeline)
     - All endpoints backed by backend/api/main.py or backend/api/auth_routes.py
   ========================================================================== */
(function () {
  "use strict";

  // Core error class
  function ApiError(message, status, body) {
    this.name = "ApiError";
    this.message = message || "Request failed";
    this.status = status || 0;
    this.body = body || null;
  }
  ApiError.prototype = Object.create(Error.prototype);

  /**
   * Make an authenticated HTTP request with httpOnly cookies.
   * Sends credentials: 'include' automatically.
   * Redirects to login on 401/403.
   */
  async function fetchAuth(method, url, payload, opts) {
    opts = opts || {};
    var fetchOpts = {
      method: method,
      credentials: 'include', // Send httpOnly cookies
      headers: opts.headers || {},
    };

    // Add Content-Type for JSON requests
    if (payload && method !== 'GET') {
      fetchOpts.headers['Content-Type'] = 'application/json';
      fetchOpts.body = JSON.stringify(payload);
    }

    var resp;
    try {
      resp = await fetch(url, fetchOpts);
    } catch (netErr) {
      throw new ApiError("Could not reach the server. Check your connection and try again.", 0, null);
    }

    // Parse response
    var data = null;
    try { data = await resp.json(); } catch (_) { data = null; }

    // Handle auth errors - redirect to login unless the caller is itself an
    // auth form that needs to render the error inline.
    if ((resp.status === 401 || resp.status === 403) && !opts.noAuthRedirect) {
      if (window.LAWAPP_AUTH && typeof window.LAWAPP_AUTH.logout === 'function') {
        window.LAWAPP_AUTH.logout();
      } else {
        window.location.href = '/pages/login.html';
      }
      throw new ApiError('Authentication required', resp.status, data);
    }

    // Handle other errors
    if (!resp.ok) {
      var detail = (data && (data.detail || data.message || data.error)) || ("Request failed (" + resp.status + ")");
      if (typeof detail === "object") { try { detail = JSON.stringify(detail); } catch (_) {} }
      throw new ApiError(detail, resp.status, data);
    }

    return data;
  }

  /**
   * Convenience wrapper for POST requests
   */
  async function postJSON(url, payload, opts) {
    return fetchAuth('POST', url, payload, opts);
  }

  /**
   * Convenience wrapper for GET requests
   */
  async function getJSON(url, opts) {
    return fetchAuth('GET', url, null, opts);
  }

  /**
   * Convenience wrapper for PUT requests
   */
  async function putJSON(url, payload, opts) {
    return fetchAuth('PUT', url, payload, opts);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // UNIFIED API CLIENT - all endpoints use httpOnly cookies
  // ─────────────────────────────────────────────────────────────────────────

  var api = {
    ApiError: ApiError,
    fetchAuth: fetchAuth,
    postJSON: postJSON,
    getJSON: getJSON,
    putJSON: putJSON,
    isLoggedIn: function () {
      if (!window.LAWAPP_AUTH) return false;
      var cache = window.LAWAPP_AUTH._meCache;
      var cacheTime = window.LAWAPP_AUTH._meCacheTime || 0;
      var cacheTTL = window.LAWAPP_AUTH._meCacheTTL || 5000;
      if (cache && (Date.now() - cacheTime) < cacheTTL) {
        return !!cache.isAuthenticated;
      }
      window.LAWAPP_AUTH.isLoggedIn().catch(function () {});
      return false;
    },

    // ─── AUTH ENDPOINTS ───────────────────────────────────────────────────

    /**
     * POST /api/auth/register
     * Register a new user (email + password)
     */
    register: async function (email, password, displayName) {
      return postJSON("/api/auth/register", {
        email: email,
        password: password,
        display_name: displayName || null,
      }, { noAuthRedirect: true });
    },

    /**
     * POST /api/auth/login
     * Login with email + password. JWT stored in httpOnly cookies.
     */
    login: async function (email, password) {
      return postJSON("/api/auth/login", {
        email: email,
        password: password,
      }, { noAuthRedirect: true });
    },

    /**
     * POST /api/auth/logout
     * Logout and revoke all sessions
     */
    logout: async function () {
      return postJSON("/api/auth/logout", { all_sessions: true });
    },

    /**
     * POST /api/auth/refresh
     * Refresh access token using refresh token from cookies
     */
    refreshToken: async function (refreshToken) {
      return postJSON("/api/auth/refresh", { refresh_token: refreshToken });
    },

    /**
     * GET /api/auth/me
     * Get current authenticated user profile
     */
    getCurrentUser: function () {
      return getJSON("/api/auth/me");
    },

    /**
     * POST /api/auth/google
     * OAuth login with Google ID token
     */
    loginGoogle: function (idToken) {
      return postJSON("/api/auth/google", { id_token: idToken });
    },

    /**
     * POST /api/auth/microsoft
     * OAuth login with Microsoft ID token
     */
    loginMicrosoft: function (idToken) {
      return postJSON("/api/auth/microsoft", { id_token: idToken });
    },

    /**
     * POST /api/auth/apple
     * OAuth login with Apple ID token
     */
    loginApple: function (idToken) {
      return postJSON("/api/auth/apple", { id_token: idToken });
    },

    /**
     * POST /api/auth/linkedin
     * OAuth login with LinkedIn ID token
     */
    loginLinkedIn: function (idToken) {
      return postJSON("/api/auth/linkedin", { id_token: idToken });
    },

    /**
     * POST /api/auth/magic-link
     * Request or consume a magic link token
     */
    requestMagicLink: function (email) {
      return postJSON("/api/auth/magic-link", { email: email }, { noAuthRedirect: true });
    },

    consumeMagicLink: function (token) {
      return postJSON("/api/auth/magic-link", { token: token });
    },

    /**
     * GET /api/auth/providers
     * Get list of available auth providers
     */
    getAuthProviders: function () {
      return getJSON("/api/auth/providers");
    },

    // ─── ONBOARDING ENDPOINTS ────────────────────────────────────────────

    /**
     * GET /onboarding/status
     * Check if user has completed onboarding
     */
    getOnboardingStatus: function () {
      return getJSON("/onboarding/status");
    },

    /**
     * POST /onboarding/complete
     * Complete onboarding and create first case
     */
    completeOnboarding: function (role, fullName, employerName, caseType) {
      return postJSON("/onboarding/complete", {
        role: role,
        full_name: fullName,
        employer_name: employerName,
        case_type: caseType,
      });
    },

    // ─── CASE MANAGEMENT ENDPOINTS ───────────────────────────────────────

    /**
     * GET /cases
     * List all cases for current user
     */
    listCases: function () {
      return getJSON("/cases");
    },

    /**
     * POST /cases
     * Create a new case
     */
    createCase: function (claimType, jurisdiction, caseTitle) {
      return postJSON("/cases", {
        claim_type: claimType,
        jurisdiction: jurisdiction || "EW",
        case_title: caseTitle || "My employment claim",
      });
    },

    /**
     * GET /cases/{case_id}
     * Get a specific case with all details
     */
    getCase: function (caseId) {
      return getJSON("/cases/" + caseId);
    },

    /**
     * PUT /cases/{case_id}
     * Update case details
     */
    updateCase: function (caseId, updates) {
      return putJSON("/cases/" + caseId, updates);
    },

    // ─── ASSESSMENT ENDPOINTS ────────────────────────────────────────────

    /**
     * POST /assess
     * Run assessment on case facts
     * Returns: strength, deadline, remedies, citations
     */
    runAssessment: function (query, facts, jurisdiction) {
      return postJSON("/assess", {
        query: query,
        facts: facts || {},
        jurisdiction: jurisdiction || "EW",
        use_model: true,
      });
    },

    // ─── DEADLINE ENDPOINTS ──────────────────────────────────────────────

    /**
     * GET /cases/{case_id}/deadline
     * Get calculated deadline for a case
     */
    getDeadline: function (caseId) {
      return getJSON("/cases/" + caseId + "/deadline");
    },

    /**
     * GET /rules/{claim_type}
     * Get statutory rules for a claim type
     */
    getRules: function (claimType, jurisdiction) {
      return getJSON("/rules/" + claimType + "?jurisdiction=" + (jurisdiction || "EW"));
    },

    // ─── DOCUMENT ENDPOINTS ──────────────────────────────────────────────

    /**
     * POST /cases/{case_id}/bundle/preview
     * Preview generated documents
     */
    previewBundle: function (caseId, documentTypes) {
      return postJSON("/cases/" + caseId + "/bundle/preview", {
        document_types: documentTypes || ["et1", "particulars"],
      });
    },

    /**
     * POST /cases/{case_id}/bundle/generate
     * Generate and save documents
     */
    generateBundle: function (caseId, documentTypes) {
      return postJSON("/cases/" + caseId + "/bundle/generate", {
        document_types: documentTypes || ["et1", "particulars"],
      });
    },

    /**
     * GET /cases/{case_id}/bundle
     * Get list of generated documents
     */
    getBundle: function (caseId) {
      return getJSON("/cases/" + caseId + "/bundle");
    },

    getTimeline: function (caseId) {
      return getJSON("/cases/" + caseId + "/timeline");
    },

    getEscalation: function (caseId) {
      return getJSON("/cases/" + caseId + "/escalation");
    },

    submitHandoffLead: function (payload) {
      return postJSON("/handoff/leads", payload);
    },

    featuresClaimAssessment: function (facts, matterId) {
      return postJSON("/api/features/claim-assessment", {
        facts: facts,
        matter_id: matterId || null,
      });
    },

    /**
     * GET /api/cases/{case_id}/documents
     * Get list of documents for a case
     */
    getDocuments: function (caseId) {
      return getJSON("/api/cases/" + caseId + "/documents");
    },

    // ─── UPLOAD & EXTRACTION ENDPOINTS ──────────────────────────────────

    /**
     * POST /cases/{case_id}/uploads
     * Upload a file (contract, dismissal letter, etc)
     */
    uploadFile: async function (caseId, file) {
      var formData = new FormData();
      formData.append("file", file);

      var resp;
      try {
        resp = await fetch("/cases/" + caseId + "/uploads", {
          method: "POST",
          credentials: "include",
          body: formData, // Don't set Content-Type - let browser set it
        });
      } catch (netErr) {
        throw new ApiError("Could not reach the server. Check your connection and try again.", 0, null);
      }

      if (resp.status === 401 || resp.status === 403) {
        if (window.LAWAPP_AUTH && typeof window.LAWAPP_AUTH.logout === 'function') {
          window.LAWAPP_AUTH.logout();
        } else {
          window.location.href = '/pages/login.html';
        }
        throw new ApiError('Authentication required', resp.status, null);
      }

      var data = null;
      try { data = await resp.json(); } catch (_) { data = null; }

      if (!resp.ok) {
        var detail = (data && (data.detail || data.message || data.error)) || ("Upload failed (" + resp.status + ")");
        throw new ApiError(detail, resp.status, data);
      }

      return data;
    },

    /**
     * POST /cases/{case_id}/uploads/{upload_id}/extract
     * Extract facts from uploaded document
     */
    extractFromUpload: function (caseId, uploadId) {
      return postJSON("/cases/" + caseId + "/uploads/" + uploadId + "/extract", {});
    },

    /**
     * POST /cases/{case_id}/uploads/{upload_id}/apply-confirmed
     * Apply extracted facts after user confirmation
     */
    applyConfirmedFacts: function (caseId, uploadId, confirmedFacts) {
      return postJSON("/cases/" + caseId + "/uploads/" + uploadId + "/apply-confirmed", {
        confirmed_facts: confirmedFacts,
      });
    },

    /**
     * GET /cases/{case_id}/uploads
     * List uploaded files for a case
     */
    getUploads: function (caseId) {
      return getJSON("/cases/" + caseId + "/uploads");
    },

    // ─── FREE PUBLIC TOOLS ────────────────────────────────────────────────
    // Deterministic, DB-first tools that work without login

    /**
     * POST /api/tools/claim-checker
     * Check if user has a potential employment claim
     */
    toolsClaimChecker: function (facts) {
      return postJSON("/api/tools/claim-checker", { facts: facts });
    },

    /**
     * POST /api/tools/deadline-calculator
     * Calculate tribunal deadline
     */
    toolsDeadline: function (params) {
      return postJSON("/api/tools/deadline-calculator", {
        event_date: params.event_date,
        event_type: params.event_type || "dismissal",
        jurisdiction: params.jurisdiction || "EW",
      });
    },

    /**
     * POST /api/tools/compensation-estimate
     * Estimate statutory compensation
     */
    toolsCompensation: function (params) {
      return postJSON("/api/tools/compensation-estimate", {
        weekly_pay: Number(params.weekly_pay),
        months_employed: parseInt(params.months_employed, 10),
        jurisdiction: params.jurisdiction || "EW",
      });
    },

    /**
     * POST /api/tools/acas-prep
     * Get ACAS early conciliation prep
     */
    toolsAcasPrep: function (caseSummary) {
      return postJSON("/api/tools/acas-prep", { case_summary: caseSummary });
    },

    // ─── HEALTH ENDPOINTS ────────────────────────────────────────────────

    /**
     * GET /health
     * Health check endpoint
     */
    getHealth: function () {
      return getJSON("/health");
    },

    /**
     * GET /freshness
     * Get legal source freshness report
     */
    getFreshness: function () {
      return getJSON("/freshness");
    },

    // ─── CASE OS EXTENSIONS ─────────────────────────────────────────────

    createCaseFromAssessment: function (body) {
      return postJSON("/cases", body);
    },

    getTimeline: function (caseId) {
      return getJSON("/cases/" + caseId + "/timeline");
    },

    addTimelineEvent: function (caseId, event) {
      return postJSON("/cases/" + caseId + "/timeline/events", event);
    },

    getEscalation: function (caseId) {
      return getJSON("/cases/" + caseId + "/escalation");
    },

    submitHandoffLead: function (payload) {
      return postJSON("/handoff/leads", payload);
    },

    featuresClaimAssessment: function (facts) {
      return postJSON("/api/features/claim-assessment", { facts: facts });
    },

    featuresStrength: function (facts) {
      return postJSON("/api/features/strength", { facts: facts });
    },

    featuresKnowledgeModules: function () {
      return getJSON("/api/features/knowledge/modules");
    },

    featuresDocumentDecode: function (text, docType) {
      return postJSON("/api/features/document-decode", {
        text: text,
        doc_type: docType || "letter",
      });
    },

    chatMessage: async function (message, conversationId, caseId) {
      var user = await getJSON("/api/auth/me").catch(function () { return null; });
      var userId = (user && (user.id || user.user_id || user.sub)) || "anonymous";
      return postJSON("/api/chat/message", {
        message: message,
        conversation_id: conversationId || null,
        case_id: caseId || null,
        user_id: String(userId),
        jurisdiction: "EW",
        mode: "chat",
      });
    },
  };

  window.LAWAPP_API = api;
})();
