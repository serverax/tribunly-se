/**
 * Controlled-beta employment scope — single source of truth for UI pickers.
 * Must match backend.domains.employment.modules.PRODUCTION_EMPLOYMENT_MODULES.
 */
(function () {
  var MODULES = [
    { key: "unfair_dismissal", label: "Unfair dismissal" },
    { key: "unpaid_wages", label: "Unpaid wages / unlawful deduction" },
    { key: "wrongful_dismissal", label: "Wrongful dismissal / notice pay" },
    { key: "redundancy", label: "Redundancy rights and pay" },
    { key: "flexible_working", label: "Flexible working" },
    { key: "holiday_pay", label: "Holiday pay and annual leave" },
    { key: "working_time", label: "Working time and rest breaks" },
    { key: "part_time_workers", label: "Part-time worker rights" },
    { key: "fixed_term_workers", label: "Fixed-term worker rights" },
    { key: "agency_workers", label: "Agency worker rights" },
    { key: "employment_contracts", label: "Employment contracts / written particulars" },
  ];

  var PARTIAL_HIDDEN = [
    "constructive_dismissal", "discrimination", "pregnancy_maternity_discrimination",
    "equal_pay", "whistleblowing", "health_and_safety", "trade_union_rights",
    "maternity_rights", "paternity_rights", "parental_leave", "shared_parental_leave",
    "national_minimum_wage", "tupe",
  ];

  function populateSelect(selectEl, opts) {
    if (!selectEl) return;
    var includeBlank = opts && opts.includeBlank;
    var blankLabel = (opts && opts.blankLabel) || "Not sure / skip";
    while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
    if (includeBlank) {
      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = blankLabel;
      selectEl.appendChild(blank);
    }
    MODULES.forEach(function (m) {
      var opt = document.createElement("option");
      opt.value = m.key;
      opt.textContent = m.label;
      selectEl.appendChild(opt);
    });
  }

  function populateRadioGroup(containerEl, name, defaultKey) {
    if (!containerEl) return;
    while (containerEl.firstChild) containerEl.removeChild(containerEl.firstChild);
    MODULES.forEach(function (m, i) {
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "radio";
      input.name = name;
      input.value = m.key;
      if (m.key === defaultKey || (!defaultKey && i === 0)) input.checked = true;
      var strong = document.createElement("strong");
      strong.textContent = m.label;
      label.appendChild(input);
      label.appendChild(document.createTextNode(" "));
      label.appendChild(strong);
      containerEl.appendChild(label);
    });
  }

  window.LAWAPP_BETA_SCOPE = {
    modules: MODULES,
    partialHidden: PARTIAL_HIDDEN,
    moduleKeys: function () { return MODULES.map(function (m) { return m.key; }); },
    populateSelect: populateSelect,
    populateRadioGroup: populateRadioGroup,
    betaNotice: "Controlled beta — 11 employment topics (England & Wales). Not full UK employment law coverage.",
  };
})();
