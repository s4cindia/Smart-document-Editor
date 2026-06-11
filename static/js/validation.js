/* =========================================================================
   validation.js — CHECK + ANALYTICS toolbar groups, the side panel, and the
   PDF inspector panel.

   Adds SDE.actions for:
     validate, errors, missing, duplicate-rows-check, quality,
     duplicate-finder, statistics, summary, profile, charts, close-panel
   Plus SDE.openPanel(...) and SDE.openPdfPanel(info) (called from app.js).
   ========================================================================= */
(function () {
  let chartInstance = null;

  /* ---------- panel plumbing -------------------------------------------- */
  SDE.openPanel = function ({ title, icon = "fa-layer-group", html }) {
    document.getElementById("panelTitle").textContent = title;
    document.getElementById("panelIcon").className = `fa-solid ${icon}`;
    document.getElementById("panelBody").innerHTML = html;
    document.getElementById("panel").classList.add("open");
  };
  SDE.closePanel = function () {
    document.getElementById("panel").classList.remove("open");
    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
  };
  SDE.actions["close-panel"] = SDE.closePanel;

  /* ---------- tiny render helpers --------------------------------------- */
  const esc = (s) => SDE.esc(s);
  const num = (n) => (n == null ? "—" : Number(n).toLocaleString());

  function metric(label, value, cls = "") {
    return `<div class="metric ${cls}"><div class="label">${esc(label)}</div>
      <div class="value">${value}</div></div>`;
  }
  function metricGrid(cards) {
    return `<div class="metric-grid">${cards.join("")}</div>`;
  }
  function miniTable(headers, rows) {
    if (!rows.length) return `<div class="hint">Nothing to show.</div>`;
    const head = headers.map((h) => `<th>${esc(h)}</th>`).join("");
    const body = rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("");
    return `<table class="mini-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  function scoreColor(score) {
    if (score >= 85) return "#16a34a";
    if (score >= 60) return "#d97706";
    return "#dc2626";
  }
  function scoreRing(score) {
    const c = scoreColor(score);
    return `<div class="score-ring">
      <div class="ring-circle" style="background:${c}">${score}</div>
      <div><div class="num" style="color:${c}">${score}<span style="font-size:14px">/100</span></div>
        <div class="meta">Data quality score</div></div>
    </div>`;
  }
  function gate() {
    if (!SDE.status || !SDE.status.loaded || SDE.status.source === "pdf") {
      SDE.toast("Load a data file first", "warn");
      return false;
    }
    return true;
  }

  /* =======================================================================
     CHECK group
     ===================================================================== */

  /* ----- Validate (full report) ---------------------------------------- */
  SDE.actions["validate"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.post("/api/validate", {});
      renderValidation(d.report);
      const sc = d.report.quality_score;
      SDE.setValidationStatus(`${sc}/100`, scoreColor(sc));
      // highlight error rows in the grid too
      loadErrorHighlights();
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };

  function renderValidation(r) {
    const cards = metricGrid([
      metric("Rows", num(r.total_rows)),
      metric("Columns", num(r.total_columns)),
      metric("Blank column", num(Object.values(r.missing_by_col).reduce((a, b) => a + b, 0)),
        r.issue_count ? "warn" : "good"),
      metric("Blank rows", num(r.blank_rows), r.blank_rows ? "bad" : "good"),
      metric("Duplicate rows", num(r.duplicate_rows), r.duplicate_rows ? "bad" : "good"),
      metric("Total issues", num(r.issue_count), r.issue_count ? "bad" : "good"),
    ]);

    const issueRows = (r.issues || []).map((i) => [
      esc(i.type), esc(i.column),
      `<span class="tag ${i.count ? "amber" : "green"}">${num(i.count)}</span>`,
    ]);
    const fmtRows = Object.entries(r.detected_formats || {}).map(([c, k]) =>
      [esc(c), `<span class="tag green">${esc(k)}</span>`]);

    SDE.openPanel({
      title: "Validation report", icon: "fa-shield-halved",
      html: scoreRing(r.quality_score) + cards +
        `<h4>Issues found</h4>` +
        miniTable(["Type", "Column", "Count"], issueRows) +
        (fmtRows.length ? `<h4>Detected formats</h4>` +
          miniTable(["Column", "Expected"], fmtRows) : "") +
        `<div class="hint" style="margin-top:14px">Use <b>Errors</b> to highlight bad rows in the grid, or <b>Reports</b> to export.</div>`,
    });
  }

  /* ----- Errors (rows failing format checks) --------------------------- */
  SDE.actions["errors"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.get("/api/validate/errors");
      const cols = SDE.columns.slice(0, 4);
      const rows = d.rows.slice(0, 100).map((rec) => [
        `<b>${rec.__id}</b>`,
        ...cols.map((c) => esc(rec[c])),
        `<span class="tag red">${esc(rec.__reason)}</span>`,
      ]);
      SDE.openPanel({
        title: `Errors (${d.count})`, icon: "fa-triangle-exclamation",
        html: (d.count
          ? `<div class="hint" style="margin-bottom:12px">${d.count} row(s) failed format checks. Matching rows are tinted red in the grid.</div>`
          : `<div class="hint">No format errors detected. 🎉</div>`) +
          (rows.length ? miniTable(["#", ...cols, "Reason"], rows) : ""),
      });
      SDE.grid.setErrorRows(d.rows.map((r) => r.__id));
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };

  async function loadErrorHighlights() {
    try {
      const d = await SDE.get("/api/validate/errors");
      SDE.grid.setErrorRows(d.rows.map((r) => r.__id));
    } catch (e) { /* ignore */ }
  }

  /* ----- Missing values ------------------------------------------------- */
  SDE.actions["missing"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.post("/api/validate", {});
      const r = d.report;
      const entries = Object.entries(r.missing_by_col).sort((a, b) => b[1] - a[1]);
      const total = r.total_rows || 1;
      const rows = entries.map(([c, n]) => [
        esc(c),
        `<span class="tag ${n ? "amber" : "green"}">${num(n)}</span>`,
        `${((n / total) * 100).toFixed(1)}%`,
      ]);
      SDE.openPanel({
        title: "Missing values", icon: "fa-circle-question",
        html: metricGrid([
          metric("Total missing", num(entries.reduce((a, [, n]) => a + n, 0)), "warn"),
          metric("Blank rows", num(r.blank_rows), r.blank_rows ? "bad" : "good"),
        ]) + `<h4>Per column</h4>` + miniTable(["Column", "Missing", "% of rows"], rows),
      });
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };

  /* ----- Duplicate rows check (all columns) ----------------------------- */
  SDE.actions["duplicate-rows-check"] = async function () {
    if (!gate()) return;
    await runDuplicates(null, "Duplicate rows");
  };

  /* ----- Duplicate finder — matches on the VISIBLE columns -------------- */
  SDE.actions["duplicate-finder"] = function () {
    if (!gate()) return;
    const all = SDE.columns || [];
    const vis = (SDE.grid.visibleColumns && SDE.grid.visibleColumns()) || [];
    const usingAll = vis.length === 0 || vis.length >= all.length;
    const shown = vis.length ? vis : all;
    const chips = shown.map((c) => `<span class="dupcol-chip">${esc(c)}</span>`).join("");
    SDE.modal({
      title: "Find duplicates", icon: "fa-clone",
      bodyHTML: `<div class="hint" style="margin-bottom:10px">Duplicates are matched using only the columns currently <b>shown</b> in the grid. Use <b>View → Columns…</b> to show just the fields that define a duplicate, then run this.</div>
        <div class="field"><label>Matching on ${shown.length} visible column${shown.length === 1 ? "" : "s"}${usingAll ? " (all columns)" : ""}</label>
          <div class="dupcols">${chips}</div></div>`,
      buttons: [
        { label: "Cancel", onClick: SDE.closeModal },
        { label: "Find duplicates", variant: "primary", onClick: () => {
            SDE.closeModal();
            runDuplicates(usingAll ? null : vis, "Duplicate finder");
          } },
      ],
    });
  };

  async function runDuplicates(columns, title) {
    SDE.busy(true);
    try {
      const d = await SDE.post("/api/duplicates", { columns });
      const res = d.result;
      const cols = (res.columns || SDE.columns).slice(0, 4);
      const rows = (res.rows || []).slice(0, 120).map((rec) => [
        `<span class="tag amber">#${rec.__group}</span>`,
        `<b>${rec.__id}</b>`,
        ...cols.map((c) => esc(rec[c])),
      ]);
      SDE.openPanel({
        title, icon: "fa-clone",
        html: metricGrid([
          metric("Duplicate groups", num(res.group_count), res.group_count ? "warn" : "good"),
          metric("Duplicate rows", num(res.duplicate_rows), res.duplicate_rows ? "bad" : "good"),
        ]) +
          `<div class="hint" style="margin-bottom:10px">Matched on: ${cols.map(esc).join(", ") || "all columns (entire row)"} · each duplicate group is tinted a different colour and grouped together in the grid.</div>` +
          miniTable(["Group", "#", ...cols], rows) +
          (res.duplicate_rows
            ? `<button class="btn danger" style="margin-top:14px;width:100%" id="dropDupBtn">
                 <i class="fa-solid fa-broom"></i> Drop duplicates (keep first)</button>`
            : ""),
      });
      SDE.grid.setDuplicateRows(res.duplicate_ids || [], res.groups || []);
      // Server reordered the rows so each group sits together — reload the grid
      // so the grouped order is visible, then re-apply the group colours.
      if (d.regrouped && SDE.grid.refresh) {
        if (SDE.grid.clearSort) SDE.grid.clearSort();
        SDE.grid.refresh();
        setTimeout(() => SDE.grid.setDuplicateRows(res.duplicate_ids || [], res.groups || []), 150);
      }
      // Rows have been grouped/coloured — enable Save so the user can keep this
      // arrangement, and let them know the export can carry the colours.
      if (res.duplicate_rows && SDE.markDirty) {
        SDE.markDirty();
        SDE.toast("Duplicates grouped & coloured \u2014 use Save to keep this order, "
          + "or Export with the duplicate-highlight option.", "info");
      }
      const drop = document.getElementById("dropDupBtn");
      if (drop) drop.onclick = () => dropDuplicates(res.columns);

      // Remember on what basis duplicates were found, and reveal the info
      // button next to the Check menu so the user can review it any time.
      SDE._dupBasis = {
        columns: res.columns || [],
        allColumns: !columns,            // null columns => matched on all columns
        groups: res.group_count,
        rows: res.duplicate_rows,
        keyColumns: (res.columns && res.columns.length) ? res.columns : (SDE.columns || []),
        sample: (res.rows || []).slice(0, 300),   // grouped rows w/ values, for review
      };
      const infoBtn = document.getElementById("dupInfoBtn");
      if (infoBtn) infoBtn.style.display = "";
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  }

  function dropDuplicates(columns) {
    Swal.fire({
      icon: "warning", title: "Drop duplicate rows?",
      text: "Keeps the first occurrence of each. Undo with Ctrl+Z.",
      showCancelButton: true, confirmButtonText: "Drop", confirmButtonColor: "#dc2626",
    }).then(async (r) => {
      if (!r.isConfirmed) return;
      SDE.busy(true);
      try {
        const d = await SDE.post("/api/duplicates/drop", { columns });
        SDE.applyStatus(d.status);
        SDE.grid.setDuplicateRows([]);
        SDE.grid.refresh();
        SDE.closePanel();
        SDE.toast(`Dropped ${d.removed} duplicate row(s)`, "success");
      } catch (e) { SDE.toast(e.message, "error"); }
      finally { SDE.busy(false); }
    });
  }

  /* ----- Data quality (score-focused view) ------------------------------ */
  SDE.actions["quality"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.post("/api/validate", {});
      const r = d.report;
      const cells = (r.total_rows * Math.max(1, r.total_columns)) || 1;
      const missing = Object.values(r.missing_by_col).reduce((a, b) => a + b, 0);
      const rows = [
        ["Completeness", `${(100 - (missing / cells) * 100).toFixed(1)}%`],
        ["Uniqueness", `${(100 - (r.duplicate_rows / (r.total_rows || 1)) * 100).toFixed(1)}%`],
        ["Non-blank rows", `${(100 - (r.blank_rows / (r.total_rows || 1)) * 100).toFixed(1)}%`],
        ["Format validity", r.issues.some((i) => i.type.startsWith("Invalid"))
          ? `<span class="tag amber">issues</span>` : `<span class="tag green">clean</span>`],
      ].map(([k, v]) => [esc(k), v]);
      SDE.setValidationStatus(`${r.quality_score}/100`, scoreColor(r.quality_score));
      SDE.openPanel({
        title: "Data quality", icon: "fa-gauge-high",
        html: scoreRing(r.quality_score) +
          `<h4>Quality dimensions</h4>` + miniTable(["Dimension", "Score"], rows) +
          `<div class="hint" style="margin-top:14px">Score weights missing values, duplicates and blank rows.</div>`,
      });
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };
  
  /* ----- Summary (overview) -------------------------------------------- */
  SDE.actions["summary"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.get("/api/analytics/overview");
      const o = d.overview;
      const typeRows = Object.entries(o.type_summary || {}).map(([t, n]) =>
        [esc(t), num(n)]);
      SDE.openPanel({
        title: "Data summary", icon: "fa-list-check",
        html: metricGrid([
          metric("Total rows", num(o.total_rows)),
          metric("Total columns", num(o.total_columns)),
          metric("Missing values", num(o.missing_values), o.missing_values ? "warn" : "good"),
          metric("Duplicate rows", num(o.duplicate_rows), o.duplicate_rows ? "bad" : "good"),
          metric("Memory", esc(o.memory)),
        ]) + `<h4>Column types</h4>` + miniTable(["Type", "Columns"], typeRows),
      });
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };

  /* ----- Statistics (numeric describe) --------------------------------- */
  SDE.actions["statistics"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.get("/api/analytics/statistics");
      const rows = d.statistics.map((s) => [
        `<b>${esc(s.column)}</b>`, num(s.count), num(s.min), num(s.max),
        s.mean == null ? "—" : Number(s.mean).toFixed(2),
        s.median == null ? "—" : Number(s.median).toFixed(2),
        s.std == null ? "—" : Number(s.std).toFixed(2),
      ]);
      SDE.openPanel({
        title: "Statistics", icon: "fa-calculator",
        html: rows.length
          ? `<div style="overflow-x:auto">${miniTable(
              ["Column", "Count", "Min", "Max", "Mean", "Median", "Std"], rows)}</div>`
          : `<div class="hint">No numeric columns to summarise.</div>`,
      });
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };

  /* ----- Data profile --------------------------------------------------- */
  SDE.actions["profile"] = async function () {
    if (!gate()) return;
    SDE.busy(true);
    try {
      const d = await SDE.get("/api/analytics/profile");
      const rows = d.profile.map((p) => [
        `<b>${esc(p.column)}</b>`,
        `<span class="tag green">${esc(p.type)}</span>`,
        num(p.unique),
        `${num(p.nulls)} (${p.null_pct}%)`,
        p.top != null ? `${esc(p.top)} ×${num(p.top_count)}`
          : (p.mean != null ? `μ ${Number(p.mean).toFixed(2)}` : "—"),
      ]);
      SDE.openPanel({
        title: "Data profile", icon: "fa-fingerprint",
        html: `<div style="overflow-x:auto">${miniTable(
          ["Column", "Type", "Unique", "Nulls", "Top / Mean"], rows)}</div>`,
      });
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };

  /* ----- Charts (frequency) -------------------------------------------- */
  SDE.actions["charts"] = async function () {
    if (!gate()) return;
    const options = SDE.columns.map((c) =>
      `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    SDE.openPanel({
      title: "Charts", icon: "fa-chart-column",
      html: `<div class="field"><label>Column (frequency)</label>
          <select id="chCol"><option value="">Auto-pick</option>${options}</select></div>
        <canvas id="freqChart" height="220"></canvas>
        <div class="hint" style="margin-top:10px">Top values by frequency.</div>`,
    });
    const sel = document.getElementById("chCol");
    sel.onchange = () => drawChart(sel.value);
    drawChart("");
  };

  async function drawChart(column) {
    try {
      const url = column ? `/api/analytics/chart?column=${encodeURIComponent(column)}`
                         : "/api/analytics/chart";
      const d = await SDE.get(url);
      const c = d.chart;
      const ctx = document.getElementById("freqChart");
      if (!ctx) return;
      if (chartInstance) chartInstance.destroy();
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      chartInstance = new Chart(ctx, {
        type: "bar",
        data: {
          labels: c.labels.map((x) => (x == null ? "(null)" : String(x))),
          datasets: [{
            label: c.column || "frequency",
            data: c.values,
            backgroundColor: "#2563eb",
            borderRadius: 5,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false },
            title: { display: !!c.column, text: c.column ? `Frequency · ${c.column}` : "" } },
          scales: {
            x: { ticks: { color: dark ? "#cbd5e1" : "#475569", maxRotation: 60, minRotation: 0 },
                 grid: { display: false } },
            y: { ticks: { color: dark ? "#cbd5e1" : "#475569" },
                 grid: { color: dark ? "#1e293b" : "#e2e8f0" } },
          },
        },
      });
      if (!c.column && !c.labels.length) {
        SDE.toast("No low-cardinality column to chart — pick one above", "info");
      }
    } catch (e) { SDE.toast(e.message, "error"); }
  }

  /* =======================================================================
     PDF inspector panel (opened from app.js after a PDF is loaded)
     ===================================================================== */
  SDE.openPdfPanel = function (info) {
    const m = info.meta || {};
    const meta = [
      ["Pages", info.page_count],
      ["Title", m.title || "—"],
      ["Author", m.author || "—"],
      ["Producer", m.producer || "—"],
      ["Tables found", (info.tables || []).length],
    ].map(([k, v]) => `<div class="kv"><span class="hint">${esc(k)}:</span> <b>${esc(v)}</b></div>`).join("");

    const tables = (info.tables || []).map((t) => `
      <div class="pdf-table-row">
        <div>
          <div class="nm">Page ${t.page} · Table ${t.index + 1}</div>
          <div class="hint">${t.rows} rows × ${Array.isArray(t.columns) ? t.columns.length : t.columns} cols</div>
        </div>
        <div class="actions">
          <span class="pill-btn" data-pdf-load="${t.page}:${t.index}"><i class="fa-solid fa-table"></i> Load</span>
          <span class="pill-btn" data-pdf-xlsx="${t.page}:${t.index}"><i class="fa-solid fa-file-excel"></i></span>
          <span class="pill-btn" data-pdf-csv="${t.page}:${t.index}"><i class="fa-solid fa-file-csv"></i></span>
        </div>
      </div>`).join("");

    SDE.openPanel({
      title: "PDF inspector", icon: "fa-file-pdf",
      html: `<div style="display:flex;flex-direction:column;gap:5px;margin-bottom:14px">${meta}</div>
        <div class="field"><label>Search text</label>
          <input type="text" id="pdfSearch" placeholder="Find in PDF text…"></div>
        <div id="pdfSearchResults"></div>
        <h4>Extracted tables</h4>
        ${tables || `<div class="hint">No tables detected. Use search to inspect text.</div>`}`,
    });

    const search = document.getElementById("pdfSearch");
    search.addEventListener("keydown", async (e) => {
      if (e.key !== "Enter") return;
      const term = search.value.trim();
      if (!term) return;
      try {
        const d = await SDE.post("/api/pdf/search", { term });
        const box = document.getElementById("pdfSearchResults");
        box.innerHTML = d.count
          ? `<div class="hint" style="margin:8px 0">${d.count} hit(s):</div>` +
            miniTable(["Page", "Context"], d.hits.slice(0, 40).map((h) =>
              [h.page, esc(h.context || h.snippet || "")]))
          : `<div class="hint" style="margin:8px 0">No matches.</div>`;
      } catch (err) { SDE.toast(err.message, "error"); }
    });

    document.getElementById("panelBody").addEventListener("click", async (e) => {
      const load = e.target.closest("[data-pdf-load]");
      const xlsx = e.target.closest("[data-pdf-xlsx]");
      const csv = e.target.closest("[data-pdf-csv]");
      if (load) {
        const [page, index] = load.dataset.pdfLoad.split(":").map(Number);
        SDE.busy(true);
        try {
          const d = await SDE.post("/api/pdf/load-table", { page, index });
          SDE.applyStatus(d.status);
          SDE.grid.reload();
          SDE.toast("Table loaded into grid", "success");
        } catch (err) { SDE.toast(err.message, "error"); }
        finally { SDE.busy(false); }
      } else if (xlsx || csv) {
        const el = xlsx || csv;
        const key = (xlsx ? el.dataset.pdfXlsx : el.dataset.pdfCsv);
        const [page, index] = key.split(":").map(Number);
        const format = xlsx ? "excel" : "csv";
        try {
          const d = await SDE.post("/api/pdf/export-table", { page, index, format });
          SDE.downloadLinkToast(d.url, d.file);
        } catch (err) { SDE.toast(err.message, "error"); }
      }
    });
  };
})();
