(function () {
  const onReady = (fn) =>
    window.document$ ? document$.subscribe(fn) : document.addEventListener('DOMContentLoaded', fn);

  function getBackendBase() {
    const m = document.querySelector('meta[name="mkdocs-backend-base"]');
    return m ? m.getAttribute('content') : '';
  }

  async function loadLastChange() {
    const metaFile = document.querySelector('meta[name="mkdocs-src-path"]');
    const target = document.getElementById('aw-last-change');
    if (!metaFile || !target) return;

    const file = metaFile.getAttribute('content');
    const BASE = getBackendBase();

    try {
      const res = await fetch(`${BASE}/meta/last_change?file=${encodeURIComponent(file)}`, {
        credentials: 'include'
      });

      if (!res.ok) {
        // 404 = keine Info -> einfach leise ignorieren
        if (res.status === 404) return;
        const txt = await res.text();
        console.warn('last_change failed', res.status, txt);
        return;
      }

      const data = await res.json();
      const ts = data.timestamp || '';
      const user = data.user || 'unbekannt';

      target.textContent = `– Zuletzt geändert: ${ts} durch ${user}`;
    } catch (e) {
      console.warn('last_change error', e);
    }
  }

  onReady(loadLastChange);
})();
