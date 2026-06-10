(function () {
  let observer = null;
  let scheduled = false;
  let rendering = false;

  function uniqBy(arr, keyFn) {
    const seen = new Set();
    const out = [];
    for (const x of arr) {
      const k = keyFn(x);
      if (!k || seen.has(k)) continue;
      seen.add(k);
      out.push(x);
    }
    return out;
  }

  function isVisible(el) {
    return !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  }

  function buildList(targetEl, items) {
    if (!targetEl) return;

    const ul = document.createElement("ul");
    for (const it of items || []) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = it.href;
      a.textContent = it.text;
      li.appendChild(a);
      ul.appendChild(li);
    }

    targetEl.innerHTML = "";
    if (!items || items.length === 0) {
      targetEl.innerHTML = "<p>Keine Einträge gefunden.</p>";
      return;
    }
    targetEl.appendChild(ul);
  }

  function getPrimaryNav() {
    // Material: Navigation steckt in der Primary Sidebar
    return document.querySelector(".md-sidebar--primary .md-nav--primary") ||
        document.querySelector(".md-nav--primary");
  }

  function getTopLevelLinks(nav) {
    const topList = nav?.querySelector(":scope > ul.md-nav__list");
    if (!topList) return [];

    const items = Array.from(topList.querySelectorAll(":scope > li.md-nav__item"));

    const out = items.map(li => {
      const directA = li.querySelector(":scope > a.md-nav__link[href]");
      if (directA && isVisible(directA)) {
        return { href: directA.getAttribute("href"), text: (directA.textContent || "").trim() };
      }

      const firstChildLink = li.querySelector("a.md-nav__link[href]");
      if (firstChildLink && isVisible(firstChildLink)) {
        const label = li.querySelector(":scope > label.md-nav__link, :scope > span.md-nav__link");
        const labelText = (label?.textContent || "").trim();
        const linkText = (firstChildLink.textContent || "").trim();

        return {
          href: firstChildLink.getAttribute("href"),
          text: labelText || linkText
        };
      }
      return null;
    })
        .filter(Boolean)
        .filter(x => x.href && x.text && !x.href.startsWith("#"));

    return uniqBy(out, x => x.href);
  }

  function findSectionContainer(nav) {
    const activeItem =
        nav?.querySelector("li.md-nav__item--active") ||
        nav?.querySelector("a.md-nav__link--active")?.closest("li.md-nav__item");

    if (!activeItem) return null;

    return (
        activeItem.querySelector(":scope > nav.md-nav") ||
        activeItem.querySelector(":scope > ul.md-nav__list") ||
        null
    );
  }

  function readLinks(container) {
    if (!container) return [];
    const links = Array.from(container.querySelectorAll('a.md-nav__link[href]'))
        .filter(isVisible)
        .map(a => ({ href: a.getAttribute("href"), text: (a.textContent || "").trim() }))
        .filter(x => x.href && x.text && !x.href.startsWith("#"));

    return uniqBy(links, x => x.href + "||" + x.text);
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }
  function normalizeLine(s) { return (s || "").replace(/\s+/g, " ").trim().toLowerCase(); }

  function runAll() {
    if (rendering) return;
    rendering = true;

    if (observer) observer.disconnect();

    try {
      const nav = getPrimaryNav();

      const siteToc = document.getElementById("site-toc");
      if (siteToc && nav) {
        buildList(siteToc, getTopLevelLinks(nav));
      }

      const sectionToc = document.getElementById("section-toc");
      if (sectionToc && nav) {
        const sectionContainer = findSectionContainer(nav);
        let links = readLinks(sectionContainer);

        // WICHTIG: relative href korrekt relativ zur aktuellen Seite auflösen
        const current = new URL(location.href).pathname.replace(/\/$/, "");
        links = links.filter(l => {
          try {
            const hrefPath = new URL(l.href, location.href).pathname.replace(/\/$/, "");
            return hrefPath !== current;
          } catch (_) {
            return true;
          }
        });

        buildList(sectionToc, links);
      }
    } finally {
      rendering = false;
      startObserver();
    }
  }

  function scheduleRun() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      runAll();
    });
  }

  function startObserver() {
    const target =
        document.querySelector(".md-container") ||
        document.querySelector(".md-main") ||
        document.body;

    if (!target) return;

    observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        const t = m.target;
        if (t && (t.id === "site-toc" || t.id === "section-toc" || t.closest?.("#site-toc, #section-toc"))) {
          continue;
        }
        scheduleRun();
        break;
      }
    });

    observer.observe(target, { childList: true, subtree: true });
  }

  // Material Instant Navigation
  (function attachMaterialHook() {
    const d$ = window.document$;
    if (d$ && typeof d$.subscribe === "function") {
      d$.subscribe(() => setTimeout(() => { try { runAll(); } catch (e) {} }, 0));
    }
  })();

  window.addEventListener("popstate", () => setTimeout(() => { try { runAll(); } catch (e) {} }, 0));
  window.addEventListener("hashchange", () => setTimeout(() => { try { runAll(); } catch (e) {} }, 0));

  // ✅ BOOTSTRAP: beim ersten Laden sofort starten
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => { startObserver(); runAll(); });
  } else {
    startObserver();
    runAll();
  }
})();
