// docs/assets/js/nav-numbering.js
(function () {
  const onReady = (fn) => {
    if (window.document$) {
      document$.subscribe(fn);   // Material: bei jedem Seitenwechsel
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  };

  function clearOldNumbers(root) {
    // Alte Nummern entfernen (falls schon mal gelaufen)
    root.querySelectorAll(".aw-nav-num").forEach((el) => el.remove());
  }

  function renumberNav() {
    const primary = document.querySelector(
      '[data-md-component="navigation"] .md-nav--primary > ul'
    );
    if (!primary) return;

    clearOldNumbers(primary);

    // Rekursiv durch die Navigation laufen
    function walk(ul, prefix) {
      const items = Array.from(ul.children).filter((li) =>
        li.classList.contains("md-nav__item")
      );

      items.forEach((li, index) => {
        const currentIndex = index + 1;
        const level = prefix.length + 1;

        // neue Nummer
        const numArr =
          level <= 3 ? prefix.concat(currentIndex) : prefix.slice(0, 3);
        const numText = numArr.join(".");

        const link = li.querySelector(":scope > a.md-nav__link");
        if (link && level <= 3) {
          // Nummer einfügen
          const span = document.createElement("span");
          span.className = "aw-nav-num";
          span.textContent = numText + " ";
          link.insertBefore(span, link.firstChild);
        }

        // ggf. Kinder behandeln
        const subUl = li.querySelector(":scope > nav.md-nav > ul");
        if (subUl) {
          // Tiefer als 3 Ebenen wird nicht weiter hochgezählt,
          // aber die Struktur bleibt konsistent
          const nextPrefix = level <= 3 ? numArr : numArr.slice(0, 3);
          walk(subUl, nextPrefix);
        }
      });
    }

    walk(primary, []);
  }

  onReady(renumberNav);
})();
