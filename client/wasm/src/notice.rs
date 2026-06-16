use wasm_bindgen::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct NoticeResult {
    pub ok: bool,
    pub statutory_minimum_weeks: u32,
    pub full_years_counted: u32,
    pub notes: Vec<String>,
    pub error: Option<String>,
}

/// Pure-Rust core (testable without a wasm runtime). FAIL-CLOSED: invalid input returns
/// `ok: false` with an `error`, never panics.
pub fn calculate_statutory_notice(service_months: i32, direction: &str) -> NoticeResult {
    if service_months < 0 {
        return NoticeResult {
            ok: false, statutory_minimum_weeks: 0, full_years_counted: 0,
            notes: vec![], error: Some("Service months must be positive.".to_string()),
        };
    }

    if direction != "employee_to_employer" && direction != "employer_to_employee" {
        return NoticeResult {
            ok: false, statutory_minimum_weeks: 0, full_years_counted: 0,
            notes: vec![],
            error: Some("direction must be 'employee_to_employer' or 'employer_to_employee'.".to_string()),
        };
    }

    let mut notes = vec![
        "Continuous service supplied directly; calculator does not assess interruption rules.".to_string(),
        "Returns statutory MINIMUM only  -  contract notice prevails if longer.".to_string(),
    ];

    if direction == "employee_to_employer" {
        // ERA 1996 s.86(2): 1 week fixed minimum once >= 1 month service.
        let weeks = if service_months < 1 { 0 } else { 1 };
        if weeks == 1 { notes.push("ERA 1996 s.86(2): 1 week fixed minimum after 1 month service.".to_string()); }
        return NoticeResult {
            ok: true, statutory_minimum_weeks: weeks, full_years_counted: 0, notes, error: None,
        };
    }

    // employer_to_employee (ERA 1996 s.86(1))
    let (weeks, years) = if service_months < 1 {
        notes.push("Under 1 month service: no statutory minimum notice.".to_string());
        (0u32, 0u32)
    } else if service_months < 24 {
        notes.push("1 month to 2 years service: 1 week statutory minimum.".to_string());
        (1u32, 0u32)
    } else {
        let years = (service_months / 12) as u32;
        let weeks = std::cmp::min(years, 12);
        notes.push(format!("{} years service: {} weeks statutory minimum (capped at 12).", years, weeks));
        (weeks, years)
    };

    NoticeResult { ok: true, statutory_minimum_weeks: weeks, full_years_counted: years, notes, error: None }
}

#[wasm_bindgen]
pub fn calculate_statutory_notice_wasm(service_months: i32, direction: &str) -> JsValue {
    let result = calculate_statutory_notice(service_months, direction);
    serde_wasm_bindgen::to_value(&result).unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn employer_caps_at_12_weeks() {
        // 20 years service → capped at 12 weeks.
        let r = calculate_statutory_notice(20 * 12, "employer_to_employee");
        assert!(r.ok);
        assert_eq!(r.statutory_minimum_weeks, 12);
        assert_eq!(r.full_years_counted, 20);
    }

    #[test]
    fn employer_one_week_band() {
        let r = calculate_statutory_notice(12, "employer_to_employee");
        assert!(r.ok);
        assert_eq!(r.statutory_minimum_weeks, 1);
    }

    #[test]
    fn employee_fixed_one_week() {
        let r = calculate_statutory_notice(60, "employee_to_employer");
        assert!(r.ok);
        assert_eq!(r.statutory_minimum_weeks, 1);
    }

    // ---- bad input MUST fail closed ----

    #[test]
    fn negative_service_fails_closed() {
        let r = calculate_statutory_notice(-5, "employer_to_employee");
        assert!(!r.ok);
        assert!(r.error.is_some());
    }

    #[test]
    fn unknown_direction_fails_closed() {
        let r = calculate_statutory_notice(36, "sideways");
        assert!(!r.ok);
        assert!(r.error.is_some());
    }
}
