/**
 * Case OS UI components - StrengthMeter, LegalBasis, RiskPanel, etc.
 */
(function () {
  "use strict";

  function clear(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function textEl(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  var Components = {
    StrengthMeter: function (container, opts) {
      clear(container);
      opts = opts || {};
      var strength = opts.strength || "uncertain";
      var pct = opts.percent != null ? opts.percent : (window.CaseEngine ? CaseEngine.strengthPercent(strength) : 40);
      var labels = { high: "Strong", medium: "Moderate", low: "Weak", uncertain: "Uncertain" };

      var wrap = textEl("div", "cos-strength-meter");
      var labelRow = textEl("div", "cos-strength-label");
      labelRow.append(
        textEl("span", null, "Claim strength"),
        textEl("strong", null, labels[strength] || "Uncertain")
      );
      var track = textEl("div", "cos-strength-track");
      var fill = textEl("div", "cos-strength-fill " + strength);
      fill.style.width = pct + "%";
      fill.setAttribute("role", "progressbar");
      fill.setAttribute("aria-valuenow", String(pct));
      fill.setAttribute("aria-valuemin", "0");
      fill.setAttribute("aria-valuemax", "100");
      track.appendChild(fill);
      wrap.append(labelRow, track);
      if (opts.note) {
        wrap.appendChild(textEl("p", null, opts.note));
        wrap.lastChild.style.fontSize = "0.82rem";
        wrap.lastChild.style.color = "var(--muted)";
        wrap.lastChild.style.marginTop = "0.5rem";
      }
      container.appendChild(wrap);
    },

    LegalBasis: function (container, citations) {
      clear(container);
      var card = textEl("div", "cos-card");
      card.appendChild(textEl("h3", null, "Legal basis"));
      if (!citations || !citations.length) {
        card.appendChild(textEl("p", null, "No citations returned yet. Run analysis to load grounded sources."));
        container.appendChild(card);
        return;
      }
      var ul = document.createElement("ul");
      ul.style.margin = "0";
      ul.style.paddingLeft = "1.25rem";
      citations.forEach(function (c) {
        var li = document.createElement("li");
        li.style.marginBottom = "0.5rem";
        li.style.fontSize = "0.9rem";
        if (typeof c === "string") {
          li.textContent = c;
        } else {
          var title = c.title || c.source || c.id || "Source";
          if (c.url) {
            var a = document.createElement("a");
            a.href = c.url;
            a.textContent = title;
            a.target = "_blank";
            a.rel = "noopener noreferrer";
            li.appendChild(a);
          } else {
            li.textContent = title;
          }
          if (c.snippet) {
            var sn = textEl("div", null, c.snippet);
            sn.style.color = "var(--muted)";
            sn.style.fontSize = "0.82rem";
            sn.style.marginTop = "0.2rem";
            li.appendChild(sn);
          }
        }
        ul.appendChild(li);
      });
      card.appendChild(ul);
      container.appendChild(card);
    },

    RiskPanel: function (container, risks) {
      clear(container);
      var card = textEl("div", "cos-card");
      card.appendChild(textEl("h3", null, "Risk factors"));
      if (!risks || !risks.length) {
        card.appendChild(textEl("p", null, "No specific risks flagged. Verify deadlines and evidence before filing."));
        container.appendChild(card);
        return;
      }
      risks.forEach(function (r) {
        var row = textEl("div", null);
        row.style.marginBottom = "0.65rem";
        row.style.padding = "0.65rem";
        row.style.background = "var(--warn-bg)";
        row.style.borderRadius = "var(--radius-sm)";
        row.style.fontSize = "0.88rem";
        row.textContent = typeof r === "string" ? r : (r.message || r.text || JSON.stringify(r));
        card.appendChild(row);
      });
      container.appendChild(card);
    },

    DeadlineWidget: function (container, data) {
      clear(container);
      var card = textEl("div", "cos-card");
      card.appendChild(textEl("h3", null, "Deadline tracker"));

      if (!data || !data.deadline_date) {
        card.appendChild(textEl("p", null, "Enter your dismissal date to calculate tribunal deadlines."));
        container.appendChild(card);
        return;
      }

      var urgency = data.urgency || "safe";
      var days = data.days_remaining != null ? data.days_remaining : "—";
      var uClass = window.CaseEngine ? CaseEngine.urgencyClass(urgency) : "safe";

      var summary = textEl("p", null);
      summary.innerHTML = "<strong>" + (data.deadline_date || "") + "</strong> · " + days + " days remaining";
      card.appendChild(summary);

      var bar = textEl("div", "cos-deadline-bar");
      var fill = textEl("div", "cos-deadline-fill " + uClass);
      var pct = 100;
      if (typeof days === "number") {
        pct = Math.max(5, Math.min(100, (days / 90) * 100));
      }
      fill.style.width = pct + "%";
      bar.appendChild(fill);
      card.appendChild(bar);

      if (data.acas_required) {
        var acas = textEl("p", null, "ACAS early conciliation may be required before tribunal.");
        acas.style.fontSize = "0.85rem";
        acas.style.color = "var(--muted)";
        card.appendChild(acas);
      }

      var steps = textEl("div", "cos-deadline-steps");
      ["Dismissal", "ACAS EC", "Tribunal claim"].forEach(function (label, i) {
        var step = textEl("div", "cos-deadline-step" + (i === 0 ? " done" : i === 1 ? " current" : ""), label);
        steps.appendChild(step);
      });
      card.appendChild(steps);
      container.appendChild(card);
    },

    Timeline: function (container, events) {
      clear(container);
      var wrap = textEl("div", "cos-timeline");
      if (!events || !events.length) {
        wrap.appendChild(textEl("p", null, "No timeline events yet."));
        container.appendChild(wrap);
        return;
      }
      events.forEach(function (ev) {
        var item = textEl("div", "cos-timeline-item");
        var date = ev.event_date || ev.date || ev.created_at || "";
        if (date) item.appendChild(textEl("div", "cos-timeline-date", String(date).slice(0, 10)));
        item.appendChild(textEl("strong", null, ev.title || ev.event_type || "Event"));
        if (ev.description || ev.notes) {
          item.appendChild(textEl("p", null, ev.description || ev.notes));
          item.lastChild.style.margin = "0.25rem 0 0";
          item.lastChild.style.fontSize = "0.88rem";
          item.lastChild.style.color = "var(--muted)";
        }
        wrap.appendChild(item);
      });
      container.appendChild(wrap);
    },

    EvidenceBoard: function (container, uploads) {
      clear(container);
      var grid = textEl("div", "cos-evidence-grid");
      var list = (uploads && uploads.uploads) ? uploads.uploads : (Array.isArray(uploads) ? uploads : []);

      if (!list.length) {
        grid.appendChild(textEl("p", null, "No evidence uploaded yet."));
        container.appendChild(grid);
        return;
      }

      list.forEach(function (u) {
        var tile = textEl("div", "cos-evidence-tile");
        tile.appendChild(textEl("strong", null, u.filename || u.original_filename || "Document"));
        var meta = textEl("div", null, (u.doc_type || u.mime_type || "file") + " · " + (u.created_at || "").slice(0, 10));
        meta.style.fontSize = "0.78rem";
        meta.style.color = "var(--muted)";
        meta.style.marginTop = "0.35rem";
        tile.appendChild(meta);
        if (u.tags && u.tags.length) {
          var tags = textEl("div", null, u.tags.join(", "));
          tags.style.fontSize = "0.75rem";
          tags.style.marginTop = "0.25rem";
          tile.appendChild(tags);
        }
        grid.appendChild(tile);
      });
      container.appendChild(grid);
    },

    DocumentBuilder: function (container, bundle) {
      clear(container);
      var card = textEl("div", "cos-card");
      card.appendChild(textEl("h3", null, "Document pipeline"));

      var components = (bundle && bundle.bundle_components) ? bundle.bundle_components : [];
      if (!bundle || !bundle.bundle_generated) {
        card.appendChild(textEl("p", null, "No documents generated yet. Preview or generate your ET1 pack from this case."));
        var types = textEl("ul", null);
        ["ET1 claim form", "Particulars of claim", "Schedule of loss"].forEach(function (t) {
          var li = textEl("li", null, t);
          types.appendChild(li);
        });
        card.appendChild(types);
        container.appendChild(card);
        return;
      }

      components.forEach(function (c) {
        var row = textEl("div", null);
        row.style.display = "flex";
        row.style.justifyContent = "space-between";
        row.style.padding = "0.5rem 0";
        row.style.borderBottom = "1px solid var(--border)";
        row.appendChild(textEl("span", null, c.document_type || c.type || "Document"));
        var status = textEl("span", "cos-pill cos-pill-green", c.status || "ready");
        row.appendChild(status);
        card.appendChild(row);
      });
      container.appendChild(card);
    },

    ModuleStatusBadge: function (container, modules) {
      clear(container);
      if (!modules || !modules.length) return;
      var wrap = textEl("div", null);
      wrap.style.display = "flex";
      wrap.style.flexWrap = "wrap";
      wrap.style.gap = "0.35rem";
      modules.forEach(function (m) {
        var cov = m.display_status
          || ((window.LAWAPP_BETA_SCOPE && LAWAPP_BETA_SCOPE.coverageLabel)
            ? LAWAPP_BETA_SCOPE.coverageLabel(m.status)
            : "Coming soon");
        var cls = cov === "Ready to read" ? "cos-pill-green" : "cos-pill-amber";
        var pill = textEl("span", "cos-pill " + cls, (m.label || m.key) + " · " + cov);
        wrap.appendChild(pill);
      });
      container.appendChild(wrap);
    },
  };

  window.LAWAPP_COMPONENTS = Components;
})();
