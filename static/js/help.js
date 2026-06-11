/* ==========================================================================
   help.js — "WCAG & Axe Lookup" Help dialog (self-contained)
   --------------------------------------------------------------------------
   This is the ONLY frontend file for the Help feature. It is intentionally
   isolated so it can be changed without touching app.js:

     • registers the SDE.actions["wcag-help"] handler (the Help button),
     • renders the two-tab dialog (WCAG criteria + Rule ID),
     • talks to its own backend at /api/help/* (see help_lookup/ in Python),
     • injects its own styles (no dependency on style.css).

   It only relies on the shared SDE core (SDE.modal / SDE.post / SDE.esc),
   which every feature uses. To evolve Help, edit this file + help_lookup/.
   ========================================================================== */
(function () {
  if (typeof SDE === "undefined") return;       // needs the SDE core (app.js)

  var HELP = {};

  /* one-time stylesheet injection so Help is visually self-contained */
  HELP.injectStyles = function () {
    if (document.getElementById("help-lookup-styles")) return;
    var css = `
      .help-tabs { display:flex; gap:6px; margin-bottom:10px; }
      .help-tab { padding:8px 16px; border-radius:8px; border:1px solid var(--border,#e2e8f0);
        background:var(--surface,#fff); color:var(--text-faint,#64748b); font-weight:600;
        cursor:pointer; font-size:13px; }
      .help-tab.is-active { background:var(--accent,#2563eb); color:#fff; border-color:var(--accent,#2563eb); }
      .help-table { width:100%; border-collapse:collapse; font-size:12.5px; }
      .help-table th { text-align:left; color:var(--text-faint,#64748b); font-weight:600;
        padding:6px 8px; border-bottom:2px solid var(--border,#e2e8f0); }
      .help-table td { padding:7px 8px; border-bottom:1px solid var(--border,#e2e8f0); }
      .help-chip { display:inline-block; font-size:10.5px; line-height:1.4; padding:1px 7px;
        border-radius:10px; background:var(--surface-2,#f1f5f9); color:var(--text-faint,#64748b);
        border:1px solid var(--border,#e2e8f0); white-space:nowrap; }
      .help-chip--id { font-weight:600; font-size:11.5px; background:var(--accent-soft,#eef2ff);
        color:var(--accent,#4f46e5); border-color:var(--accent,#c7d2fe); }
      .help-err { color:#dc2626; }
    `;
    var s = document.createElement("style");
    s.id = "help-lookup-styles";
    s.textContent = css;
    document.head.appendChild(s);
  };

  /* the Help button (data-action="wcag-help") opens this */
  SDE.actions["wcag-help"] = function () {
    HELP.injectStyles();
    SDE.modal({
      title: "WCAG & Axe Lookup", icon: "fa-circle-question", wide: true,
      bodyHTML: `
        <div class="help-tabs">
          <button id="helpTabWcag" class="help-tab" onclick="SDE.helpTab('wcag')">WCAG criteria</button>
          <button id="helpTabAxe" class="help-tab" onclick="SDE.helpTab('axe')">Rule ID</button>
        </div>
        <div id="helpPaneWcag">
          <div class="hint">Search by criterion number, name, or level — results are WCAG Ref, WCAG (name) and WCAG Ver (level).</div>
          <input id="helpWcagQ" type="text" autocomplete="off" placeholder="e.g. 1.4.3  ·  contrast  ·  AA"
            oninput="SDE.helpSearchWcag(this.value)" style="width:100%;margin:10px 0;padding:8px 10px">
          <div id="helpWcagResults" style="max-height:320px;overflow:auto"></div>
        </div>
        <div id="helpPaneAxe" style="display:none">
          <div class="hint">Search the axe rule catalogue by Rule ID, description, tag, or WCAG criterion.</div>
          <input id="helpAxeQ" type="text" autocomplete="off" placeholder="e.g. color-contrast  ·  alt text  ·  1.4.3"
            oninput="SDE.helpSearchAxe(this.value)" style="width:100%;margin:10px 0;padding:8px 10px">
          <div id="helpAxeResults" style="max-height:320px;overflow:auto"></div>
        </div>`,
      buttons: [{ label: "Close", onClick: SDE.closeModal }],
    });
    HELP.axeLoaded = false;
    SDE.helpTab("wcag");
    SDE.helpSearchWcag("");
  };

  SDE.helpTab = function (which) {
    var axe = which === "axe";
    document.getElementById("helpPaneWcag").style.display = axe ? "none" : "block";
    document.getElementById("helpPaneAxe").style.display = axe ? "block" : "none";
    var bw = document.getElementById("helpTabWcag"), ba = document.getElementById("helpTabAxe");
    if (bw) bw.classList.toggle("is-active", !axe);
    if (ba) ba.classList.toggle("is-active", axe);
    if (axe && !HELP.axeLoaded) { HELP.axeLoaded = true; SDE.helpSearchAxe(""); }
  };

  SDE.helpSearchWcag = async function (q) {
    var box = document.getElementById("helpWcagResults");
    if (!box) return;
    try {
      var d = await SDE.post("/api/help/wcag-search", { q: q || "" });
      if (!d.count) { box.innerHTML = `<div class="hint">No matching WCAG criteria in the tag file.</div>`; return; }
      var rows = (d.rows || []).map(function (r) {
        return `<tr><td style="font-weight:600;white-space:nowrap">${SDE.esc(r.ref)}</td>
          <td>${SDE.esc(r.name)}</td><td style="white-space:nowrap">${SDE.esc(r.level)}</td></tr>`;
      }).join("");
      box.innerHTML = `<div class="hint" style="margin-bottom:6px">${d.count} of ${d.total} criteria</div>
        <table class="help-table"><tr><th>WCAG Ref</th><th>WCAG</th><th>WCAG Ver</th></tr>${rows}</table>`;
    } catch (e) {
      box.innerHTML = `<div class="hint help-err">Search failed: ${SDE.esc(e.message)}</div>`;
    }
  };

  SDE.helpSearchAxe = async function (q) {
    var box = document.getElementById("helpAxeResults");
    if (!box) return;
    try {
      var d = await SDE.post("/api/help/axe-search", { q: q || "" });
      if (!d.count) { box.innerHTML = `<div class="hint">No matching rules.</div>`; return; }
      var rows = (d.rows || []).map(function (r) {
        var link = r.helpUrl ? `<a href="${SDE.esc(r.helpUrl)}" target="_blank" rel="noopener">docs</a>` : "";
        var wcag = r.wcag ? `${SDE.esc(r.wcag)}${r.level ? " · " + SDE.esc(r.level) : ""}` : SDE.esc(r.level || "");
        var idChip = `<span class="help-chip help-chip--id">${SDE.esc(r.ruleId)}</span>`;
        var tags = (r.tags || []).map(function (t) { return `<span class="help-chip">${SDE.esc(t)}</span>`; }).join(" ");
        return `<tr>
          <td style="vertical-align:top">${idChip}</td>
          <td style="vertical-align:top"><div style="display:flex;flex-wrap:wrap;gap:3px">${tags}</div></td>
          <td style="vertical-align:top"><div style="font-weight:600">${SDE.esc(r.help || "")}</div>
            <div class="hint" style="margin-top:2px">${SDE.esc(r.description || "")}</div></td>
          <td style="white-space:nowrap;vertical-align:top">${wcag}</td>
          <td style="vertical-align:top">${link}</td></tr>`;
      }).join("");
      box.innerHTML = `<div class="hint" style="margin-bottom:6px">${d.count} of ${d.total} rules</div>
        <table class="help-table"><tr><th>Rule ID</th><th>Tags</th><th>Rule</th><th>WCAG</th><th></th></tr>${rows}</table>`;
    } catch (e) {
      box.innerHTML = `<div class="hint help-err">Search failed: ${SDE.esc(e.message)}</div>`;
    }
  };
})();
