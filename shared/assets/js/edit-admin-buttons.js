(function () {
  const PUBLISH_SIGNAL_KEY = "asko:publish-refresh";

  const onReady = (fn) =>
      window.document$
          ? window.document$.subscribe(fn)
          : document.addEventListener("DOMContentLoaded", fn);

  function getSrcPath() {
    const m = document.querySelector('meta[name="mkdocs-src-path"]');
    return m ? m.getAttribute("content") : null;
  }

  function pathToMd(p) {
    p = (p || "").replace(/^\/+/, "");
    if (p === "" || p.endsWith("/")) p += "index.html";
    return p.replace(/index\.html$/i, "index.md").replace(/\.html$/i, ".md");
  }

  function inferSite() {
    const parts = (window.location.pathname || "")
      .replace(/\\/g, "/")
      .replace(/^\/+/, "")
      .split("/")
      .filter(Boolean);

    if (parts[0] === "site" && parts[1]) return parts[1];
    return parts[0] || "schaden";
  }

  function signalMatchesCurrentSite(signal) {
    if (!signal || typeof signal !== "object") return false;
    const targetSite = String(signal.site || "").trim().toLowerCase();
    if (!targetSite || targetSite === "all") return true;
    return targetSite === inferSite().toLowerCase();
  }

  function reloadWithCacheBuster(signal) {
    if (!signalMatchesCurrentSite(signal)) return;
    const token = String(signal.ts || Date.now());
    const url = new URL(window.location.href);
    if (url.searchParams.get("aw_refresh") === token) return;
    url.searchParams.set("aw_refresh", token);
    window.location.replace(url.toString());
  }

  window.addEventListener("storage", (event) => {
    if (event.key !== PUBLISH_SIGNAL_KEY || !event.newValue) return;
    try {
      reloadWithCacheBuster(JSON.parse(event.newValue));
    } catch (_) {}
  });

  function buildEditorHref() {
    const mdPath = getSrcPath() || pathToMd(window.location.pathname);
    const site = inferSite();
    return `/static/editor/editor.html?site=${encodeURIComponent(site)}&file=${encodeURIComponent(mdPath)}`;
  }

  onReady(() => {
    const actions = document.querySelector('[data-aw="actions"]');
    const btnEdit = document.getElementById("aw-edit");
    const btnAdmin = document.getElementById("aw-admin");
    if (!actions || !btnEdit || !btnAdmin) return;

    const refreshTargets = () => {
      btnEdit.href = buildEditorHref();
      btnAdmin.href = `/static/admin/admin.html`;
      actions.hidden = false;
    };

    refreshTargets();
    btnEdit.addEventListener("click", refreshTargets, true);
    btnEdit.addEventListener("mouseenter", refreshTargets);
    btnEdit.addEventListener("focus", refreshTargets);
  });
})();
