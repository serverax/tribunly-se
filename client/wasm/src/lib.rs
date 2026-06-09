use wasm_bindgen::prelude::*;
use serde::{Deserialize, Serialize};
use chrono::{NaiveDate, Months, TimeDelta};

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DeadlineResult {
    pub limitation_date: Option<String>,
    pub base_limit: Option<String>,
    pub ec_applied: Option<bool>,
    pub authority: Option<String>,
    pub notes: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pause_days: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adjusted_limit: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ec_floor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub floor_applied: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl DeadlineResult {
    fn err(msg: &str) -> Self {
        DeadlineResult {
            limitation_date: None, base_limit: None, ec_applied: None,
            authority: None, notes: None, pause_days: None, adjusted_limit: None,
            ec_floor: None, floor_applied: None, error: Some(msg.to_string()),
        }
    }
}

fn parse_date(s: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(s, "%Y-%m-%d").ok()
}

fn format_date(d: NaiveDate) -> String {
    d.format("%Y-%m-%d").to_string()
}

pub mod notice;

/// Pure-Rust core (testable without a wasm runtime). The `#[wasm_bindgen]` entry point
/// is a thin serializer around this. FAIL-CLOSED: every error path returns a
/// `DeadlineResult` with `error: Some(..)` — it never panics on bad input.
pub fn compute_deadline(
    edt_str: &str,
    time_limit_months: i32,
    ec_day_a_str: Option<String>,
    ec_day_b_str: Option<String>,
) -> DeadlineResult {
    // Guard: statutory ET time limits are small (3–6 months). Reject non-positive or
    // absurd values instead of casting a negative i32 to a huge u32 (which would panic
    // inside checked_add_months .unwrap()).
    if time_limit_months <= 0 || time_limit_months > 120 {
        return DeadlineResult::err("Invalid time limit (months) — must be between 1 and 120.");
    }

    let edt = match parse_date(edt_str) {
        Some(d) => d,
        None => return DeadlineResult::err("Invalid EDT date format."),
    };

    // Step 1: Base limit (checked — never panic on date overflow).
    let anniversary = match edt.checked_add_months(Months::new(time_limit_months as u32)) {
        Some(d) => d,
        None => return DeadlineResult::err("Date out of range for the given time limit."),
    };
    let base_limit = match anniversary.checked_sub_signed(TimeDelta::days(1)) {
        Some(d) => d,
        None => return DeadlineResult::err("Date out of range computing base limit."),
    };

    let (day_a_str, day_b_str) = match (ec_day_a_str, ec_day_b_str) {
        (Some(a), Some(b)) => (a, b),
        _ => {
            return DeadlineResult {
                limitation_date: Some(format_date(base_limit)),
                base_limit: Some(format_date(base_limit)),
                ec_applied: Some(false),
                authority: Some("ERA 1996 s.111(2)".to_string()),
                notes: Some(format!("{}-month-less-1-day rule from EDT {}: deadline {}.", time_limit_months, edt_str, format_date(base_limit))),
                pause_days: None, adjusted_limit: None, ec_floor: None, floor_applied: None, error: None,
            };
        }
    };

    // Step 2: EC stop-clock (s.207B)
    let day_a = parse_date(&day_a_str);
    let day_b = parse_date(&day_b_str);
    if day_a.is_none() || day_b.is_none() {
        return DeadlineResult::err("Invalid EC date format.");
    }
    let (day_a, day_b) = (day_a.unwrap(), day_b.unwrap());

    if day_b < day_a {
        return DeadlineResult::err("EC certificate date must be on or after ACAS contact date.");
    }

    let pause_days = (day_b - day_a).num_days();
    let adjusted = match base_limit.checked_add_signed(TimeDelta::days(pause_days)) {
        Some(d) => d,
        None => return DeadlineResult::err("Date out of range applying EC pause."),
    };

    // Step 3: Floor (one calendar month after Day B)
    let floor = match day_b.checked_add_months(Months::new(1)) {
        Some(d) => d,
        None => return DeadlineResult::err("Date out of range computing EC floor."),
    };
    let (limit_date, floor_applied) = if adjusted >= floor {
        (adjusted, false)
    } else {
        (floor, true)
    };

    DeadlineResult {
        limitation_date: Some(format_date(limit_date)),
        base_limit: Some(format_date(base_limit)),
        ec_applied: Some(true),
        authority: Some("ERA 1996 s.111(2) + s.207B".to_string()),
        notes: Some(format!("Base {} + {} EC pause days = {}. Floor (1 month after Day B {}) = {}. Final = {}{}.",
            format_date(base_limit), pause_days, format_date(adjusted), day_b_str, format_date(floor), format_date(limit_date),
            if floor_applied { " (floor applied)" } else { "" }
        )),
        pause_days: Some(pause_days),
        adjusted_limit: Some(format_date(adjusted)),
        ec_floor: Some(format_date(floor)),
        floor_applied: Some(floor_applied),
        error: None,
    }
}

#[wasm_bindgen]
pub fn compute_deadline_wasm(
    edt_str: &str,
    time_limit_months: i32,
    ec_day_a_str: Option<String>,
    ec_day_b_str: Option<String>,
) -> JsValue {
    let result = compute_deadline(edt_str, time_limit_months, ec_day_a_str, ec_day_b_str);
    serde_wasm_bindgen::to_value(&result).unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_limit_three_month_less_one_day() {
        // EDT 2026-01-01, 3-month limit, no EC → 2026-03-31 (3 months less 1 day).
        let r = compute_deadline("2026-01-01", 3, None, None);
        assert_eq!(r.error, None);
        assert_eq!(r.base_limit.as_deref(), Some("2026-03-31"));
        assert_eq!(r.ec_applied, Some(false));
    }

    #[test]
    fn ec_pause_extends_limit() {
        // EC stop-clock adds pause days; result must be >= base.
        let r = compute_deadline("2026-01-01", 3, Some("2026-02-01".into()), Some("2026-02-15".into()));
        assert_eq!(r.error, None);
        assert_eq!(r.ec_applied, Some(true));
        assert_eq!(r.pause_days, Some(14));
    }

    // ---- bad input MUST fail closed (return error, NOT panic) ----

    #[test]
    fn negative_months_fails_closed() {
        // Previously panicked: (-3 as u32) -> huge -> checked_add_months None -> unwrap panic.
        let r = compute_deadline("2026-01-01", -3, None, None);
        assert!(r.error.is_some());
        assert_eq!(r.limitation_date, None);
    }

    #[test]
    fn zero_months_fails_closed() {
        let r = compute_deadline("2026-01-01", 0, None, None);
        assert!(r.error.is_some());
    }

    #[test]
    fn extreme_months_fails_closed() {
        let r = compute_deadline("2026-01-01", 1_000_000, None, None);
        assert!(r.error.is_some());
    }

    #[test]
    fn invalid_edt_fails_closed() {
        let r = compute_deadline("not-a-date", 3, None, None);
        assert_eq!(r.error.as_deref(), Some("Invalid EDT date format."));
    }

    #[test]
    fn ec_day_b_before_day_a_fails_closed() {
        let r = compute_deadline("2026-01-01", 3, Some("2026-02-15".into()), Some("2026-02-01".into()));
        assert!(r.error.is_some());
    }

    #[test]
    fn invalid_ec_date_fails_closed() {
        let r = compute_deadline("2026-01-01", 3, Some("bad".into()), Some("2026-02-01".into()));
        assert_eq!(r.error.as_deref(), Some("Invalid EC date format."));
    }
}
