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
    --asko-border:rgba(255,255,255,.35);
  }

  body.asko-portal .md-header{
    background:linear-gradient(90deg,var(--asko-teal),var(--asko-teal-dark))!important;
  }
  body.asko-portal .md-tabs{
    background:linear-gradient(90deg,var(--asko-teal),var(--asko-teal-dark))!important;
  }
  body.asko-portal .md-sidebar--primary,
  body.asko-portal .md-sidebar--secondary{
    display:none!important;
  }
  body.asko-portal .md-main__inner{
    margin-left:auto!important;
    margin-right:auto!important;
  }
  @media (min-width:76.25em){
    body.asko-portal .md-main__inner{max-width:1100px;}
  }
  body.asko-portal .md-content__inner>header{display:none!important;}
  body.asko-portal .md-content__inner{margin:0;}
  body.asko-portal .md-content__inner:before{display:none;}

  body.asko-portal .asko-portal-header{
    background:#fff;
    padding:26px 18px 18px;
  }
  body.asko-portal .asko-portal-header-inner{
    max-width:1100px;
    margin:0 auto;
    display:flex;
    flex-direction:column;
    align-items:center;
    text-align:center;
    gap:14px;
  }
  body.asko-portal .asko-logo{
    height:42px;
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
    font-size:36px;
    font-weight:900;
    color:var(--asko-ink);
    letter-spacing:0;
  }
  body.asko-portal .asko-portal-greeting{
    max-width:720px;
    margin-top:6px;
    color:#475569;
    font-size:16px;
    line-height:1.5;
  }

  body.asko-portal .asko-landing{
    background:linear-gradient(180deg,var(--asko-teal) 0%,var(--asko-teal-dark) 100%);
    padding:26px 0 46px;
  }
  body.asko-portal .asko-tiles__inner{
    max-width:1100px;
    margin:0 auto;
    padding:0 18px;
  }
  body.asko-portal .asko-grid{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
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
    transition:transform .12s ease,background .12s ease,border-color .12s ease;
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
    letter-spacing:0;
    line-height:1.2;
    overflow-wrap:anywhere;
  }
  body.asko-portal .md-footer{display:none!important;}
  body.asko-portal .md-container{padding-bottom:0!important;}

  @media (max-width:980px){
    body.asko-portal .asko-grid{grid-template-columns:repeat(2,1fr);}
  }
  @media (max-width:520px){
    body.asko-portal .asko-portal-header-inner{flex-direction:column;text-align:center;}
    body.asko-portal .asko-grid{grid-template-columns:1fr;}
  }
</style>
