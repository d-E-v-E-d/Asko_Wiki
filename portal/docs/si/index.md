<!-- ASKO Wiki Länderportal: Slowenien -->
<div class="asko-page">
  <header class="asko-portal-header">
    <div class="asko-portal-header-inner">
      <img src="../assets/img/logo.svg" alt="ASKO Logo" class="asko-logo">
      <div class="asko-portal-titlewrap">
        <h1 class="asko-portal-title">Slowenien</h1>
        <div class="asko-portal-greeting">Bitte wählen Sie einen Bereich aus, um fortzufahren.</div>
      </div>
    </div>
  </header>
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
  document.addEventListener("DOMContentLoaded", () => {
    if (document.querySelector(".asko-page")) document.body.classList.add("asko-portal");
    document.querySelectorAll(".asko-tile[href]").forEach((tile) => {
      tile.addEventListener("click", (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const href = tile.getAttribute("href");
        if (!href) return;
        event.preventDefault();
        window.location.assign(new URL(href, window.location.href).href);
      });
    });
  });
</script>

<style>
  body.asko-portal{
    --asko-teal:#16b9a6;
    --asko-teal-dark:#0ea58f;
    --asko-ink:#0f172a;
    --asko-muted:#475569;
    --asko-border:rgba(255,255,255,.38);
  }
  body.asko-portal .md-header{background:linear-gradient(90deg,var(--asko-teal),var(--asko-teal-dark))!important;}
  body.asko-portal .md-tabs{background:var(--asko-teal-dark)!important;}
  body.asko-portal .md-content__inner{margin:0;max-width:none;}
  body.asko-portal .md-content__inner:before{display:none;}
  body.asko-portal .md-sidebar{display:none!important;}
  body.asko-portal .md-main__inner{margin:0;max-width:none;}
  body.asko-portal .md-content{margin:0;}
  body.asko-portal .asko-page{min-height:calc(100vh - 64px);background:linear-gradient(180deg,#f8fafc 0%,#eef8f6 100%);}
  body.asko-portal .asko-portal-header{padding:42px 24px 22px;}
  body.asko-portal .asko-portal-header-inner{width:min(1120px,100%);margin:0 auto;display:flex;gap:22px;align-items:center;}
  body.asko-portal .asko-logo{width:86px;height:auto;display:block;}
  body.asko-portal .asko-portal-title{margin:0;color:var(--asko-ink);font-size:clamp(1.8rem,3vw,3rem);letter-spacing:0;}
  body.asko-portal .asko-portal-greeting{margin-top:8px;color:var(--asko-muted);font-size:1rem;line-height:1.5;}
  body.asko-portal .asko-landing{padding:18px 24px 58px;}
  body.asko-portal .asko-tiles__inner{width:min(1120px,100%);margin:0 auto;}
  body.asko-portal .asko-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;}
  body.asko-portal .asko-tile{min-height:112px;padding:18px 20px;border-radius:8px;border:1px solid rgba(14,165,143,.28);background:rgba(255,255,255,.78);box-shadow:0 10px 28px rgba(15,23,42,.08);display:flex;align-items:center;justify-content:center;text-align:center;color:var(--asko-ink);text-decoration:none;transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease,background .15s ease;}
  body.asko-portal .asko-tile:hover{transform:translateY(-2px);box-shadow:0 16px 34px rgba(15,23,42,.12);border-color:rgba(14,165,143,.58);background:#fff;}
  body.asko-portal .asko-tile--testumgebung{background:rgba(220,38,38,.10);border-color:rgba(220,38,38,.32);}
  body.asko-portal .asko-tile--testumgebung:hover{background:rgba(220,38,38,.16);border-color:rgba(220,38,38,.55);}
  body.asko-portal .asko-tile__label{font-weight:700;font-size:1.05rem;line-height:1.25;overflow-wrap:anywhere;}
  @media (max-width:700px){body.asko-portal .asko-portal-header-inner{align-items:flex-start}.asko-logo{width:72px}.asko-grid{grid-template-columns:1fr}}
</style>
