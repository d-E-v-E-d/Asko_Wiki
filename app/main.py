from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routes import auth_routes, editor_routes, admin_routes, preview_routes, meta_routes, sync_routes
from app.auth.deps import COOKIE_NAME
from app.runtime_paths import get_app_root, get_site_build_root, get_sites_root
from app.security import decode_token
from app.site_registry import SITES

app = FastAPI(title="Arbeitsanweisung Editor/Admin")

APP_ROOT = get_app_root()
SITES_ROOT = get_sites_root()
SITE_BUILD_ROOT = get_site_build_root()

# UI
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "app" / "static")), name="static")

# MkDocs Build Output
app.mount("/site", StaticFiles(directory=str(SITE_BUILD_ROOT), html=True), name="site")

for site_def in SITES:
  s = site_def.key
  live_dir = SITES_ROOT / site_def.folder / "docs"
  draft_dir = SITES_ROOT / site_def.folder / "docs_draft"

  live_dir.mkdir(parents=True, exist_ok=True)
  draft_dir.mkdir(parents=True, exist_ok=True)

  app.mount(f"/docs/{s}",  StaticFiles(directory=str(live_dir)),  name=f"docs_{s}")
  app.mount(f"/docs_draft/{s}", StaticFiles(directory=str(draft_dir)), name=f"docs_draft_{s}")

# API Router
app.include_router(auth_routes.router)
app.include_router(editor_routes.router)
app.include_router(preview_routes.router)
app.include_router(admin_routes.router)
app.include_router(meta_routes.router)
app.include_router(sync_routes.router)

@app.get("/")
async def root(request: Request):
  token = request.cookies.get(COOKIE_NAME)
  if token:
    try:
      decode_token(token)
      return RedirectResponse("/static/admin/admin.html", status_code=302)
    except Exception:
      pass
  return RedirectResponse("/static/admin/admin.html", status_code=302)
