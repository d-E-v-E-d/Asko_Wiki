<!-- portal/index.md (oder index.md) – ASKO Arbeitsanweisungen Portal -->

<!-- ASKO Arbeitsanweisungen – Portal -->
<div class="asko-page">

  <!-- Kopfbereich (außerhalb der Kacheln) -->
  <header class="asko-portal-header">
    <div class="asko-portal-header-inner">
      <img src="assets/img/logo.svg" alt="ASKO Logo" class="asko-logo">
      <div class="asko-portal-titlewrap">
        <h1 class="asko-portal-title">Arbeitsanweisungen Portal</h1>
        <div class="asko-portal-greeting">
          Willkommen im Arbeitsanweisungs-Portal der ASKO.<br>
          Bitte wählen Sie einen Bereich aus, um fortzufahren.
        </div>
      </div>
    </div>
  </header>

  <!-- Kachelbereich (nur Kacheln) -->
  <section class="asko-landing">
    <div class="asko-tiles__inner">
      <div class="asko-grid" role="list">
        <a class="asko-tile" href="./allgemein/" role="listitem"><span class="asko-tile__label">Allgemein</span></a>
        <a class="asko-tile" href="./schaden/" role="listitem"><span class="asko-tile__label">Schaden</span></a>
        <a class="asko-tile" href="./betrieb/" role="listitem"><span class="asko-tile__label">Betrieb</span></a>
        <a class="asko-tile" href="./vertrieb/" role="listitem"><span class="asko-tile__label">Vertrieb</span></a>
        <a class="asko-tile" href="./buchhaltung/" role="listitem"><span class="asko-tile__label">Buchhaltung</span></a>
        <a class="asko-tile" href="./novas/" role="listitem"><span class="asko-tile__label">Novas</span></a>
        <a class="asko-tile" href="./wto/" role="listitem"><span class="asko-tile__label">Warentransportversicherung-Online</span></a>
        <a class="asko-tile" href="./datenschutz/" role="listitem"><span class="asko-tile__label">Datenschutz</span></a>
        <a class="asko-tile" href="./it-faq/" role="listitem"><span class="asko-tile__label">IT-FAQ</span></a>
        <a class="asko-tile asko-tile--testumgebung" href="./testumgebung/" role="listitem"><span class="asko-tile__label">Testumgebung</span></a>
      </div>
    </div>
  </section>

</div>

<script>
  // Portal-only: Body-Klasse setzen (ohne :has(), ohne doppelten Script-Block)
  document.addEventListener("DOMContentLoaded", () => {
    if (document.querySelector(".asko-page")) {
      document.body.classList.add("asko-portal");
    }

    const headerInner = document.querySelector(".md-header__inner");
    if (headerInner && !document.getElementById("askoPortalSearch")) {
      const searchBox = document.createElement("div");
      searchBox.className = "asko-portal-search";
      searchBox.setAttribute("role", "search");
      searchBox.innerHTML = `
        <label class="asko-portal-search__label" for="askoPortalSearch">Suche</label>
        <input id="askoPortalSearch" class="asko-portal-search__input" type="search" autocomplete="off" placeholder="Alle Bereiche durchsuchen ...">
        <div id="askoPortalSearchStatus" class="asko-portal-search__status">Durchsucht alle Bereiche außer Testumgebung.</div>
        <div id="askoPortalSearchResults" class="asko-portal-search__results" hidden></div>
      `;
      headerInner.appendChild(searchBox);
    }

    const input = document.getElementById("askoPortalSearch");
    const resultsEl = document.getElementById("askoPortalSearchResults");
    const statusEl = document.getElementById("askoPortalSearchStatus");
    if (!input || !resultsEl || !statusEl) return;

    document.querySelectorAll(".asko-tile[href]").forEach((tile) => {
      tile.addEventListener("click", (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const href = tile.getAttribute("href");
        if (!href) return;
        event.preventDefault();
        window.location.assign(new URL(href, window.location.href).href);
      });
    });

    const areas = [
      { id: "allgemein", label: "Allgemein" },
      { id: "schaden", label: "Schaden" },
      { id: "betrieb", label: "Betrieb" },
      { id: "vertrieb", label: "Vertrieb" },
      { id: "buchhaltung", label: "Buchhaltung" },
      { id: "novas", label: "Novas" },
      { id: "wto", label: "Warentransportversicherung-Online" },
      { id: "datenschutz", label: "Datenschutz" },
      { id: "it-faq", label: "IT-FAQ" }
    ];
    let docsPromise = null;

    const cleanText = (value) => String(value || "")
      .replace(/<[^>]*>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const normalize = (value) => cleanText(value).toLocaleLowerCase("de-AT");
    const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#039;"
    }[ch]));

    async function loadDocs() {
      if (docsPromise) return docsPromise;
      docsPromise = Promise.all(areas.map(async (area) => {
        try {
          const res = await fetch(`./${area.id}/search/search_index.json`, { cache: "force-cache" });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          return (data.docs || []).map((doc) => ({
            area,
            location: String(doc.location || ""),
            title: cleanText(doc.title) || "Ohne Titel",
            text: cleanText(doc.text)
          }));
        } catch (err) {
          console.warn("Portal-Suche konnte Bereich nicht laden:", area.id, err);
          return [];
        }
      })).then((groups) => groups.flat());
      return docsPromise;
    }

    function makeHref(doc) {
      const location = doc.location.replace(/^\/+/, "");
      return `./${doc.area.id}/${location}`;
    }

    function scoreDoc(doc, terms) {
      const title = normalize(doc.title);
      const path = normalize(decodeURIComponent(doc.location || ""));
      const area = normalize(doc.area.label);
      const text = normalize(doc.text);
      if (!terms.every((term) => area.includes(term) || title.includes(term) || path.includes(term) || text.includes(term))) {
        return 0;
      }
      return terms.reduce((score, term) => {
        if (area.includes(term)) score += 12;
        if (title.includes(term)) score += 10;
        if (path.includes(term)) score += 4;
        if (text.includes(term)) score += 1;
        return score;
      }, 0);
    }

    function makeSnippet(doc, terms) {
      const sources = [
        cleanText(doc.text),
        cleanText(doc.title),
        decodeURIComponent(doc.location || "")
      ].filter(Boolean);
      for (const source of sources) {
        const lower = source.toLocaleLowerCase("de-AT");
        const hit = terms.map((term) => lower.indexOf(term)).filter((idx) => idx >= 0).sort((a, b) => a - b)[0];
        if (hit == null) continue;
        const start = Math.max(0, hit - 58);
        const end = Math.min(source.length, hit + 122);
        return `${start > 0 ? "..." : ""}${source.slice(start, end)}${end < source.length ? "..." : ""}`;
      }
      return cleanText(doc.text).slice(0, 160);
    }

    function highlightTerms(value, terms) {
      const text = String(value || "");
      const lower = text.toLocaleLowerCase("de-AT");
      let pos = 0;
      let html = "";
      while (pos < text.length) {
        let best = null;
        for (const term of terms) {
          const idx = lower.indexOf(term, pos);
          if (idx < 0) continue;
          if (!best || idx < best.idx || (idx === best.idx && term.length > best.term.length)) {
            best = { idx, term };
          }
        }
        if (!best) {
          html += escapeHtml(text.slice(pos));
          break;
        }
        html += escapeHtml(text.slice(pos, best.idx));
        html += `<mark>${escapeHtml(text.slice(best.idx, best.idx + best.term.length))}</mark>`;
        pos = best.idx + best.term.length;
      }
      return html;
    }

    async function runSearch() {
      const query = input.value.trim();
      if (query.length < 2) {
        resultsEl.hidden = true;
        resultsEl.innerHTML = "";
        statusEl.textContent = "Mindestens 2 Zeichen eingeben.";
        return;
      }

      statusEl.textContent = "Suche läuft ...";
      const terms = normalize(query).split(/\s+/).filter(Boolean);
      const docs = await loadDocs();
      const matches = docs
        .map((doc) => ({ doc, score: scoreDoc(doc, terms) }))
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score || a.doc.title.localeCompare(b.doc.title, "de-AT"))
        .slice(0, 30);

      if (!matches.length) {
        resultsEl.hidden = false;
        resultsEl.innerHTML = '<div class="asko-portal-search__empty">Keine Treffer gefunden.</div>';
        statusEl.textContent = "0 Treffer";
        return;
      }

      resultsEl.hidden = false;
      resultsEl.innerHTML = matches.map(({ doc }) => {
        const path = decodeURIComponent(doc.location || "").replace(/\/$/, "") || "Startseite";
        const snippet = makeSnippet(doc, terms);
        return `
          <a class="asko-portal-search__result" href="${escapeHtml(makeHref(doc))}">
            <span class="asko-portal-search__area">${escapeHtml(doc.area.label)}</span>
            <span class="asko-portal-search__title">${highlightTerms(doc.title, terms)}</span>
            <span class="asko-portal-search__path">${escapeHtml(path)}</span>
            <span class="asko-portal-search__snippet">${highlightTerms(snippet, terms)}</span>
          </a>
        `;
      }).join("");
      statusEl.textContent = `${matches.length} Treffer`;
    }

    let searchTimer = null;
    input.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(runSearch, 180);
    });
    input.addEventListener("focus", () => {
      if (input.value.trim().length >= 2 && resultsEl.innerHTML.trim()) {
        resultsEl.hidden = false;
      }
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".asko-portal-search")) {
        resultsEl.hidden = true;
      }
    });
  });
</script>

<style>
  /* ===== Portal Scope über Body-Klasse ===== */
  body.asko-portal{
    --asko-teal:#16b9a6;
    --asko-teal-dark:#0ea58f;
    --asko-ink:#0f172a;
    --asko-border:rgba(255,255,255,.35);
  }

  /* ===== MkDocs Header oben (der blaue) -> grün ===== */
  body.asko-portal .md-header{
    background: linear-gradient(90deg, var(--asko-teal), var(--asko-teal-dark)) !important;
  }

  /* Tabs-Leiste (falls aktiv) ebenfalls grün */
  body.asko-portal .md-tabs{
    background: linear-gradient(90deg, var(--asko-teal), var(--asko-teal-dark)) !important;
  }

  /* ===== Navigation nur im Portal ausblenden ===== */
  body.asko-portal .md-sidebar--primary,
  body.asko-portal .md-sidebar--secondary{
    display:none !important;
  }

  /* Content ohne Sidebars sauber */
  body.asko-portal .md-main__inner{
    margin-left:auto !important;
    margin-right:auto !important;
  }
  @media (min-width: 76.25em){
    body.asko-portal .md-main__inner{
      max-width:1100px;
    }
  }

  /* Seitenkopf im Content ausblenden (Landing clean) */
  body.asko-portal .md-content__inner > header{
    display:none !important;
  }

  /* ===== Portal Header (Content) – weiß, sauber, Greeting außerhalb der Kacheln ===== */
  body.asko-portal .asko-portal-header{
    background:#ffffff;
    padding: 26px 18px 18px;
  }

body.asko-portal .asko-portal-header-inner{
  max-width:1100px;
  margin:0 auto;
  display:flex;
  flex-direction:column;     /* Logo oben */
  align-items:center;        /* horizontal zentriert */
  text-align:center;
  gap:14px;
}

body.asko-portal .asko-logo{
  height:42px;               /* kleiner */
  width:auto;
  display:block;
}

body.asko-portal .asko-portal-title{
  margin:0;
  font-size:36px;            /* etwas größer */
  font-weight:900;
  color:var(--asko-ink);
  letter-spacing:-0.02em;
}

body.asko-portal .asko-portal-greeting{
  max-width:720px;
  margin-top:6px;
  font-size:16px;
  color:#475569;
  line-height:1.5;
}

body.asko-portal .asko-portal-search{
  width:min(680px, 56vw);
  margin-left:auto;
  position:relative;
  flex:0 1 680px;
  text-align:left;
  z-index:5;
}

body.asko-portal .asko-portal-search__label{
  position:absolute;
  width:1px;
  height:1px;
  padding:0;
  margin:-1px;
  overflow:hidden;
  clip:rect(0,0,0,0);
  border:0;
}

body.asko-portal .asko-portal-search__input{
  width:100%;
  min-height:36px;
  border:1px solid rgba(255,255,255,.55);
  border-radius:4px;
  padding:7px 10px;
  font:inherit;
  color:#0f172a;
  background:rgba(255,255,255,.96);
  box-shadow:0 1px 2px rgba(15,23,42,.12);
}

body.asko-portal .asko-portal-search__input:focus{
  outline:2px solid rgba(255,255,255,.65);
  border-color:#fff;
}

body.asko-portal .asko-portal-search__status{
  display:none;
}

body.asko-portal .asko-portal-search__results{
  position:absolute;
  top:calc(100% + 6px);
  left:0;
  right:0;
  margin-top:0;
  border:1px solid #e2e8f0;
  border-radius:6px;
  max-height:min(62vh, 520px);
  overflow-y:auto;
  overflow-x:hidden;
  background:#fff;
  box-shadow:0 10px 28px rgba(15,23,42,.10);
}

body.asko-portal .asko-portal-search__result{
  display:grid;
  grid-template-columns:135px minmax(0, 1fr);
  gap:4px 12px;
  padding:10px 12px;
  color:#0f172a;
  text-decoration:none;
  border-top:1px solid #e2e8f0;
}

body.asko-portal .asko-portal-search__result:first-child{
  border-top:0;
}

body.asko-portal .asko-portal-search__result:hover{
  background:#f8fafc;
}

body.asko-portal .asko-portal-search__area{
  grid-row:span 3;
  color:#0f766e;
  font-size:13px;
  font-weight:900;
  min-width:0;
  overflow-wrap:anywhere;
  hyphens:auto;
  line-height:1.25;
}

body.asko-portal .asko-portal-search__title{
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-weight:800;
}

body.asko-portal .asko-portal-search__path{
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  color:#64748b;
  font-size:13px;
}

body.asko-portal .asko-portal-search__snippet{
  min-width:0;
  color:#334155;
  font-size:12px;
  line-height:1.35;
}

body.asko-portal .asko-portal-search mark{
  background:#fde68a;
  color:#111827;
  padding:0 .08em;
}

body.asko-portal .asko-portal-search__empty{
  padding:12px;
  color:#64748b;
  font-size:14px;
}


body.asko-portal .asko-logo{
  height:42px;               /* kleiner */
  width:auto;
  display:block;
}

body.asko-portal .asko-portal-title{
  margin:0;
  font-size:36px;            /* etwas größer */
  font-weight:900;
  color:var(--asko-ink);
  letter-spacing:-0.02em;
}

body.asko-portal .asko-portal-greeting{
  max-width:720px;
  margin-top:6px;
  font-size:16px;
  color:#475569;
  line-height:1.5;
}


  body.asko-portal .asko-logo{
    height:56px;
    width:auto;
    display:block;
  }

  body.asko-portal .asko-portal-titlewrap{
    display:flex;
    flex-direction:column;
    text-align:center;
    gap:6px;
  }

  body.asko-portal .asko-portal-title{
    margin:0;
    font-size:28px;
    font-weight:900;
    color:var(--asko-ink);
    letter-spacing:-0.02em;
  }

  body.asko-portal .asko-portal-greeting{
    color:#475569;
    font-size:15px;
    line-height:1.5;
  }

  /* ===== Landing + Kacheln ===== */
  body.asko-portal .asko-landing{
    background: linear-gradient(180deg, var(--asko-teal) 0%, var(--asko-teal-dark) 100%);
    padding:26px 0 46px;
  }

  body.asko-portal .asko-tiles__inner{
    max-width:1100px;
    margin:0 auto;
    padding:0 18px;
  }

  body.asko-portal .asko-grid{
    display:grid;
    grid-template-columns:repeat(4, minmax(0, 1fr));
    gap:18px;
  }

  body.asko-portal .asko-tile{
    min-height:92px;
    padding:18px;
    border:2px solid var(--asko-border);
    background:rgba(0,0,0,.06);
    color:#fff;
    text-decoration:none;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    transition:transform .12s ease, background .12s ease, border-color .12s ease;
  }

  body.asko-portal .asko-tile:hover{
    transform:translateY(-2px);
    background:rgba(0,0,0,.10);
    border-color:rgba(255,255,255,.6);
  }

  body.asko-portal .asko-tile--testumgebung{
    background:#fee2e2;
    border-color:#f87171;
    color:#7f1d1d;
  }

  body.asko-portal .asko-tile--testumgebung:hover{
    background:#fecaca;
    border-color:#ef4444;
  }

  body.asko-portal .asko-tile__label{
    font-weight:900;
    font-size:16px;
    letter-spacing:-.02em;
    line-height:1.2;
  }

  /* Responsive */
  @media (max-width:980px){
    body.asko-portal .asko-grid{ grid-template-columns:repeat(2, 1fr); }
  }
  @media (max-width:520px){
    body.asko-portal .asko-portal-header-inner{
      flex-direction:column;
      text-align:center;
    }
    body.asko-portal .asko-grid{ grid-template-columns:1fr; }
    body.asko-portal .asko-portal-search{
      width:100%;
      flex:1 1 100%;
      order:20;
      margin:6px 0 0;
    }
    body.asko-portal .asko-portal-search__result{
      grid-template-columns:1fr;
    }
    body.asko-portal .asko-portal-search__area{
      grid-row:auto;
    }
  }

  /* Footer im Portal komplett ausblenden */
  body.asko-portal .md-footer{
    display:none !important;
  }

  /* Optional: damit unten kein leerer Abstand bleibt */
  body.asko-portal .md-container{
    padding-bottom:0 !important;
  }
</style>
