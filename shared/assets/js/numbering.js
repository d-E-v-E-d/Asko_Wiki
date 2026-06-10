(function () {
  const onReady = (fn) => (window.document$ ? window.document$.subscribe(fn) : document.addEventListener('DOMContentLoaded', fn));

  function getActiveTrail() {
    const navRoot = document.querySelector('[data-md-component="navigation"]');
    if (!navRoot) return [];
    const active = navRoot.querySelector('.md-nav__link[aria-current="page"]');
    if (!active) return [];
    const trail = [];
    let li = active.closest('.md-nav__item');
    while (li) {
      const siblings = Array.from(li.parentElement.children).filter((el) => el.matches('.md-nav__item'));
      trail.unshift(siblings.indexOf(li) + 1);
      li = li.parentElement.closest('.md-nav__item');
    }
    return trail;
  }

  function applyNumbers(pageNo) {
    const article = document.querySelector('article.md-content__inner');
    if (!article) return;
    // alte Nummern entfernen
    article.querySelectorAll('.aw-num').forEach(el => el.classList.remove('aw-num'));

    let c2 = 0, c3 = 0, c4 = 0;
    article.querySelectorAll('h1,h2,h3,h4').forEach((h) => {
      const tag = h.tagName;
      let num = null;
      if (tag === 'H1') { c2 = c3 = c4 = 0; num = pageNo; }
      else if (tag === 'H2') { c2++; c3 = c4 = 0; num = `${pageNo}.${c2}`; }
      else if (tag === 'H3') { c3++; c4 = 0; num = `${pageNo}.${c2}.${c3}`; }
      else if (tag === 'H4') { c4++; num = `${pageNo}.${c2}.${c3}.${c4}`; }
      if (num) { h.classList.add('aw-num'); h.setAttribute('data-num', num); }
    });
  }

  onReady(() => {
    const trail = getActiveTrail();
    if (!trail.length) return;
    applyNumbers(trail.join('.'));
  });
})();
