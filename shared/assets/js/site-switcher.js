(function () {
    const AREAS = [
        { label: "Land", href: "../" },
        { label: "Allgemein", area: "allgemein" },
        { label: "Schaden", area: "schaden" },
        { label: "Betrieb", area: "betrieb" },
        { label: "Vertrieb", area: "vertrieb" },
        { label: "Buchhaltung", area: "buchhaltung" },
        { label: "Novas", area: "novas" },
        { label: "WTO", area: "wto" },
        { label: "Datenschutz", area: "datenschutz" },
        { label: "IT-FAQ", area: "it-faq" },
        { label: "Testumgebung", area: "testumgebung" }
    ];
    const COUNTRY_KEYS = new Set(["at", "de", "si", "it", "ro"]);

    function routeParts() {
        const parts = (location.pathname || "/").replace(/^\/+/, "").split("/").filter(Boolean);
        if (parts[0] === "site") return parts.slice(1);
        return parts;
    }

    function currentCountry() {
        const parts = routeParts();
        return COUNTRY_KEYS.has(parts[0]) ? parts[0] : "at";
    }

    function mount() {
        const actions = document.querySelector(".aw-actions");
        if (!actions) return;
        if (document.getElementById("asko-area-switcher")) return;

        const country = currentCountry();
        const prefix = location.pathname.replace(/^\/site\//, "/").startsWith(`/${country}/`) ? "" : "/site";
        const wrap = document.createElement("div");
        wrap.id = "asko-area-switcher";
        wrap.className = "aw-switcher";

        const select = document.createElement("select");
        select.className = "aw-switcher__select";
        select.setAttribute("aria-label", "Anderen Bereich wählen");

        const ph = document.createElement("option");
        ph.value = "";
        ph.textContent = "Anderen Bereich wählen";
        ph.selected = true;
        ph.disabled = true;
        select.appendChild(ph);

        const here = (location.pathname || "/").replace(/^\/site/, "").replace(/\/+$/, "") + "/";
        AREAS.forEach((item) => {
            const opt = document.createElement("option");
            const href = item.area ? `${prefix}/${country}/${item.area}/` : `${prefix}/${country}/`;
            const target = href.replace(/^\/site/, "").replace(/\/+$/, "") + "/";
            opt.value = href;
            opt.textContent = (target === here) ? `✓ ${item.label}` : item.label;
            select.appendChild(opt);
        });

        select.addEventListener("change", (e) => {
            const url = e.target.value;
            if (url) window.location.href = url;
        });

        wrap.appendChild(select);
        actions.insertBefore(wrap, actions.firstChild);
    }

    document.addEventListener("DOMContentLoaded", mount);
})();
