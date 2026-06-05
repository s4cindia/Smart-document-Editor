/* =========================================================================
   grid.js — AG Grid (Community) data grid layer.

   Uses the Infinite Row Model so 50k / 100k / 250k row datasets never get
   dumped into the DOM at once. Paging, sorting and searching are delegated
   to the Flask backend (Polars) via POST /api/data/rows.

   Exposes the SDE.grid API consumed by app.js / validation.js:
     SDE.grid.init()             – build the grid
     SDE.grid.reload()           – refresh columns + reset view (new file)
     SDE.grid.reloadKeepView()   – refresh columns, keep filters (undo/redo)
     SDE.grid.refresh()          – purge the row cache (re-fetch current view)
     SDE.grid.search(term)       – global contains-search across all columns
     SDE.grid.selectedIds()      – array of __id for ticked (loaded) rows
     SDE.grid.applyTheme(theme)  – swap ag-theme-quartz / quartz-dark
     SDE.grid.setDuplicateRows(ids)
     SDE.grid.setErrorRows(ids)
   ========================================================================= */
(function () {
  const G = {
    api: null,
    built: false,
    editable: true,
    _pending: 0,
    // active server-side search state
    searchTerm: null,
    searchColumns: null,
    searchMode: "contains",
    // highlight sets (row __id)
    dupIds: new Set(),
    errIds: new Set(),
  };
  SDE.grid = G;

  const gridEl = () => document.getElementById("grid");

  /* ---------- column definitions ---------------------------------------- */
  function buildColumnDefs() {
    const selector = {
      headerName: "",
      colId: "__sel",
      width: 46,
      pinned: "left",
      checkboxSelection: true,
      sortable: false,
      filter: false,
      resizable: false,
      suppressMovable: true,
      lockPosition: true,
      editable: false,
    };

    const cols = (SDE.columnDefs || []).map((c) => {
      const isNum = c.dataType === "number";
      const isSummary = String(c.field).trim().toLowerCase() === "summary";
      const def = {
        field: c.field,
        headerName: c.headerName || c.field,
        editable: () => G.editable,
        resizable: true,
        sortable: true,
        minWidth: 110,
        headerTooltip: `${c.field}  ·  ${c.polarsType || c.dataType}`,
        cellClassRules: {
          "error-cell": (p) => p.data && G.errIds.has(p.data.__id),
          // Summary cells longer than 215 chars or containing a line break
          "summary-overflow-cell": (p) => isSummary && p.value != null &&
            (String(p.value).length > 215 || String(p.value).indexOf("\n") >= 0),
          "missing-cell": (p) => {
            const v = p.value;
            return v === null || v === undefined ||
              (typeof v === "string" && v.trim() === "");
          },
        },
      };
      if (isNum) {
        def.type = "numericColumn";
        def.valueParser = (p) => {
          if (p.newValue === "" || p.newValue == null) return null;
          const n = Number(p.newValue);
          return Number.isNaN(n) ? p.newValue : n;
        };
      }
      return def;
    });

    return [selector, ...cols];
  }

  /* ---------- datasource (infinite row model) --------------------------- */
  function makeDatasource() {
    return {
      getRows: async (params) => {
        const body = {
          startRow: params.startRow,
          endRow: params.endRow,
          sortModel: params.sortModel,
          search: G.searchTerm,
          searchColumns: G.searchColumns,
          searchMode: G.searchMode,
        };
        try {
          const d = await SDE.post("/api/data/rows", body);
          // Infinite Row Model uses successCallback/failCallback; newer
          // versions also expose success/fail. Support whichever exists.
          if (typeof params.successCallback === "function") {
            params.successCallback(d.rows, d.lastRow);
          } else {
            params.success({ rowData: d.rows, rowCount: d.lastRow });
          }
          SDE.setFilteredCount(d.lastRow);
        } catch (e) {
          SDE.toast("Failed to load rows: " + e.message, "error");
          if (typeof params.failCallback === "function") params.failCallback();
          else if (typeof params.fail === "function") params.fail();
        }
      },
    };
  }

  /* ---------- grid construction ----------------------------------------- */
  function gridOptions() {
    return {
      columnDefs: buildColumnDefs(),
      rowModelType: "infinite",
      datasource: makeDatasource(),
      cacheBlockSize: 100,
      maxBlocksInCache: 40,
      infiniteInitialRowCount: 1,
      rowSelection: "multiple",
      suppressRowClickSelection: true,
      getRowId: (p) => String(p.data.__id),
      animateRows: false,
      enableCellTextSelection: true,
      ensureDomOrder: true,
      tooltipShowDelay: 400,
      rowClassRules: {
        "dup-row": (p) => p.data && G.dupIds.has(p.data.__id),
      },
      defaultColDef: {
        sortable: true,
        resizable: true,
        filter: false,
        suppressHeaderMenuButton: true,
      },
      onCellValueChanged: onCellValueChanged,
      onSelectionChanged: () => {
        if (G.api) SDE.setSelectedCount(G.api.getSelectedRows().length);
      },
    };
  }

  async function onCellValueChanged(ev) {
    G._pending++;
    try {
      await SDE.post("/api/data/cell", {
        id: ev.data.__id, field: ev.colDef.field, value: ev.newValue,
      });
      SDE.refreshStatus();
    } catch (e) {
      SDE.toast("Edit rejected: " + e.message, "error");
      G.refresh();
    } finally {
      G._pending--;
    }
  }

  /* Commit any in-progress edit, then resolve once pending saves finish.
     Called before export/report so downloads always include the latest edits. */
  G.stopEditing = function () {
    try { if (G.api && G.api.stopEditing) G.api.stopEditing(false); } catch (e) {}
  };
  G.flush = function () {
    return new Promise((resolve) => {
      const started = Date.now();
      const timer = setInterval(() => {
        if (G._pending <= 0 || Date.now() - started > 4000) {
          clearInterval(timer);
          resolve();
        }
      }, 30);
    });
  };

  /* ---------- public API ------------------------------------------------ */
  G.init = function () {
    if (G.built) return;
    const el = gridEl();
    if (typeof agGrid === "undefined" || !agGrid.createGrid) {
      el.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-faint)">
        <i class="fa-solid fa-triangle-exclamation" style="font-size:28px"></i>
        <p style="margin-top:12px">The data grid library failed to load.<br>
        Check your internet connection or antivirus/proxy, then reload the page
        (Ctrl+F5).</p></div>`;
      SDE.toast("Grid library failed to load", "error");
      return;
    }
    try {
      G.api = agGrid.createGrid(el, gridOptions());
      G.built = true;
      G.applyTheme(document.documentElement.getAttribute("data-theme"));
    } catch (err) {
      console.error("AG Grid init failed:", err);
      el.innerHTML = `<div style="padding:40px;text-align:center;color:var(--danger)">
        Grid failed to start: ${SDE.esc(err.message)}</div>`;
      SDE.toast("Grid failed to start — see console (F12)", "error");
    }
  };

  async function loadColumns() {
    const d = await SDE.get("/api/data/columns");
    SDE.columnDefs = d.columns || [];
    SDE.columns = d.names || [];
  }

  G.reload = async function () {
    try { await loadColumns(); }
    catch (e) { SDE.toast(e.message, "error"); return; }

    G.dupIds.clear();
    G.errIds.clear();
    G.searchTerm = null; G.searchColumns = null; G.searchMode = "contains";

    if (!G.built) { G.init(); return; }
    G.api.setGridOption("columnDefs", buildColumnDefs());
    G.api.setGridOption("datasource", makeDatasource());
  };

  // undo/redo may change the schema (column promotion / merge / split),
  // so refresh column defs but keep the current filters/search.
  G.reloadKeepView = async function () {
    try {
      await loadColumns();
      if (G.built) G.api.setGridOption("columnDefs", buildColumnDefs());
    } catch (e) { /* ignore */ }
    G.refresh();
  };

  G.refresh = function () {
    if (G.api) G.api.purgeInfiniteCache();
  };

  G.search = function (term) {
    G.searchTerm = (term && term.length) ? term : null;
    G.searchColumns = null;
    G.searchMode = "contains";
    G.refresh();
  };

  G.applyTheme = function (theme) {
    const el = gridEl();
    if (!el) return;
    el.classList.remove("ag-theme-quartz", "ag-theme-quartz-dark");
    el.classList.add(theme === "dark" ? "ag-theme-quartz-dark" : "ag-theme-quartz");
  };

  G.selectedIds = function () {
    if (!G.api) return [];
    return G.api.getSelectedRows().map((r) => r.__id);
  };

  G.setDuplicateRows = function (ids) {
    G.dupIds = new Set(ids || []);
    if (G.api) G.api.redrawRows();
  };

  G.setErrorRows = function (ids) {
    G.errIds = new Set(ids || []);
    if (G.api) G.api.redrawRows();
  };

  /* =======================================================================
     ACTIONS — VIEW + ROWS toolbar groups
     ===================================================================== */
  function guard() {
    if (!SDE.status || !SDE.status.loaded || SDE.status.source === "pdf") {
      SDE.toast("Load a data file first", "warn");
      return false;
    }
    return true;
  }

  /* ----- VIEW: search (across all/selected columns) --------------------- */
  SDE.actions["search"] = function () {
    if (!guard()) return;
    SDE.modal({
      title: "Search", icon: "fa-magnifying-glass",
      bodyHTML: `
        <div class="field"><label>Search term</label>
          <input type="text" id="schTerm" placeholder="Type to search…"></div>
        <div class="field"><label>Match mode</label>
          <select id="schMode">
            <option value="contains">Contains</option>
            <option value="exact">Exact match</option>
            <option value="starts">Starts with</option>
            <option value="ends">Ends with</option>
            <option value="regex">Regex</option>
          </select></div>
        <div class="field"><label>Columns (none = all)</label>
          ${SDE.columnSelectHTML("schCols", { multiple: true })}</div>`,
      buttons: [
        { label: "Clear", onClick: () => { SDE.closeModal(); SDE.actions["clear-filters"](); } },
        { label: "Search", variant: "primary", onClick: () => {
          const cols = SDE.getSelected("schCols");
          G.searchTerm = document.getElementById("schTerm").value.trim() || null;
          G.searchColumns = cols.length ? cols : null;
          G.searchMode = document.getElementById("schMode").value;
          SDE.closeModal();
          G.refresh();
        } },
      ],
    });
    setTimeout(() => { const e = document.getElementById("schTerm"); if (e) e.focus(); }, 60);
  };

  /* ----- VIEW: filter (server-side, reuses the search engine) ----------- */
  SDE.actions["filter"] = function () {
    if (!guard()) return;
    SDE.modal({
      title: "Filter rows", icon: "fa-filter",
      bodyHTML: `
        <div class="field"><label>Column</label>
          ${SDE.columnSelectHTML("fltCol", { multiple: false })}</div>
        <div class="field"><label>Condition</label>
          <select id="fltMode">
            <option value="contains">Contains</option>
            <option value="exact">Equals</option>
            <option value="starts">Starts with</option>
            <option value="ends">Ends with</option>
            <option value="regex">Matches regex</option>
          </select></div>
        <div class="field"><label>Value</label>
          <input type="text" id="fltVal" placeholder="Value to match…"></div>`,
      buttons: [
        { label: "Cancel", onClick: SDE.closeModal },
        { label: "Apply filter", variant: "primary", onClick: () => {
          const col = document.getElementById("fltCol").value;
          G.searchTerm = document.getElementById("fltVal").value || null;
          G.searchColumns = col ? [col] : null;
          G.searchMode = document.getElementById("fltMode").value;
          SDE.closeModal();
          G.refresh();
          SDE.toast("Filter applied", "success");
        } },
      ],
    });
  };

  /* ----- VIEW: clear filters + sort ------------------------------------- */
  SDE.actions["clear-filters"] = function () {
    if (!guard()) return;
    G.searchTerm = null; G.searchColumns = null; G.searchMode = "contains";
    if (G.api) G.api.applyColumnState({ defaultState: { sort: null } });
    G.refresh();
    const gs = document.getElementById("globalSearch");
    if (gs) gs.value = "";
    SDE.toast("Filters & sorting cleared", "info");
  };

  /* ----- VIEW: sort ----------------------------------------------------- */
  SDE.actions["sort"] = function () {
    if (!guard()) return;
    SDE.modal({
      title: "Sort data", icon: "fa-arrow-down-wide-short",
      bodyHTML: `
        <div class="field"><label>Column</label>
          ${SDE.columnSelectHTML("srtCol", { multiple: false })}</div>
        <div class="field"><label>Direction</label>
          <select id="srtDir">
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select></div>`,
      buttons: [
        { label: "Cancel", onClick: SDE.closeModal },
        { label: "Sort", variant: "primary", onClick: () => {
          const col = document.getElementById("srtCol").value;
          const dir = document.getElementById("srtDir").value;
          SDE.closeModal();
          G.api.applyColumnState({
            state: [{ colId: col, sort: dir }],
            defaultState: { sort: null },
          });
        } },
      ],
    });
  };

  /* ----- VIEW: column manager (Columns / Hide) -------------------------- */
  function showAllColumns() {
    G.api.getColumns().forEach((col) => {
      if (col.getColId() !== "__sel") G.api.setColumnVisible(col.getColId(), true);
    });
  }
  function columnManager(title) {
    if (!guard()) return;
    const state = G.api.getColumnState();
    const rows = state
      .filter((c) => c.colId !== "__sel")
      .map((c) => `
        <label class="chk-row">
          <input type="checkbox" data-col="${SDE.esc(c.colId)}" ${c.hide ? "" : "checked"}>
          <span>${SDE.esc(c.colId)}</span>
        </label>`).join("");
    SDE.modal({
      title, icon: "fa-table-columns",
      bodyHTML: `<div class="hint" style="margin-bottom:10px">Tick the columns to keep visible. Drag column headers in the grid to reorder.</div>
        <div class="chk-list">${rows}</div>`,
      buttons: [
        { label: "Show all", onClick: () => { showAllColumns(); SDE.closeModal(); } },
        { label: "Apply", variant: "primary", onClick: () => {
            document.querySelectorAll("#modalBody input[data-col]").forEach((cb) => {
              G.api.setColumnVisible(cb.dataset.col, cb.checked);
            });
            SDE.closeModal();
          } },
      ],
    });
  }
  SDE.actions["columns"] = () => columnManager("Manage columns");
  SDE.actions["hide-columns"] = () => columnManager("Hide / show columns");
  SDE.actions["show-columns"] = function () {
    if (!guard()) return;
    showAllColumns();
    SDE.toast("All columns visible", "info");
  };

  /* ----- ROWS: edit toggle ---------------------------------------------- */
  SDE.actions["edit"] = function () {
    if (!guard()) return;
    G.editable = !G.editable;
    G.api.redrawRows();
    SDE.toast(G.editable ? "Inline editing ON — double-click a cell" : "Inline editing OFF",
      G.editable ? "success" : "info");
  };

  /* ----- ROWS: add row -------------------------------------------------- */
  SDE.actions["add-row"] = async function () {
    if (!guard()) return;
    try {
      const d = await SDE.post("/api/data/add-row", {});
      SDE.applyStatus(d.status);
      G.refresh();
      SDE.toast("Row added", "success");
    } catch (e) { SDE.toast(e.message, "error"); }
  };

  /* ----- ROWS: delete selected ----------------------------------------- */
  SDE.actions["delete-row"] = function () {
    if (!guard()) return;
    const ids = G.selectedIds();
    if (!ids.length) { SDE.toast("Tick the rows to delete first", "warn"); return; }
    Swal.fire({
      icon: "warning", title: `Delete ${ids.length} row(s)?`,
      text: "This can be undone with Ctrl+Z.",
      showCancelButton: true, confirmButtonText: "Delete",
      confirmButtonColor: "#dc2626",
    }).then(async (r) => {
      if (!r.isConfirmed) return;
      try {
        const d = await SDE.post("/api/data/delete-rows", { ids });
        SDE.applyStatus(d.status);
        G.api.deselectAll();
        G.refresh();
        SDE.toast(`Deleted ${d.removed} row(s)`, "success");
      } catch (e) { SDE.toast(e.message, "error"); }
    });
  };

  /* ----- ROWS: duplicate selected --------------------------------------- */
  SDE.actions["duplicate-selected"] = async function () {
    if (!guard()) return;
    const ids = G.selectedIds();
    if (!ids.length) { SDE.toast("Tick the rows to duplicate first", "warn"); return; }
    try {
      const d = await SDE.post("/api/data/duplicate-rows", { ids });
      SDE.applyStatus(d.status);
      G.refresh();
      SDE.toast(`Duplicated ${d.added} row(s)`, "success");
    } catch (e) { SDE.toast(e.message, "error"); }
  };

  /* ----- ROWS: tick / untick (loaded rows) ------------------------------ */
  SDE.actions["tick-all"] = function () {
    if (!guard()) return;
    let n = 0;
    G.api.forEachNode((node) => { if (node.data) { node.setSelected(true); n++; } });
    SDE.toast(n ? `Ticked ${n} loaded row(s) — scroll to load & tick more` : "No rows loaded", "info");
  };
  SDE.actions["untick-all"] = function () {
    if (!guard()) return;
    G.api.deselectAll();
  };

  /* ----- ROWS: undo / redo ---------------------------------------------- */
  SDE.actions["undo"] = async function () {
    try {
      const d = await SDE.post("/api/data/undo", {});
      SDE.applyStatus(d.status);
      G.reloadKeepView();
      SDE.toast("Undo: " + d.description, "info");
    } catch (e) { SDE.toast(e.message, "warn"); }
  };
  SDE.actions["redo"] = async function () {
    try {
      const d = await SDE.post("/api/data/redo", {});
      SDE.applyStatus(d.status);
      G.reloadKeepView();
      SDE.toast("Redo: " + d.description, "info");
    } catch (e) { SDE.toast(e.message, "warn"); }
  };
})();
