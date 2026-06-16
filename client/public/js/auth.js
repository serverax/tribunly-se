/**
 * LAWAPP AUTH - httpOnly Cookie-Based Security Model
 *
 * SECURITY DESIGN:
 * - JWT tokens stored in httpOnly, Secure, SameSite cookies (NOT localStorage)
 * - No sensitive tokens in JavaScript memory or DOM
 * - Credentials sent with credentials: 'include' for cross-site requests
 * - Session check via /api/auth/me endpoint (backend source of truth)
 * - Fails closed: any 401/403 redirects to login immediately
 * - CSRF protection: backend validates Origin/Referer headers
 */

(function() {
  window.LAWAPP_AUTH = {
    /**
     * Check if user is authenticated by calling the /api/auth/me endpoint.
     * This is the authoritative check - no client-side token inspection.
     * Caches result for 5 seconds to avoid excessive calls.
     */
    _meCache: null,
    _meCacheTime: 0,
    _meCacheTTL: 5000, // 5 seconds

    async isLoggedIn() {
      try {
        const now = Date.now();
        if (this._meCache && (now - this._meCacheTime) < this._meCacheTTL) {
          return this._meCache.isAuthenticated;
        }

        const resp = await fetch('/api/auth/me', {
          credentials: 'include', // send httpOnly cookies
        });

        if (resp.ok) {
          this._meCache = { isAuthenticated: true };
          this._meCacheTime = now;
          return true;
        } else if (resp.status === 401) {
          this._meCache = { isAuthenticated: false };
          this._meCacheTime = now;
          return false;
        } else {
          // Server error - fail closed
          return false;
        }
      } catch (err) {
        console.error('Auth check error:', err);
        return false;
      }
    },

    /**
     * Get current user profile from /api/auth/me.
     * Returns { id, email, created_at, subscription_status } or null if not authenticated.
     */
    async getCurrentUser() {
      try {
        const resp = await fetch('/api/auth/me', {
          credentials: 'include',
        });

        if (!resp.ok) {
          if (resp.status === 401 || resp.status === 403) {
            this.logout();
          }
          return null;
        }

        return await resp.json();
      } catch (err) {
        console.error('Get current user error:', err);
        return null;
      }
    },

    /**
     * Ensure user is logged in. Redirect to login if not.
     * Returns true if authenticated, false otherwise.
     */
    async ensureLoggedIn() {
      const isAuth = await this.isLoggedIn();
      if (!isAuth) {
        window.location.href = '/pages/login.html?next=' + encodeURIComponent(window.location.pathname);
        return false;
      }
      return true;
    },

    /**
     * Compatibility shim for pages still migrating from bearer-token auth.
     * Cookie auth does not need JS-readable Authorization headers.
     */
    getAuthHeaders() {
      return {};
    },

    /**
     * Logout: call backend to revoke session, clear cache, redirect to login.
     */
    async logout() {
      try {
        // Attempt server-side logout (revoke refresh token)
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ all_sessions: true }),
          credentials: 'include',
        });
      } catch (err) {
        // Ignore errors - client logout continues anyway
        console.warn('Logout request failed:', err);
      }

      // Clear client state
      this._meCache = null;
      sessionStorage.removeItem('assessment_result');
      sessionStorage.removeItem('assessment_facts');
      sessionStorage.removeItem('assessment_facts_full');

      // Redirect to login
      window.location.href = '/pages/login.html';
    },

    /**
     * Fetch with automatic auth and error handling.
     * Sends cookies automatically (credentials: 'include').
     * Fails closed: redirects to login on 401/403.
     */
    async fetchWithAuth(url, options) {
      const opts = Object.assign({}, options || {});
      opts.credentials = opts.credentials || 'include'; // Always include cookies
      opts.headers = opts.headers || {};

      const resp = await fetch(url, opts);

      if (resp.status === 401 || resp.status === 403) {
        console.warn('Auth failed: ' + resp.status + '. Redirecting to login.');
        this.logout();
        throw new Error('Authentication failed');
      }

      return resp;
    },

    /**
     * Update navigation bar based on login status.
     */
    async updateNav() {
      const nav = document.querySelector('.nav-links');
      if (!nav) return;

      nav.textContent = '';

      const home = document.createElement('a');
      home.href = '/';
      home.textContent = 'Home';
      nav.appendChild(home);

      const isAuth = await this.isLoggedIn();

      if (isAuth) {
        const dashboard = document.createElement('a');
        dashboard.href = '/pages/dashboard.html';
        dashboard.textContent = 'Dashboard';

        const logout = document.createElement('a');
        logout.href = '#';
        logout.textContent = 'Logout';
        logout.onclick = (e) => {
          e.preventDefault();
          this.logout();
        };

        nav.append(dashboard, logout);
      } else {
        const login = document.createElement('a');
        login.href = '/pages/login.html';
        login.textContent = 'Login';

        const register = document.createElement('a');
        register.href = '/pages/register.html';
        register.textContent = 'Sign up';

        nav.append(login, register);
      }
    }
  };
})();

// ── Controlled-beta notice (remove at public launch) ─────────────────────────
// Injected site-wide so the beta warning stays visible on every page that
// loads auth.js. Safe DOM construction only  -  no innerHTML.
(function () {
  function addBetaBanner() {
    if (document.getElementById('beta-banner')) return;
    var bar = document.createElement('div');
    bar.id = 'beta-banner';
    bar.setAttribute('role', 'note');
    bar.style.cssText = 'background:#fef3c7;color:#78350f;padding:8px 16px;' +
      'font-size:14px;text-align:center;border-bottom:1px solid #f59e0b;';
    var strong = document.createElement('strong');
    strong.textContent = 'Controlled beta  -  11 employment topics. Not legal advice. ';
    bar.appendChild(strong);
    bar.appendChild(document.createTextNode(
      'This tool provides legal information to help you prepare. Do not enter real names, ' +
      'addresses, NI numbers, medical details or other sensitive personal data during the beta. ' +
      'Tribunal deadlines are strict  -  verify dates with ACAS or a qualified adviser.'));
    document.body.insertBefore(bar, document.body.firstChild);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addBetaBanner);
  } else { addBetaBanner(); }
})();
