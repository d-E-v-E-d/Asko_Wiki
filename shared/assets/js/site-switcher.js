(function () {
    const LINKS = [
        { label: "Portal", href: "/" },
        { label: "Allgemein", href: "/allgemein/" },
        { label: "Schaden", href: "/schaden/" },
        { label: "Betrieb", href: "/betrieb/" },
        { label: "Vertrieb", href: "/vertrieb/" },
        { label: "Buchhaltung", href: "/buchhaltung/" },
        { label: "Novas", href: "/novas/" },
        { label: "WTO", href: "/wto/" },
        { label: "Datenschutz", href: "/datenschutz/" },
        { label: "IT-FAQ", href: "/it-faq/" },
        { label: "Testumgebung", href: "/testumgebung/" }
    ];

    function mount() {
        // Ziel: links neben Bearbeiten/Admin (aw-actions)
        const actions = document.querySelector(".aw-actions");
        if (!actions) return;

        if (document.getElementById("asko-area-switcher")) return;

        const wrap = document.createElement("div");
        wrap.id = "asko-area-switcher";
        wrap.className = "aw-switcher"; // styling wie aw-btn

        const select = document.createElement("select");
        select.className = "aw-switcher__select";
        select.setAttribute("aria-label", "Anderen Bereich wählen");

        const ph = document.createElement("option");
        ph.value = "";
        ph.textContent = "Anderen Bereich wählen";
        ph.selected = true;
        ph.disabled = true;
        select.appendChild(ph);

        // optional: current markieren (best-effort)
        const here = (location.pathname || "/").replace(/\/+$/, "") + "/";
        LINKS.forEach((l) => {
            const opt = document.createElement("option");
            const target = (l.href || "/").replace(/\/+$/, "") + "/";
            opt.value = l.href;
            opt.textContent = (target === here) ? `✓ ${l.label}` : l.label;
            select.appendChild(opt);
        });

        select.addEventListener("change", (e) => {
            const url = e.target.value;
            if (url) window.location.href = url;
        });

        wrap.appendChild(select);

        // links einfügen (vor Bearbeiten/Admin)
        actions.insertBefore(wrap, actions.firstChild);
    }

    document.addEventListener("DOMContentLoaded", mount);
})();
