(function () {
  // MkDocs Material: bei jedem Seitenwechsel ausführen
  const onReady = (fn) =>
    window.document$
      ? document$.subscribe(fn)
      : document.addEventListener("DOMContentLoaded", fn);

  function numberHeadings() {
    const article =
      document.querySelector("article.md-content__inner") ||
      document.querySelector("article");
    if (!article) return;

    // Alte Nummern zurücksetzen
    article.querySelectorAll("h1,h2").forEach((h) => {
      h.classList.remove("aw-num");
      h.removeAttribute("data-num");
    });

    let c1 = 0;
    let c2 = 0;

    article.querySelectorAll("h1,h2").forEach((h) => {
      if (h.tagName === "H1") {
        c1 += 1;
        c2 = 0;
        h.classList.add("aw-num");
        h.setAttribute("data-num", String(c1));
      } else {
        // H2
        if (c1 === 0) c1 = 1; // falls Seite nur mit H2 beginnt
        c2 += 1;
        h.classList.add("aw-num");
        h.setAttribute("data-num", c1 + "." + c2);
      }
    });
  }

  onReady(numberHeadings);
})();
