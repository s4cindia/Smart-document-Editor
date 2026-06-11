/* =========================================================================
   saveas.js — one place that owns "download a file the user can rename".

   window.saveFileAs(url, suggestedName, opts) shows a small dialog so the user
   can keep the default name or type their own, then downloads the file under
   that name. The file's extension is preserved automatically. Works on every
   page: it uses SweetAlert2 for a nice dialog when present (base.html pages)
   and falls back to the browser's native prompt otherwise (operation pages).

   Self-contained on purpose — no dependency on the SDE app namespace — so the
   standalone operation pages can use the exact same behaviour.
   ========================================================================= */
(function () {
  "use strict";

  function cleanName(name, fallbackUrl) {
    name = String(name == null ? "" : name).trim();
    if (!name && fallbackUrl) name = String(fallbackUrl);
    // keep only the final path segment, drop any query/hash
    name = name.split(/[\\/]/).pop().split("?")[0].split("#")[0];
    return name || "download";
  }

  function splitExt(name) {
    var i = name.lastIndexOf(".");
    if (i > 0 && i < name.length - 1) return [name.slice(0, i), name.slice(i)];
    return [name, ""];
  }

  // Strip characters Windows/macOS forbid in filenames; never return empty.
  function sanitizeBase(base) {
    base = String(base == null ? "" : base)
      .replace(/[\\/:*?"<>|\r\n\t]+/g, "_")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\.+$/, "");          // no trailing dots (invalid on Windows)
    return base || "download";
  }

  function withExt(base, ext) {
    if (ext && base.toLowerCase().slice(-ext.length) === ext.toLowerCase()) {
      return base;                   // user already typed the extension
    }
    return base + ext;
  }

  function triggerDownload(url, finalName) {
    // Same-origin <a download> controls the saved name; the ?name= query is a
    // belt-and-suspenders so a server (download route) can set the same name in
    // Content-Disposition for any flow that ignores the attribute.
    var sep = url.indexOf("?") >= 0 ? "&" : "?";
    var href = url + sep + "name=" + encodeURIComponent(finalName);
    var a = document.createElement("a");
    a.href = href;
    a.download = finalName;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { try { a.remove(); } catch (e) { /* ignore */ } }, 0);
  }

  /**
   * Ask the user for a name, then download `url` under it.
   * @param {string} url            same-origin download URL
   * @param {string} suggestedName  default file name (extension kept)
   * @param {object} [opts]         optional {rows, cols} shown as context
   * @returns {Promise<boolean>}    true if saved, false if cancelled
   */
  window.saveFileAs = function (url, suggestedName, opts) {
    opts = opts || {};
    var suggested = cleanName(suggestedName, url);
    var parts = splitExt(suggested);
    var base = parts[0], ext = parts[1];

    var note = "";
    if (opts.rows != null && opts.cols != null) {
      note = Number(opts.rows).toLocaleString() + " rows · "
           + Number(opts.cols).toLocaleString() + " columns";
    }

    if (window.Swal && typeof Swal.fire === "function") {
      var html = (note
            ? '<div style="margin-bottom:8px;color:#64748b;font-size:13px">'
              + note + ' included</div>'
            : "")
        + (ext
            ? '<div style="color:#64748b;font-size:12px;margin-bottom:6px">'
              + 'The <b>' + ext + '</b> extension is kept automatically.</div>'
            : "");
      return Swal.fire({
        title: "Save file as",
        html: html,
        input: "text",
        inputValue: base,
        inputAttributes: { "aria-label": "File name", autocapitalize: "off",
                           autocorrect: "off", spellcheck: "false" },
        showCancelButton: true,
        confirmButtonText: "Save",
        cancelButtonText: "Cancel",
        inputValidator: function (v) {
          if (!v || !v.trim()) return "Please enter a file name";
        }
      }).then(function (res) {
        if (!res || !res.isConfirmed) return false;
        triggerDownload(url, withExt(sanitizeBase(res.value), ext));
        return true;
      });
    }

    // Fallback for pages without SweetAlert2 (e.g. the operation pages).
    var label = "Save file as" + (note ? " (" + note + ")" : "") + ":";
    var typed = window.prompt(label, base);
    if (typed === null) return Promise.resolve(false);
    triggerDownload(url, withExt(sanitizeBase(typed), ext));
    return Promise.resolve(true);
  };
})();
