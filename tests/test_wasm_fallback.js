const { computeDeadline, addCalendarMonths, parseDate, formatDate } = require('../client/public/js/deadline.js');
const assert = require('assert');

// Since this is Node and we used --target web, the WASM loader (initWasm) will fail gracefully
// and it will use the JS fallback, verifying the fallback logic.

function runTests() {
    // 1. Simple 3-month rule without EC
    let res = computeDeadline('2026-04-01', 3, null, null);
    assert.strictEqual(res.limitation_date, '2026-06-30');
    assert.strictEqual(res.ec_applied, false);
    
    // 2. EC pause (s.207B) but no floor extension needed
    res = computeDeadline('2026-04-01', 3, '2026-05-01', '2026-05-15');
    assert.strictEqual(res.pause_days, 14);
    assert.strictEqual(res.limitation_date, '2026-07-14');
    assert.strictEqual(res.floor_applied, false);
    
    // 3. EC floor extension (s.207B) where 1 month after Day B is the deadline
    res = computeDeadline('2026-04-01', 3, '2026-06-20', '2026-07-05');
    // Base: 2026-06-30
    // Pause: 15 days -> 2026-07-15
    // Floor: 1 month after 2026-07-05 -> 2026-08-05
    assert.strictEqual(res.ec_floor, '2026-08-05');
    assert.strictEqual(res.limitation_date, '2026-08-05');
    assert.strictEqual(res.floor_applied, true);

    // 4. Invalid EC dates
    res = computeDeadline('2026-04-01', 3, '2026-06-20', '2026-06-10'); // Day B < Day A
    assert.ok(res.error.includes('after ACAS contact date'));
    
    // 5. Statutory Notice (Employer to Employee)
    const { calculateStatutoryNotice } = require('../client/public/js/deadline.js');
    
    let n = calculateStatutoryNotice(10, 'employer_to_employee'); // < 2 years
    assert.strictEqual(n.statutory_minimum_weeks, 1);
    
    n = calculateStatutoryNotice(60, 'employer_to_employee'); // 5 years
    assert.strictEqual(n.statutory_minimum_weeks, 5);
    
    n = calculateStatutoryNotice(200, 'employer_to_employee'); // 16 years (capped at 12)
    assert.strictEqual(n.statutory_minimum_weeks, 12);
    
    // 6. Statutory Notice (Employee to Employer)
    n = calculateStatutoryNotice(120, 'employee_to_employer'); // 10 years -> still 1 week
    assert.strictEqual(n.statutory_minimum_weeks, 1);

    console.log("Fallback JS tests passed successfully.");
}

runTests();
