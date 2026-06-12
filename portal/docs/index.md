<!-- ASKO Wiki Länderportal -->
<div class="asko-page">
  <header class="asko-portal-header">
    <div class="asko-portal-header-inner">
      <img src="assets/img/logo.svg" alt="ASKO Logo" class="asko-logo">
      <div class="asko-portal-titlewrap">
        <h1 class="asko-portal-title">Arbeitsanweisungen Portal</h1>
        <div class="asko-portal-greeting">Willkommen im Arbeitsanweisungs-Portal der ASKO.<br>Bitte wählen Sie ein Land aus, um fortzufahren.</div>
      </div>
    </div>
  </header>
  <section class="asko-landing">
    <div class="asko-tiles__inner">
      <div class="asko-grid" role="list">
        <a class="asko-tile asko-tile--at" href="./at/" role="listitem"><span class="asko-tile__label">Österreich</span></a>
        <a class="asko-tile asko-tile--de" href="./de/" role="listitem"><span class="asko-tile__label">Deutschland</span></a>
        <a class="asko-tile asko-tile--si" href="./si/" role="listitem"><span class="asko-tile__label">Slowenien</span></a>
        <a class="asko-tile asko-tile--it" href="./it/" role="listitem"><span class="asko-tile__label">Italien</span></a>
        <a class="asko-tile asko-tile--ro" href="./ro/" role="listitem"><span class="asko-tile__label">Rumänien</span></a>
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
    body.asko-portal .md-main__inner{max-width:1180px;}
  }
  body.asko-portal .md-content__inner>header{display:none!important;}
  body.asko-portal .md-content__inner{margin:0;}
  body.asko-portal .md-content__inner:before{display:none;}

  body.asko-portal .asko-portal-header{
    background:#fff;
    padding:26px 18px 18px;
  }
  body.asko-portal .asko-portal-header-inner{
    max-width:1180px;
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
    max-width:1180px;
    margin:0 auto;
    padding:0 18px;
  }
  body.asko-portal .asko-grid{
    display:grid;
    grid-template-columns:repeat(5,minmax(0,1fr));
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
  body.asko-portal .asko-grid .asko-tile--at{border-color:rgba(220,38,38,.86)!important;}
  body.asko-portal .asko-grid .asko-tile--de{border-color:rgba(15,23,42,.88)!important;}
  body.asko-portal .asko-grid .asko-tile--si{border-color:rgba(37,99,235,.86)!important;}
  body.asko-portal .asko-grid .asko-tile--it{border-color:rgba(22,163,74,.86)!important;}
  body.asko-portal .asko-grid .asko-tile--ro{border-color:rgba(202,138,4,.90)!important;}
  body.asko-portal .asko-grid .asko-tile--at:hover{border-color:rgba(248,113,113,.98)!important;}
  body.asko-portal .asko-grid .asko-tile--de:hover{border-color:rgba(31,41,55,.98)!important;}
  body.asko-portal .asko-grid .asko-tile--si:hover{border-color:rgba(96,165,250,.98)!important;}
  body.asko-portal .asko-grid .asko-tile--it:hover{border-color:rgba(74,222,128,.98)!important;}
  body.asko-portal .asko-grid .asko-tile--ro:hover{border-color:rgba(245,158,11,.98)!important;}
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

