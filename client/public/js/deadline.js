/**
 * Client-side deadline calculator — Phase 10 WASM Integration.
 *
 * Uses Rust WASM for deterministic legal arithmetic.
 * Falls back to strict JS equivalent if WASM fails to load.
 *
 * Assigned to window.LawappDeadline for inline-script use.
 */

(function (global) {
  'use strict';

  let wasmModule = null;

  // ── WASM Loader ─────────────────────────────────────────────────────────────
  async function initWasm() {
    if (wasmModule) return wasmModule;
    try {
      const module = await import('../wasm/lawapp_wasm.js');
      await module.default();
      wasmModule = module;
      console.log('lawapp-wasm loaded successfully.');
      return module;
    } catch (e) {
      console.warn('WASM load failed, falling back to JS calculator:', e);
      return null;
    }
  }

  // Pre-initialize WASM asynchronously.
  initWasm();

  // ── JS Fallback Logic (strict mirror of WASM/Python) ──────────────────────
  function calculateStatutoryNoticeJS(serviceMonths, direction) {
    if (serviceMonths < 0) return { ok: false, error: 'Service months must be positive.' };
    const notes = [
      'Continuous service supplied directly; calculator does not assess interruption rules.',
      'Returns statutory MINIMUM only — contract notice prevails if longer.',
    ];
    if (direction === 'employee_to_employer') {
      const weeks = serviceMonths < 1 ? 0 : 1;
      if (weeks === 1) notes.push('ERA 1996 s.86(2): 1 week fixed minimum after 1 month service.');
      return { ok: true, statutory_minimum_weeks: weeks, full_years_counted: 0, notes };
    }
    let weeks = 0;
    let years = 0;
    if (serviceMonths < 1) {
      notes.push('Under 1 month service: no statutory minimum notice.');
    } else if (serviceMonths < 24) {
      weeks = 1;
      notes.push('1 month to 2 years service: 1 week statutory minimum.');
    } else {
      years = Math.floor(serviceMonths / 12);
      weeks = Math.min(years, 12);
      notes.push(`${years} years service: ${weeks} weeks statutory minimum (capped at 12).`);
    }
    return { ok: true, statutory_minimum_weeks: weeks, full_years_counted: years, notes };
  }

  function addCalendarMonths(d, n) {
    const year  = d.getFullYear();
    const month = d.getMonth() + n;           
    const targetYear  = year  + Math.floor(month / 12);
    const targetMonth = ((month % 12) + 12) % 12;
    const maxDay = new Date(targetYear, targetMonth + 1, 0).getDate();
    const day    = Math.min(d.getDate(), maxDay);
    return new Date(targetYear, targetMonth, day);
  }

  function parseDate(s) {
    if (!s) return null;
    const parts = s.split('-').map(Number);
    if (parts.length !== 3 || parts.some(isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function formatDate(d) {
    if (!d || isNaN(d.getTime())) return null;
    const y  = d.getFullYear();
    const m  = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  }

  function daysDiff(d1, d2) {
    return Math.round((d2.getTime() - d1.getTime()) / 86400000);
  }

  function computeDeadlineJS(edtStr, timeLimitMonths, ecDayAStr, ecDayBStr) {
    const edt = parseDate(edtStr);
    if (!edt) return null;

    const anniversary = addCalendarMonths(edt, timeLimitMonths);
    const baseLimit   = new Date(anniversary.getTime() - 86400000);

    if (!ecDayAStr || !ecDayBStr) {
      return {
        limitation_date: formatDate(baseLimit),
        base_limit:      formatDate(baseLimit),
        ec_applied:      false,
        authority:       'ERA 1996 s.111(2)',
        notes: `${timeLimitMonths}-month-less-1-day rule from EDT ${edtStr}: deadline ${formatDate(baseLimit)}.`,
      };
    }

    const dayA = parseDate(ecDayAStr);
    const dayB = parseDate(ecDayBStr);

    if (!dayA || !dayB) return { error: 'Invalid EC date format.' };
    if (dayB < dayA) return { error: 'EC certificate date must be on or after ACAS contact date.' };

    const pauseDays = daysDiff(dayA, dayB);
    const adjusted  = new Date(baseLimit.getTime() + pauseDays * 86400000);

    const floor        = addCalendarMonths(dayB, 1);
    const limitDate    = adjusted >= floor ? adjusted : floor;
    const floorApplied = limitDate.getTime() === floor.getTime() && floor > adjusted;

    return {
      limitation_date: formatDate(limitDate),
      base_limit:      formatDate(baseLimit),
      pause_days:      pauseDays,
      adjusted_limit:  formatDate(adjusted),
      ec_floor:        formatDate(floor),
      floor_applied:   floorApplied,
      ec_applied:      true,
      authority:       'ERA 1996 s.111(2) + s.207B',
      notes: (
        `Base ${formatDate(baseLimit)} + ${pauseDays} EC pause days = ${formatDate(adjusted)}. ` +
        `Floor (1 month after Day B ${ecDayBStr}) = ${formatDate(floor)}. ` +
        `Final = ${formatDate(limitDate)}${floorApplied ? ' (floor applied)' : ''}.`
      ),
    };
  }

  // ── Unified API ───────────────────────────────────────────────────────────
  function computeDeadline(edtStr, timeLimitMonths, ecDayAStr, ecDayBStr) {
    if (wasmModule && wasmModule.compute_deadline_wasm) {
      try {
        const result = wasmModule.compute_deadline_wasm(
          edtStr, timeLimitMonths, 
          ecDayAStr || undefined, 
          ecDayBStr || undefined
        );
        return result;
      } catch (e) {
        console.error("WASM compute_deadline_wasm failed, falling back to JS", e);
      }
    }
    return computeDeadlineJS(edtStr, timeLimitMonths, ecDayAStr, ecDayBStr);
  }

  function calculateStatutoryNotice(serviceMonths, direction) {
    if (wasmModule && wasmModule.calculate_statutory_notice_wasm) {
      try {
        return wasmModule.calculate_statutory_notice_wasm(serviceMonths, direction);
      } catch (e) {
        console.error("WASM calculate_statutory_notice_wasm failed, falling back to JS", e);
      }
    }
    return calculateStatutoryNoticeJS(serviceMonths, direction);
  }

  async function fetchDeadlineRules(apiBase, claimType) {
    claimType = claimType || 'unfair_dismissal';
    const resp = await fetch(`${apiBase}/rules/${claimType}`);
    if (!resp.ok) throw new Error(`Rules API returned HTTP ${resp.status}`);
    const data = await resp.json();

    const key   = `${claimType}.time_limit_months`;
    const rule  = data.rules.find(r => r.rule_key === key);
    if (!rule) throw new Error(`Rule '${key}' not found in API response`);

    return {
      timeLimitMonths: Math.round(rule.value_numeric),
      authorityRef:    rule.authority_ref,
      authorityUrl:    rule.authority_url,
      effectiveFrom:   rule.effective_from,
      effectiveTo:     rule.effective_to,
      lastVerifiedAt:  rule.last_verified_at || null,
    };
  }

  const api = { 
    initWasm, computeDeadline, calculateStatutoryNotice, 
    fetchDeadlineRules, parseDate, formatDate, addCalendarMonths, daysDiff 
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.LawappDeadline = api;
  }

}(typeof globalThis !== 'undefined' ? globalThis : this));
