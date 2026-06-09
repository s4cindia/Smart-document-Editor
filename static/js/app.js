/* =========================================================================
   Smart Document Editor & Validator — core application logic
   Shared namespace: window.SDE
   ========================================================================= */
window.SDE = window.SDE || {};
SDE.columns = [];          // current data column names
SDE.columnDefs = [];       // AG Grid column defs from server
SDE.actions = SDE.actions || {};   // action handlers (extended by other files)

/* ---------- HTTP helpers ------------------------------------------------ */
SDE.api = async function (path, opts = {}) {
  const res = await fetch(path, opts);
  let data;
  try { data = await res.json(); } catch { data = { ok: false, error: "Bad response" }; }
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
};
SDE.post = async function (path, body) {
  const data = await SDE.api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  // Mark "unsaved changes" whenever a data-mutating call succeeds
  // (but not for preview-only transform calls).
  const mutates = /\/api\/(data\/(cell|add-row|delete-rows|duplicate-rows|undo|redo)|transform\/|duplicates\/drop)/;
  if (mutates.test(path) && !(body && body.preview)) SDE.markDirty();
  return data;
};
SDE.get = (path) => SDE.api(path);

/* ---------- Save state (dirty/clean indicator) -------------------------- */
SDE._dirty = false;
SDE.updateSaveUI = function () {
  const badge = document.getElementById("saveState");
  const btn = document.getElementById("saveBtn");
  if (badge) {
    badge.dataset.dirty = SDE._dirty ? "true" : "false";
    badge.innerHTML = SDE._dirty
      ? '<i class="fa-solid fa-circle"></i> Unsaved changes'
      : '<i class="fa-solid fa-circle-check"></i> Saved';
  }
  if (btn) btn.disabled = !SDE._dirty;
};
SDE.markDirty = function () { SDE._dirty = true; SDE.updateSaveUI(); };
SDE.markClean = function () { SDE._dirty = false; SDE.updateSaveUI(); };

/* ---------- Notifications ----------------------------------------------- */
SDE.toast = function (msg, type = "info") {
  const colors = {
    info: "#2563eb", success: "#16a34a", error: "#dc2626", warn: "#d97706",
  };
  if (typeof Toastify === "undefined") { console.log("[toast]", type, msg); return; }
  Toastify({
    text: msg, duration: 3200, gravity: "bottom", position: "right",
    style: { background: colors[type] || colors.info, borderRadius: "9px",
      boxShadow: "0 8px 30px rgba(0,0,0,.18)", fontFamily: "Plus Jakarta Sans" },
  }).showToast();
};
SDE.busy = function (on) { document.getElementById("busy").classList.toggle("show", !!on); };

/* ---------- Modal ------------------------------------------------------- */
SDE.modal = function ({ title, icon = "fa-sliders", bodyHTML, buttons = [], wide = false }) {
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalIcon").className = `fa-solid ${icon}`;
  document.getElementById("modalBody").innerHTML = bodyHTML;
  document.getElementById("modal").classList.toggle("wide", wide);
  const foot = document.getElementById("modalFoot");
  foot.innerHTML = "";
  buttons.forEach((b) => {
    const el = document.createElement("button");
    el.className = `btn ${b.variant || ""}`;
    el.innerHTML = b.label;
    el.onclick = () => b.onClick(el);
    foot.appendChild(el);
  });
  document.getElementById("modalOverlay").classList.add("open");
};
SDE.closeModal = function () {
  document.getElementById("modalOverlay").classList.remove("open");
};

/* ---------- Column multiselect builder ---------------------------------- */
SDE.columnSelectHTML = function (id, { multiple = true, includeAll = false } = {}) {
  const opts = SDE.columns.map((c) => `<option value="${SDE.esc(c)}">${SDE.esc(c)}</option>`).join("");
  const all = includeAll ? `<option value="">— all columns —</option>` : "";
  return `<select id="${id}" ${multiple ? "multiple" : ""}>${all}${opts}</select>`;
};
SDE.getSelected = function (id) {
  const el = document.getElementById(id);
  if (!el) return [];
  return Array.from(el.selectedOptions).map((o) => o.value).filter((v) => v !== "");
};
SDE.esc = function (s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
};

/* ---------- Status / header / footer ------------------------------------ */
SDE.applyStatus = function (st) {
  SDE.status = st;
  const chip = document.getElementById("fileChipName");
  chip.textContent = st.file;
  document.getElementById("fileChip").title = st.file;
  document.getElementById("sbFile").textContent = st.loaded ? st.file : "—";
  document.getElementById("sbSize").textContent = st.size || "—";
  document.getElementById("sbRows").textContent = (st.rows || 0).toLocaleString();
  document.getElementById("sbCols").textContent = st.cols || 0;
  const undoBtn = document.getElementById("undoBtn");
  const redoBtn = document.getElementById("redoBtn");
  if (undoBtn) undoBtn.disabled = !st.can_undo;
  if (redoBtn) redoBtn.disabled = !st.can_redo;
  const dot = document.getElementById("statusDot");
  dot.classList.toggle("is-ready", !!st.loaded);
  document.getElementById("statusDotText").textContent = st.loaded ? "Ready" : "Idle";
  document.getElementById("emptyState").style.display =
    (st.loaded && st.source !== "pdf") ? "none" : "flex";
};
SDE.refreshStatus = async function () {
  try { const d = await SDE.get("/api/status"); SDE.applyStatus(d.status); }
  catch (e) { /* ignore */ }
};
SDE.setSelectedCount = function (n) {
  document.getElementById("sbSelected").textContent = n;
};
SDE.setFilteredCount = function (n) {
  document.getElementById("sbFiltered").textContent = (n || 0).toLocaleString();
};
SDE.setValidationStatus = function (text, cls) {
  const el = document.getElementById("sbValidation");
  el.innerHTML = `<i class="fa-solid fa-shield-halved"></i> ${text}`;
  el.style.color = cls || "";
};

/* ---------- Theme ------------------------------------------------------- */
SDE.toggleTheme = function () {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("sde-theme", next);
  document.querySelector("#themeToggle i").className =
    next === "dark" ? "fa-solid fa-sun" : "fa-solid fa-moon";
  if (SDE.grid && SDE.grid.applyTheme) SDE.grid.applyTheme(next);
};

/* =========================================================================
   FILE OPENING
   ========================================================================= */
SDE.actions["open-file"] = () => document.getElementById("fileInput").click();

SDE.handleUpload = async function (file) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", window.SDE_PAGE_MODE || "full");
  SDE.busy(true);
  try {
    const d = await SDE.api("/api/files/open", { method: "POST", body: fd });
    SDE.afterOpen(d);
  } catch (e) {
    SDE.fileOpenError(file && file.name, e.message);
  }
  finally { SDE.busy(false); }
};

// Pop-up shown when a file (e.g. a malformed CSV) cannot be opened.
SDE.fileOpenError = function (name, message) {
  const detail = message || "The file could not be read.";
  if (typeof Swal !== "undefined") {
    Swal.fire({
      icon: "error",
      title: "Couldn't open this file",
      html: `<div style="text-align:left">`
        + (name ? `<p style="margin:0 0 8px"><b>${SDE.esc(name)}</b></p>` : "")
        + `<p style="margin:0;color:#475569">${SDE.esc(detail)}</p>`
        + `<p style="margin:10px 0 0;color:#64748b;font-size:13px">`
        + `Check that it's a valid, non-empty CSV/Excel file and try again.</p></div>`,
      confirmButtonText: "OK", confirmButtonColor: "#4f46e5",
    });
  } else {
    SDE.toast(detail, "error");
  }
};

SDE.afterOpen = function (d) {
  if (d.needs_sheet) { SDE.pickSheet(d.path, d.sheets, d.name); return; }
  if (d.pdf) { SDE.applyStatus(d.status); SDE.openPdfPanel(d.pdf_info); SDE.toast("PDF loaded", "success"); return; }
  SDE.applyStatus(d.status);
  SDE.grid.reload();
  SDE.setValidationStatus("Not validated");
  SDE.markClean();
  SDE.toast("File loaded", "success");
  if (window.SDE_PAGE_MODE === "delivery") SDE.checkWcag();
};

/* Placeholder 3: flag rows whose WCAG name doesn't match wcag_tags.txt for
   their WCAG Ref (empty or mismatched). Colours those rows live in the grid,
   and—when a WCAG cell was just edited—pops up if that row is still incomplete. */
SDE.checkWcag = async function (editedId, rowData) {
  if (window.SDE_PAGE_MODE !== "delivery" || !SDE.grid || !SDE.grid.setWcagFlagRows) return;
  try {
    const d = await SDE.post("/api/data/validate-wcag", {});
    const ids = d.active ? (d.ids || []) : [];
    SDE.grid.setWcagFlagRows(ids);
    // After a WCAG edit, if any row still has missing/mismatched WCAG values,
    // pop up the specific errors so the user can fix them.
    if (editedId != null && ids.length) {
      const issues = d.issues || [];
      const lines = issues.slice(0, 12).map((it) =>
        `<tr><td style="font-weight:700;white-space:nowrap">${SDE.esc(String(it.ref))}</td>
          <td>${(it.problems || []).map((p) => SDE.esc(p)).join("; ")}</td></tr>`).join("");
      const more = issues.length > 12 ? `<div class="hint">…and ${issues.length - 12} more.</div>` : "";
      SDE.modal({
        title: "WCAG mismatch with tag file", icon: "fa-triangle-exclamation",
        bodyHTML: `<div class="hint"><b>${ids.length}</b> row(s) don't match
          <code>wcag_tags.txt</code> on WCAG Ref, WCAG name, or WCAG Ver
          (highlighted in violet):</div>
          <div style="max-height:300px;overflow:auto;margin-top:8px">
          <table class="mini-table"><tr><th>WCAG Ref</th><th>Problem</th></tr>${lines}</table></div>${more}`,
        buttons: [{ label: "OK", variant: "primary", onClick: SDE.closeModal }],
      });
    }
  } catch (e) { /* non-fatal */ }
};

SDE.pickSheet = function (path, sheets, name) {
  const opts = sheets.map((s) => `<option value="${SDE.esc(s)}">${SDE.esc(s)}</option>`).join("");
  SDE.modal({
    title: "Select a sheet", icon: "fa-layer-group",
    bodyHTML: `<div class="field"><label>Workbook: ${SDE.esc(name)}</label>
      <select id="sheetSel">${opts}</select></div>`,
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      { label: "Load sheet", variant: "primary", onClick: async () => {
        const sheet = document.getElementById("sheetSel").value;
        SDE.closeModal(); SDE.busy(true);
        try {
          const d = await SDE.post("/api/files/load-sheet", { path, sheet, mode: window.SDE_PAGE_MODE || "full" });
          SDE.applyStatus(d.status); SDE.grid.reload();
          SDE.setValidationStatus("Not validated");
          SDE.markClean();
          SDE.toast(`Loaded sheet "${sheet}"`, "success");
        } catch (e) { SDE.toast(e.message, "error"); }
        finally { SDE.busy(false); }
      } },
    ],
  });
};

SDE.actions["open-folder"] = async function () {
  const { value: folder } = await Swal.fire({
    title: "Open folder", input: "text",
    inputPlaceholder: "C:\\Users\\me\\Documents  or  /home/me/data",
    showCancelButton: true, confirmButtonText: "List files",
    confirmButtonColor: "#2563eb",
  });
  if (!folder) return;
  try {
    const d = await SDE.post("/api/files/folder", { folder });
    if (!d.items.length) { SDE.toast("No supported files found", "warn"); return; }
    SDE.fileListModal("Folder contents", d.items);
  } catch (e) { SDE.toast(e.message, "error"); }
};

SDE.actions["recent"] = async function () {
  const d = await SDE.get("/api/files/recent");
  if (!d.recent.length) { SDE.toast("No recent files yet", "info"); return; }
  const fmtTs = (ts) => {
    if (!ts) return "";
    try { return new Date(ts * 1000).toLocaleString(); } catch (e) { return ""; }
  };
  const items = d.recent.map((r) => {
    const when = fmtTs(r.ts);
    const parts = [];
    if (r.sheet) parts.push(`sheet: ${r.sheet}`);
    if (when) parts.push(`Opened ${when}`);
    return { path: r.path, name: r.name, ext: "", size: parts.join("  \u00b7  ") };
  });
  SDE.fileListModal("Recent files", items);
};

/* ----- Clear current file and open the next one ------------------------- */
SDE.actions["close-file"] = function () {
  const proceed = async () => {
    SDE.busy(true);
    try {
      const d = await SDE.post("/api/files/close", {});
      SDE.applyStatus(d.status);            // returns to the open screen
      SDE.columns = [];
      SDE._dupBasis = null;
      const ib = document.getElementById("dupInfoBtn");
      if (ib) ib.style.display = "none";
      if (SDE.markClean) SDE.markClean();
      if (SDE.grid && SDE.grid.reload) { try { await SDE.grid.reload(); } catch (e) {} }
      SDE.toast("File cleared \u2014 choose the next file to open.", "success");
      const fi = document.getElementById("fileInput");
      if (fi) fi.click();                   // immediately offer to open the next file
    } catch (e) {
      SDE.toast(e.message, "error");
    } finally {
      SDE.busy(false);
    }
  };
  if (SDE._dirty) {
    SDE.modal({
      title: "Clear current file?", icon: "fa-circle-xmark",
      bodyHTML: `<div class="hint">You have unsaved changes. Clearing this file will discard them and let you open the next file. Continue?</div>`,
      buttons: [
        { label: "Cancel", onClick: SDE.closeModal },
        { label: "Discard & open next", variant: "primary",
          onClick: () => { SDE.closeModal(); proceed(); } },
      ],
    });
  } else {
    proceed();
  }
};

/* ----- Downloads: re-download previously exported files ----------------- */
SDE.actions["downloads"] = async function () {
  let d;
  try { d = await SDE.get("/api/files/downloads"); }
  catch (e) { SDE.toast(e.message, "error"); return; }
  const list = (d && d.downloads) || [];
  if (!list.length) { SDE.toast("No downloads yet — export a file first.", "info"); return; }
  const fmt = (ts) => { try { return new Date(ts * 1000).toLocaleString(); } catch (e) { return ""; } };
  const kb = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB");
  const rows = list.map((it) => `
    <div class="list-item" style="cursor:default">
      <i class="fa-solid ${SDE.fileIcon(it.name)}"></i>
      <span class="nm">${SDE.esc(it.name)}</span>
      <span class="meta">${SDE.esc(fmt(it.ts))}  \u00b7  ${kb(it.size)}</span>
      <a class="btn-mini" href="${SDE.esc(it.url)}" download
         style="margin-left:auto;text-decoration:none"><i class="fa-solid fa-download"></i> Download</a>
    </div>`).join("");
  SDE.modal({
    title: "Downloads", icon: "fa-download",
    bodyHTML: `<div class="hint" style="margin-bottom:10px">Files you have exported, newest first. Click <b>Download</b> to get one again.</div>${rows}`,
    buttons: [{ label: "Close", onClick: SDE.closeModal }],
  });
};

/* ----- Duplicate basis: explain what defined the last duplicate check --- */
SDE.actions["duplicate-info"] = function () {
  const b = SDE._dupBasis;
  if (!b) {
    SDE.toast("Run \u201cCheck duplicate rows\u201d or \u201cFind duplicates\u201d first.", "info");
    return;
  }
  const cols = (b.columns && b.columns.length)
    ? b.columns.map((c) => `<span class="chip">${SDE.esc(c)}</span>`).join(" ")
    : "<i>all columns</i>";
  const scope = b.allColumns ? "every column in the data" : "the columns currently shown in the grid";

  // Build a per-group table of the actual key-column values so the user can
  // verify the grouping is correct (rows in a group should match on these).
  let valuesHTML = "";
  const keyCols = (b.keyColumns && b.keyColumns.length) ? b.keyColumns.slice(0, 6) : [];
  const sample = b.sample || [];
  if (sample.length && keyCols.length) {
    const header = `<tr><th>Group</th><th>Row</th>${keyCols.map((c) => `<th>${SDE.esc(c)}</th>`).join("")}</tr>`;
    let lastGroup = null;
    const body = sample.map((rec) => {
      const g = rec.__group;
      const groupCell = (g !== lastGroup)
        ? `<td><span class="tag amber">#${SDE.esc(g)}</span></td>` : "<td></td>";
      lastGroup = g;
      const cells = keyCols.map((c) => `<td>${SDE.esc(rec[c] == null ? "" : rec[c])}</td>`).join("");
      return `<tr>${groupCell}<td>${SDE.esc(rec.__id)}</td>${cells}</tr>`;
    }).join("");
    valuesHTML = `<h4 style="margin:14px 0 6px">Key-column values per group</h4>
      <div class="hint" style="margin-bottom:6px">Rows sharing a group number should have identical values in these column(s). ${b.sample.length >= 300 ? "Showing the first 300 rows." : ""}</div>
      <div style="max-height:340px;overflow:auto"><table class="mini-table">${header}${body}</table></div>`;
  }

  SDE.modal({
    title: "What defines a duplicate", icon: "fa-circle-info",
    bodyHTML: `<div class="hint" style="margin-bottom:10px">Two rows were treated as duplicates when they matched on ${scope}:</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px">${cols}</div>
      ${b.groups != null ? `<div class="hint" style="margin-top:12px">${b.rows} row(s) in ${b.groups} group(s) were found and grouped together.</div>` : ""}
      ${valuesHTML}`,
    buttons: [{ label: "Close", onClick: SDE.closeModal }],
  });
};

SDE.fileListModal = function (title, items) {
  const rows = items.map((it) => `
    <div class="list-item" data-path="${SDE.esc(it.path)}">
      <i class="fa-solid ${SDE.fileIcon(it.ext || it.path)}"></i>
      <span class="nm">${SDE.esc(it.name)}</span>
      <span class="meta">${SDE.esc(it.size || "")}</span>
    </div>`).join("");
  SDE.modal({
    title, icon: "fa-folder-open", bodyHTML: rows,
    buttons: [{ label: "Close", onClick: SDE.closeModal }],
  });
  document.querySelectorAll("#modalBody .list-item").forEach((el) => {
    el.onclick = async () => {
      SDE.closeModal(); SDE.busy(true);
      try { SDE.afterOpen(await SDE.post("/api/files/open-path", { path: el.dataset.path, mode: window.SDE_PAGE_MODE || "full" })); }
      catch (e) { SDE.fileOpenError(el.dataset.name || el.dataset.path, e.message); }
      finally { SDE.busy(false); }
    };
  });
};

SDE.fileIcon = function (s) {
  s = (s || "").toLowerCase();
  if (s.includes("xls")) return "fa-file-excel";
  if (s.includes("csv") || s.includes("tsv")) return "fa-file-csv";
  if (s.includes("pdf")) return "fa-file-pdf";
  return "fa-file";
};

/* =========================================================================
   TRANSFORM / BULK EDIT
   ========================================================================= */
SDE.runTransform = async function (op, params, applyLabel = "Apply") {
  SDE.busy(true);
  try {
    const d = await SDE.post(`/api/transform/${op}`, params);
    SDE.applyStatus(d.status); SDE.grid.reload();
    SDE.toast(`${applyLabel}: ${d.description}`, "success");
  } catch (e) { SDE.toast(e.message, "error"); }
  finally { SDE.busy(false); }
};

// builds the standard scope + column picker used by most transforms
SDE.transformControls = function (opts = {}) {
  return `
    <div class="field">
      <label>Apply to</label>
      <div class="seg" id="scopeSeg">
        <button class="active" data-scope="all">All rows</button>
        <button data-scope="selected">Selected rows</button>
      </div>
    </div>
    <div class="field">
      <label>Columns ${opts.colHint || "(none = all)"}</label>
      ${SDE.columnSelectHTML("tfCols", { multiple: true })}
      <div class="hint">Ctrl/Cmd-click to choose multiple. Leave empty for all.</div>
    </div>`;
};
SDE.readScope = function () {
  const active = document.querySelector("#scopeSeg .active");
  return active ? active.dataset.scope : "all";
};
SDE.wireScopeSeg = function () {
  document.querySelectorAll("#scopeSeg button").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll("#scopeSeg button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
    };
  });
};
SDE.scopeIds = function () {
  return SDE.readScope() === "selected" ? SDE.grid.selectedIds() : null;
};

// Simple text-input transforms (replace, regex, append, prepend, null replace)
SDE.openTextTransform = function (cfg) {
  SDE.modal({
    title: cfg.title, icon: cfg.icon || "fa-wand-magic-sparkles",
    bodyHTML: cfg.fields + SDE.transformControls(cfg),
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      cfg.preview ? { label: "Preview", onClick: () => cfg.onPreview() } : null,
      { label: "Apply", variant: "primary", onClick: () => cfg.onApply() },
    ].filter(Boolean),
  });
  SDE.wireScopeSeg();
};

SDE.actions["replace"] = function () {
  SDE.openTextTransform({
    title: "Find & Replace", icon: "fa-right-left", preview: true,
    fields: `<div class="row-2">
        <div class="field"><label>Find</label><input type="text" id="tfFind"></div>
        <div class="field"><label>Replace with</label><input type="text" id="tfRepl"></div>
      </div>`,
    onPreview: () => SDE.previewTransform("replace", () => ({
      find: val("tfFind"), replace: val("tfRepl"), columns: SDE.getSelected("tfCols"),
      scope: SDE.readScope(), ids: SDE.scopeIds() })),
    onApply: () => { SDE.closeModal(); SDE.runTransform("replace", {
      find: val("tfFind"), replace: val("tfRepl"), columns: SDE.getSelected("tfCols"),
      scope: SDE.readScope(), ids: SDE.scopeIds() }); },
  });
};

SDE.actions["regex-replace"] = function () {
  SDE.openTextTransform({
    title: "Regex Replace", icon: "fa-asterisk", preview: true,
    fields: `<div class="row-2">
        <div class="field"><label>Pattern (regex)</label><input type="text" id="tfPat" placeholder="\\d+"></div>
        <div class="field"><label>Replace with</label><input type="text" id="tfRepl" placeholder="#"></div>
      </div>`,
    onPreview: () => SDE.previewTransform("regex_replace", () => ({
      pattern: val("tfPat"), replace: val("tfRepl"), columns: SDE.getSelected("tfCols"),
      scope: SDE.readScope(), ids: SDE.scopeIds() })),
    onApply: () => { SDE.closeModal(); SDE.runTransform("regex_replace", {
      pattern: val("tfPat"), replace: val("tfRepl"), columns: SDE.getSelected("tfCols"),
      scope: SDE.readScope(), ids: SDE.scopeIds() }); },
  });
};

// One-click case / trim / clean transforms (with a small confirm modal for scope)
["trim", "upper", "lower", "proper", "remove-special"].forEach((act) => {
  const map = { trim: ["trim", "Trim Spaces", "fa-scissors"],
    upper: ["upper", "Upper Case", "fa-arrow-up-a-z"],
    lower: ["lower", "Lower Case", "fa-arrow-down-a-z"],
    proper: ["proper", "Proper Case", "fa-font"],
    "remove-special": ["remove_special", "Remove Special Characters", "fa-eraser"] };
  SDE.actions[act] = function () {
    const [op, title, icon] = map[act];
    SDE.modal({
      title, icon, bodyHTML: SDE.transformControls({}),
      buttons: [
        { label: "Cancel", onClick: SDE.closeModal },
        { label: "Apply", variant: "primary", onClick: () => {
          SDE.closeModal();
          SDE.runTransform(op, { columns: SDE.getSelected("tfCols"),
            scope: SDE.readScope(), ids: SDE.scopeIds() });
        } },
      ],
    });
    SDE.wireScopeSeg();
  };
});

SDE.actions["merge"] = function () {
  SDE.modal({
    title: "Merge Columns", icon: "fa-object-group",
    bodyHTML: `
      <div class="field"><label>Columns to merge (in order)</label>
        ${SDE.columnSelectHTML("mgCols", { multiple: true })}</div>
      <div class="row-2">
        <div class="field"><label>New column name</label><input type="text" id="mgTarget" value="merged"></div>
        <div class="field"><label>Separator</label><input type="text" id="mgSep" value=" "></div>
      </div>`,
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      { label: "Merge", variant: "primary", onClick: () => {
        SDE.closeModal();
        SDE.runTransform("merge", { columns: SDE.getSelected("mgCols"),
          target: val("mgTarget") || "merged", separator: val("mgSep") });
      } },
    ],
  });
};

SDE.actions["split"] = function () {
  SDE.modal({
    title: "Split Column", icon: "fa-object-ungroup",
    bodyHTML: `
      <div class="field"><label>Column to split</label>
        ${SDE.columnSelectHTML("spCol", { multiple: false })}</div>
      <div class="field"><label>Separator</label>
        <input type="text" id="spSep" value=","></div>`,
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      { label: "Split", variant: "primary", onClick: () => {
        const col = document.getElementById("spCol").value;
        SDE.closeModal();
        SDE.runTransform("split", { column: col, separator: val("spSep") || "," });
      } },
    ],
  });
};

SDE.previewTransform = async function (op, paramsFn) {
  try {
    const d = await SDE.post(`/api/transform/${op}`, { ...paramsFn(), preview: true });
    const p = d.preview;
    const cols = p.columns;
    const head = `<tr><th>#</th>${cols.map((c) => `<th>${SDE.esc(c)}</th>`).join("")}</tr>`;
    const rows = p.before.map((b, i) => {
      const a = p.after[i] || {};
      const cells = cols.map((c) =>
        `<td>${SDE.esc(b[c])} <span class="arrow">→</span> ${SDE.esc(a[c])}</td>`).join("");
      return `<tr><td>${b.__id}</td>${cells}</tr>`;
    }).join("");
    const html = `<div style="overflow:auto"><table class="preview-tbl"><thead>${head}</thead>
      <tbody>${rows}</tbody></table></div>
      <div class="hint" style="margin-top:10px">Showing up to 8 affected rows.</div>`;
    document.getElementById("modalBody").insertAdjacentHTML("beforeend",
      `<div id="previewBox" style="margin-top:14px;border-top:1px solid var(--border);padding-top:12px">${html}</div>`);
    const old = document.getElementById("previewBoxPrev");
    if (old) old.remove();
    document.getElementById("previewBox").id = "previewBoxPrev";
  } catch (e) { SDE.toast(e.message, "error"); }
};

/* Commit any in-progress grid edit and wait for pending cell-saves to finish.
   Ensures every export/report/summary reflects the latest edits. */
SDE.commitEdits = async function () {
  if (!SDE.grid) return;
  if (SDE.grid.stopEditing) SDE.grid.stopEditing();
  if (SDE.grid.flush) await SDE.grid.flush();
};

/* Explicit Save: commit the active edit, flush pending saves, mark clean.
   Edits already persist to the server as you make them; Save guarantees the
   in-progress edit is committed so the next download is fully up to date. */
SDE.actions["save"] = async function () {
  if (!SDE.status || !SDE.status.loaded) { SDE.toast("Nothing to save yet", "info"); return; }
  SDE.busy(true);
  try {
    await SDE.commitEdits();
    await SDE.refreshStatus();
    SDE.markClean();
    SDE.toast("All changes saved — downloads will be up to date", "success");
  } catch (e) { SDE.toast(e.message, "error"); }
  finally { SDE.busy(false); }
};

/* =========================================================================
   EXPORT + REPORTS
   ========================================================================= */
["csv", "pdf", "json"].forEach((fmt) => {
  SDE.actions[`export-${fmt}`] = async function () {
    if (!SDE.requireData()) return;
    SDE.busy(true);
    try {
      await SDE.commitEdits();
      const d = await SDE.post(`/api/export/${fmt}`, {});
      SDE.toast(`Exported ${d.file}`, "success");
      SDE.downloadLinkToast(d.url, d.file, { rows: d.rows, cols: d.cols });
    } catch (e) { SDE.toast(e.message, "error"); }
    finally { SDE.busy(false); }
  };
});

// Excel offers optional highlights: yellow Summary cells and/or blue blanks.
async function doExcelExport(opts) {
  opts = opts || {};
  SDE.busy(true);
  try {
    await SDE.commitEdits();
    const d = await SDE.post("/api/export/excel", {
      highlight_summary: !!opts.summary,
      highlight_blanks: !!opts.blanks,
      highlight_dups: !!opts.dups,
    });
    SDE.toast(`Exported ${d.file}`, "success");
    SDE.downloadLinkToast(d.url, d.file, { rows: d.rows, cols: d.cols });
  } catch (e) { SDE.toast(e.message, "error"); }
  finally { SDE.busy(false); }
}

// ---- merge mode: merge multiple axe workbooks, load result into the grid ----
SDE.actions["merge-files"] = function () {
  document.getElementById("mergeInput").click();
};

SDE.handleMerge = async function (fileList) {
  const fd = new FormData();
  Array.prototype.forEach.call(fileList, (f) => fd.append("files", f));
  SDE.busy(true);
  try {
    const d = await SDE.api("/api/files/merge-open", { method: "POST", body: fd });
    SDE.afterOpen(d);
    const s = d.stats || {};
    SDE.toast(`Merged ${s.files_processed}/${s.files_total} files · `
      + `${s.duplicates_removed} duplicate(s) removed · ${s.final_rows} rows`, "success");
    if (d.merge_url) SDE.downloadLinkToast(d.merge_url, d.merged_file,
      { rows: s.final_rows, cols: s.columns });
  } catch (e) {
    if (typeof Swal !== "undefined") {
      Swal.fire({ icon: "error", title: "Couldn't merge the files",
        html: `<div style="text-align:left;color:#475569">${SDE.esc(e.message)}</div>`,
        confirmButtonText: "OK", confirmButtonColor: "#4f46e5" });
    } else { SDE.toast(e.message, "error"); }
  }
  finally { SDE.busy(false); }
};
SDE.actions["delivery-errors"] = async function () {
  if (!SDE.requireData()) return;
  SDE.busy(true);
  try {
    await SDE.commitEdits();
    const d = await SDE.get("/api/feature/delivery-errors");
    const s = d.summary || {};
    const tbl = (title, obj, col) => {
      const keys = Object.keys(obj || {});
      if (!keys.length) return `<p class="hint">No "${SDE.esc(col)}" column found, or no values.</p>`;
      return `<h4 style="margin:14px 0 6px">${title}</h4><table class="mini-table">
        <thead><tr><th>${SDE.esc(col)}</th><th>Errors</th></tr></thead><tbody>` +
        keys.map((k) => `<tr><td>${SDE.esc(k)}</td><td>${obj[k]}</td></tr>`).join("") +
        `</tbody></table>`;
    };
    SDE.modal({
      title: "Error summary", icon: "fa-triangle-exclamation",
      bodyHTML: `<div class="hint">Total rows: <b>${s.total || 0}</b></div>`
        + tbl("By WCAG Ver", s.by_wcag, s.wcag_col || "WCAG Ver")
        + tbl("By Priority", s.by_prio, s.prio_col || "Priority"),
      buttons: [{ label: "Close", variant: "primary", onClick: SDE.closeModal }],
    });
  } catch (e) { SDE.toast(e.message, "error"); }
  finally { SDE.busy(false); }
};

// ---- delivery mode: manage the template (upload / remove) ----
SDE.updateTplNote = function (found) {
  const note = document.getElementById("tplNote");
  if (!note) return;
  note.classList.toggle("found", !!found);
  note.classList.toggle("missing", !found);
  const txt = note.querySelector(".tpl-note-text");
  if (txt) txt.textContent = found ? "Template ready" : "No template — plain output";
  const icon = note.querySelector("i");
  if (icon) icon.className = "fa-solid " + (found ? "fa-circle-check" : "fa-triangle-exclamation");
};
SDE.actions["template-manage"] = async function () {
  let status = { found: false };
  try { status = await SDE.get("/api/template/status"); } catch (e) { /* ignore */ }
  const statusLine = status.found
    ? `<div class="tpl-note found" style="margin-bottom:12px"><i class="fa-solid fa-circle-check"></i> A template is installed — delivery exports will use it.</div>`
    : `<div class="tpl-note missing" style="margin-bottom:12px"><i class="fa-solid fa-triangle-exclamation"></i> No template installed — delivery exports are plain workbooks.</div>`;
  SDE.modal({
    title: "Delivery template", icon: "fa-file-invoice",
    bodyHTML: `${statusLine}
      <div class="hint">Upload your standardized audit workbook (.xlsx). Exports from this page will be written into a copy of it. Remove it to go back to plain output.</div>`,
    buttons: [
      { label: "Close", onClick: SDE.closeModal },
      ...(status.found ? [{ label: "Remove template", onClick: async () => {
          try { const d = await SDE.post("/api/template/clear", {}); SDE.updateTplNote(d.found);
            SDE.toast("Template removed — exports will be plain", "info"); SDE.closeModal(); }
          catch (e) { SDE.toast(e.message, "error"); }
        } }] : []),
      { label: "Upload template…", variant: "primary", onClick: () => {
          SDE.closeModal(); document.getElementById("tplFileInput").click();
        } },
    ],
  });
};
SDE.handleTemplateUpload = async function (file) {
  if (!file) return;
  const fd = new FormData(); fd.append("file", file);
  SDE.busy(true);
  try {
    const d = await SDE.api("/api/template/upload", { method: "POST", body: fd });
    SDE.updateTplNote(d.found);
    SDE.toast(`Template set: ${d.uploaded} — delivery exports will use it`, "success");
  } catch (e) {
    if (typeof Swal !== "undefined") {
      Swal.fire({ icon: "error", title: "Couldn't use that template",
        html: `<div style="text-align:left;color:#475569">${SDE.esc(e.message)}</div>`,
        confirmButtonColor: "#4f46e5" });
    } else { SDE.toast(e.message, "error"); }
  } finally { SDE.busy(false); }
};
SDE.actions["export-template"] = function () {
  if (!SDE.requireData()) return;
  // Auto-fill defaults from the loaded file; user can edit but not leave blank.
  const fname = (SDE.status && SDE.status.file) || "";
  const courseDefault = fname.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
  const rows = (SDE.status && SDE.status.rows) || 0;
  SDE.modal({
    title: "Export using delivery template", icon: "fa-file-invoice",
    bodyHTML: `<div class="hint" style="margin-bottom:10px">These fill the Audit Summary
      heading. They're pre-filled from your file — edit if needed, but they can't be empty.</div>
      <div class="field"><label>Report title</label>
        <input id="tplTitle" type="text" value="WCAG 2.2 AA Accessibility Audit Report"></div>
      <div class="field" style="margin-top:8px"><label>Course / product name</label>
        <input id="tplCourse" type="text" value="${SDE.esc(courseDefault)}" placeholder="e.g. Phlebotomy Essentials 8e"></div>
      <div class="field" style="margin-top:8px"><label>Course details / content</label>
        <input id="tplDetails" type="text" value="${rows} issue(s) in this delivery" placeholder="e.g. ISBN … | Navigate Premier + eBook"></div>
      <div id="tplErr" class="hint" style="color:#dc2626;margin-top:8px;display:none"></div>`,
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      { label: "Export", variant: "primary", onClick: async () => {
          const title = document.getElementById("tplTitle").value.trim();
          const course = document.getElementById("tplCourse").value.trim();
          const details = document.getElementById("tplDetails").value.trim();
          const err = document.getElementById("tplErr");
          if (!title || !course || !details) {
            err.textContent = "Title, course, and details are all required — none can be empty.";
            err.style.display = "block";
            return;
          }
          SDE.closeModal();
          SDE.busy(true);
          try {
            await SDE.commitEdits();
            const d = await SDE.post("/api/feature/export-template", { title, course, details });
            SDE.toast(d.template_used ? "Exported using the delivery template"
              : "No template installed — exported a standalone workbook",
              d.template_used ? "success" : "info");
            SDE.downloadLinkToast(d.url, d.file, {});
          } catch (e) { SDE.toast(e.message, "error"); }
          finally { SDE.busy(false); }
        } },
    ],
  });
};

SDE.actions["export-excel"] = function () {
  if (!SDE.requireData()) return;
  SDE.modal({
    title: "Export to Excel", icon: "fa-file-excel",
    bodyHTML: `<div class="hint" style="margin-bottom:12px">Choose how cells should be highlighted in the downloaded workbook (leave all off for a plain file):</div>
      <label class="chk-row" style="font-size:13.5px;margin-bottom:6px"><input type="checkbox" id="xlHlSummary">
        <span>Highlight <b>Summary</b> cells over 215 characters or with line breaks in <span style="background:#DCFCE7;padding:0 6px;border-radius:3px">light green</span></span></label>
      <label class="chk-row" style="font-size:13.5px;margin-bottom:6px"><input type="checkbox" id="xlHlBlanks">
        <span>Highlight <b>blank / empty</b> cells in <span style="background:#FEE2E2;padding:0 6px;border-radius:3px">light red</span></span></label>
      <label class="chk-row" style="font-size:13.5px"><input type="checkbox" id="xlHlDups">
        <span>Download with the <b>duplicate-group</b> highlighting (the
          <span style="background:#FDEBD0;padding:0 5px;border-radius:3px">colour</span><span style="background:#DCEAFF;padding:0 5px;border-radius:3px">groups</span>
          from <b>Find duplicates</b>)</span></label>`,
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      { label: "Export", variant: "primary", onClick: () => {
          const summary = document.getElementById("xlHlSummary").checked;
          const blanks = document.getElementById("xlHlBlanks").checked;
          const dups = document.getElementById("xlHlDups").checked;
          SDE.closeModal();
          doExcelExport({ summary, blanks, dups });
        } },
    ],
  });
};

SDE.downloadLinkToast = function (url, name, meta) {
  // start the download automatically
  try {
    const a = document.createElement("a");
    a.href = url; a.download = name || "";
    document.body.appendChild(a); a.click(); a.remove();
  } catch (e) { /* manual link below */ }

  const count = (meta && meta.rows != null && meta.cols != null)
    ? `<div class="export-count">
         <div class="ec-nums"><b>${Number(meta.rows).toLocaleString()}</b> rows
           &nbsp;&middot;&nbsp; <b>${Number(meta.cols).toLocaleString()}</b> columns</div>
         <div class="ec-sub">included in the exported file</div>
       </div>`
    : "";

  // Use the app's OWN modal (local, always present) instead of SweetAlert2,
  // so the count is shown reliably even if a CDN library failed to load.
  SDE.modal({
    title: "Export complete", icon: "fa-circle-check",
    bodyHTML: `${count}
      <div class="hint" style="margin:4px 0 14px">
        Your download should have started automatically. If it didn't, use the
        button below.</div>
      <a href="${url}" download class="btn primary" style="width:100%;text-align:center">
        <i class="fa-solid fa-download"></i>&nbsp; Download ${SDE.esc(name)}</a>`,
    buttons: [{ label: "Done", variant: "primary", onClick: SDE.closeModal }],
  });
};

SDE.actions["reports"] = function () {
  if (!SDE.requireData()) return;
  SDE.modal({
    title: "Generate Report", icon: "fa-file-lines",
    bodyHTML: `
      <div class="field"><label>Report type</label>
        <select id="rpKind">
          <option value="validation">Validation report</option>
          <option value="duplicate">Duplicate report</option>
          <option value="error">Error report</option>
          <option value="summary">Data summary report</option>
        </select></div>
      <div class="field"><label>Format</label>
        <select id="rpFmt">
          <option value="pdf">PDF</option>
          <option value="excel">Excel</option>
          <option value="html">HTML</option>
        </select></div>`,
    buttons: [
      { label: "Cancel", onClick: SDE.closeModal },
      { label: "Generate", variant: "primary", onClick: async () => {
        const kind = val("rpKind"); const fmt = val("rpFmt");
        SDE.closeModal(); SDE.busy(true);
        try {
          await SDE.commitEdits();
          const d = await SDE.post(`/api/report/${kind}/${fmt}`, {});
          SDE.downloadLinkToast(d.url, d.file);
        } catch (e) { SDE.toast(e.message, "error"); }
        finally { SDE.busy(false); }
      } },
    ],
  });
};

/* ---------- small utils ------------------------------------------------- */
function val(id) { const e = document.getElementById(id); return e ? e.value : ""; }
SDE.requireData = function () {
  if (!SDE.status || !SDE.status.loaded || SDE.status.source === "pdf") {
    SDE.toast("Load a data file first", "warn"); return false;
  }
  return true;
};

/* =========================================================================
   BOOTSTRAP
   ========================================================================= */
/* =========================================================================
   RIBBON MENU (spreadsheet-style top menu)
   ========================================================================= */
SDE.initRibbon = function () {
  const ribbon = document.getElementById("ribbon");
  if (!ribbon) return;
  const menus = Array.from(ribbon.querySelectorAll(".ribbon-menu"));
  if (!menus.length) return;

  const closeAll = (except) => {
    menus.forEach((m) => {
      if (m === except) return;
      m.classList.remove("open");
      const top = m.querySelector(".ribbon-top");
      if (top) top.setAttribute("aria-expanded", "false");
    });
  };
  const open = (m) => {
    closeAll(m);
    m.classList.add("open");
    const top = m.querySelector(".ribbon-top");
    if (top) top.setAttribute("aria-expanded", "true");
  };
  const isOpen = (m) => m.classList.contains("open");
  const itemsOf = (m) => Array.from(m.querySelectorAll(".ribbon-item:not(:disabled)"));

  menus.forEach((menu) => {
    const top = menu.querySelector(".ribbon-top");
    top.addEventListener("click", (e) => {
      e.stopPropagation();
      if (isOpen(menu)) closeAll();
      else open(menu);
    });
    // Open with keyboard and move into the list
    top.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open(menu);
        const items = itemsOf(menu);
        if (items.length) items[0].focus();
      } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const i = menus.indexOf(menu);
        const next = e.key === "ArrowRight"
          ? menus[(i + 1) % menus.length]
          : menus[(i - 1 + menus.length) % menus.length];
        next.querySelector(".ribbon-top").focus();
        if (isOpen(menu)) open(next);
      }
    });
    // Clicking an item runs its action (global handler) then closes the menu
    menu.querySelectorAll(".ribbon-item").forEach((item) => {
      item.addEventListener("click", () => setTimeout(closeAll, 0));
    });
    // Keyboard navigation inside the dropdown
    menu.addEventListener("keydown", (e) => {
      const items = itemsOf(menu);
      const idx = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") {
        e.preventDefault(); items[(idx + 1) % items.length]?.focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault(); items[(idx - 1 + items.length) % items.length]?.focus();
      } else if (e.key === "Home") {
        e.preventDefault(); items[0]?.focus();
      } else if (e.key === "End") {
        e.preventDefault(); items[items.length - 1]?.focus();
      } else if (e.key === "Escape") {
        e.preventDefault(); closeAll(); top.focus();
      }
    });
  });

  // Close on outside click
  document.addEventListener("click", (e) => {
    if (!ribbon.contains(e.target)) closeAll();
  });
};


document.addEventListener("DOMContentLoaded", () => {
  // theme icon
  const t = document.documentElement.getAttribute("data-theme");
  document.querySelector("#themeToggle i").className =
    t === "dark" ? "fa-solid fa-sun" : "fa-solid fa-moon";
  document.getElementById("themeToggle").onclick = SDE.toggleTheme;

  // file input
  document.getElementById("fileInput").addEventListener("change", (e) => {
    const files = e.target.files;
    if (files && files.length > 1 && (window.SDE_PAGE_MODE === "merge")) {
      SDE.handleMerge(files);            // placeholder 1 only: merge into one grid
    } else if (files && files[0]) {
      SDE.handleUpload(files[0]);        // single file (delivery / editor)
    }
    e.target.value = "";
  });

  // merge multi-file input (merge mode)
  const mi = document.getElementById("mergeInput");
  if (mi) mi.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length) SDE.handleMerge(e.target.files);
    e.target.value = "";
  });

  // delivery template upload input (delivery mode)
  const tpl = document.getElementById("tplFileInput");
  if (tpl) tpl.addEventListener("change", (e) => {
    if (e.target.files[0]) SDE.handleTemplateUpload(e.target.files[0]);
    e.target.value = "";
  });

  // global search (header) -> grid search
  const gs = document.getElementById("globalSearch");
  gs.addEventListener("keydown", (e) => {
    if (e.key === "Enter") SDE.grid.search(gs.value.trim());
  });

  // toolbar + global action dispatch
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const act = btn.dataset.action;
    const handler = SDE.actions[act];
    if (handler) { e.preventDefault(); handler(btn); }
  });

  // modal close
  document.getElementById("modalClose").onclick = SDE.closeModal;
  document.getElementById("modalOverlay").addEventListener("click", (e) => {
    if (e.target.id === "modalOverlay") SDE.closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") SDE.closeModal();
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); if (SDE.actions["save"]) SDE.actions["save"](); }
    if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); SDE.actions["undo"](); }
    if ((e.ctrlKey || e.metaKey) && e.key === "y") { e.preventDefault(); SDE.actions["redo"](); }
  });

  SDE.initRibbon();
  SDE.refreshStatus();
});
