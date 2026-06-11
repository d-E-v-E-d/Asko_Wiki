(function(){
  function ready(fn){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  function textOf(el){
    return (el && el.textContent ? el.textContent : '').replace(/\s+/g, ' ').trim();
  }

  function escapeHtml(value){
    return String(value || '').replace(/[&<>"']/g, function(ch){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
    });
  }

  function normalize(value){
    return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function makeExcerpt(text, query){
    const plain = String(text || '').replace(/\s+/g, ' ').trim();
    if(!plain) return '';
    const nText = normalize(plain);
    const nQuery = normalize(query);
    const at = nText.indexOf(nQuery);
    const start = at > 50 ? at - 50 : 0;
    const end = Math.min(plain.length, (at >= 0 ? at + nQuery.length + 90 : 150));
    let excerpt = plain.slice(start, end);
    if(start > 0) excerpt = '...' + excerpt;
    if(end < plain.length) excerpt += '...';
    if(!nQuery) return escapeHtml(excerpt);
    const parts = [];
    let rest = excerpt;
    let offset = start;
    while(rest.length){
      const idx = normalize(rest).indexOf(nQuery);
      if(idx < 0){ parts.push(escapeHtml(rest)); break; }
      parts.push(escapeHtml(rest.slice(0, idx)));
      parts.push('<mark>' + escapeHtml(rest.slice(idx, idx + query.length)) + '</mark>');
      rest = rest.slice(idx + query.length);
      offset += idx + query.length;
      if(offset > end) break;
    }
    return parts.join('');
  }


  function parseQuery(query){
    const raw = String(query || '').trim();
    const quoted = raw.match(/^"(.+)"$/);
    if(quoted && quoted[1].trim()){
      return { mode: 'phrase', values: [normalize(quoted[1].trim())] };
    }
    if(raw.includes('+')){
      const values = raw.split('+').map(function(part){ return normalize(part.trim()); }).filter(Boolean);
      if(values.length > 1) return { mode: 'and', values: values };
    }
    return { mode: 'plain', values: [normalize(raw)] };
  }

  function matchesQuery(doc, parsed){
    const haystack = normalize(doc.title + ' ' + doc.text + ' ' + doc.area);
    if(parsed.mode === 'and'){
      return parsed.values.every(function(value){ return haystack.includes(value); });
    }
    return haystack.includes(parsed.values[0]);
  }

  const COUNTRIES = [
    { code: 'at', label: 'Österreich' },
    { code: 'de', label: 'Deutschland' },
    { code: 'si', label: 'Slowenien' },
    { code: 'it', label: 'Italien' },
    { code: 'ro', label: 'Rumänien' }
  ];

  function currentCountryCode(){
    const parts = window.location.pathname.split('/').filter(Boolean);
    const siteIndex = parts.indexOf('site');
    const candidate = siteIndex >= 0 ? parts[siteIndex + 1] : parts[0];
    return COUNTRIES.some(function(country){ return country.code === candidate; }) ? candidate : '';
  }

  function portalBaseUrl(){
    const base = new URL('../', window.location.href);
    return base.href;
  }

  function countryUrl(code){
    return new URL(code + '/', portalBaseUrl()).href;
  }

  function addCountryNav(header){
    if(!header || header.querySelector('.asko-country-nav')) return;
    const current = currentCountryCode();
    const nav = document.createElement('div');
    nav.className = 'asko-country-nav';
    nav.innerHTML = '<select id=\"askoCountrySelect\" class=\"asko-country-select\" aria-label=\"Land auswählen\" title=\"Land auswählen\">' +
      COUNTRIES.map(function(country){
        return '<option value="' + country.code + '"' + (country.code === current ? ' selected' : '') + '>' + escapeHtml(country.label) + '</option>';
      }).join('') +
      '</select>' +
      '<button class="asko-country-portal-btn" type="button">Zum Portal</button>';
    header.appendChild(nav);
    nav.querySelector('select').addEventListener('change', function(event){
      window.location.assign(countryUrl(event.target.value));
    });
    nav.querySelector('button').addEventListener('click', function(){
      window.location.assign(portalBaseUrl());
    });
  }
  async function loadIndexes(areas){
    const loaded = [];
    await Promise.all(areas.map(async function(area){
      try{
        const base = new URL(area.href, window.location.href);
        const indexUrl = new URL('search/search_index.json', base);
        const response = await fetch(indexUrl.href, { credentials: 'same-origin' });
        if(!response.ok) return;
        const payload = await response.json();
        const docs = Array.isArray(payload.docs) ? payload.docs : [];
        docs.forEach(function(doc){
          loaded.push({
            area: area.label,
            title: doc.title || area.label,
            text: doc.text || '',
            location: new URL(doc.location || '', base).href
          });
        });
      }catch(err){
        console.warn('Portal-Suche: Index konnte nicht geladen werden', area.label, err);
      }
    }));
    return loaded;
  }

  ready(function(){
    const page = document.querySelector('.asko-page');
    if(!page) return;
    document.body.classList.add('asko-portal');
    const countryCode = currentCountryCode();
    if(countryCode) document.body.classList.add('asko-country-' + countryCode);

    document.querySelectorAll('.asko-tile[href]').forEach(function(tile){
      tile.addEventListener('click', function(event){
        if(event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const href = tile.getAttribute('href');
        if(!href) return;
        event.preventDefault();
        window.location.assign(new URL(href, window.location.href).href);
      });
    });

    const header = document.querySelector('.md-header__inner');
    addCountryNav(header);
    const tiles = Array.from(document.querySelectorAll('.asko-tile[href]'));
    let searchableTiles = tiles.filter(function(tile){ return !tile.classList.contains('asko-tile--testumgebung'); });
    if(!searchableTiles.length) searchableTiles = tiles;
    const areas = searchableTiles
      .map(function(tile){ return { label: textOf(tile), href: tile.getAttribute('href') }; })
      .filter(function(area){ return area.label && area.href; });
    if(!header || !areas.length) return;

    const box = document.createElement('div');
    box.className = 'asko-portal-search';
    box.innerHTML = '<div class="asko-portal-search-field">' +
      '<input id="askoPortalSearch" type="search" autocomplete="off" placeholder="Suche" aria-label="Portal durchsuchen">' +
      '<button class="asko-portal-search-help" type="button" aria-label="Suchtipps">?</button>' +
      '<div class="asko-portal-search-tooltip" role="tooltip">' +
      '<strong>Suchtipps</strong>' +
      '<span><code>schaden+anzeige</code> findet Seiten, die beide Wörter enthalten.</span>' +
      '<span><code>&quot;schaden anzeige&quot;</code> sucht genau diesen zusammenhängenden Begriff.</span>' +
      '<span>Ohne Sonderzeichen wird der eingegebene Text gesucht.</span>' +
      '</div>' +
      '</div>' +
      '<div class="asko-portal-search-results" hidden><div class="asko-portal-search-note">Suchindex wird geladen...</div></div>';
    header.appendChild(box);

    const input = box.querySelector('input');
    const results = box.querySelector('.asko-portal-search-results');
    let docs = [];
    let loaded = false;

    const ensureLoaded = async function(){
      if(loaded) return;
      loaded = true;
      docs = await loadIndexes(areas);
    };

    const render = function(){
      const q = input.value.trim();
      if(q.length < 2){
        results.hidden = true;
        results.innerHTML = '';
        return;
      }
      const parsedQuery = parseQuery(q);
      const allFound = docs.filter(function(doc){
        return matchesQuery(doc, parsedQuery);
      });
      const shown = allFound.slice(0, 80);
      results.hidden = false;
      if(!allFound.length){
        results.innerHTML = '<div class="asko-portal-search-note">Keine Treffer gefunden.</div>';
        return;
      }
      const summary = '<div class="asko-portal-search-summary">' + shown.length + ' von ' + allFound.length + ' Treffern angezeigt</div>';
      results.innerHTML = summary + shown.map(function(doc){
        return '<a class="asko-portal-search-hit" href="' + escapeHtml(doc.location) + '">' +
          '<span class="asko-portal-search-area">' + escapeHtml(doc.area) + '</span>' +
          '<span class="asko-portal-search-body"><strong>' + escapeHtml(doc.title) + '</strong><small>' + makeExcerpt(doc.text, q) + '</small></span>' +
          '</a>';
      }).join('');
    };

    input.addEventListener('focus', async function(){
      await ensureLoaded();
      render();
    });
    input.addEventListener('input', async function(){
      await ensureLoaded();
      render();
    });
    document.addEventListener('click', function(event){
      if(!box.contains(event.target)) results.hidden = true;
    });
    input.addEventListener('keydown', function(event){
      if(event.key === 'Escape') results.hidden = true;
    });
  });
})();







