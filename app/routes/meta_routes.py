# app/routes/meta_routes.py
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List
from app.services.build_service import REPO_ROOT
from app.services.log_service import read_log
from app.services.pages_service import list_folder_paths

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/last_change")
def last_change(file: str = Query(..., description="relativer Pfad z.B. Schadenbearbeitung_Generell/zweck.md")):
    """
    Liefert den letzten Logeintrag (draft_saved/approved) zu einer Datei.
    Wird von der MkDocs-Seite genutzt, um 'Zuletzt geändert' im Footer anzuzeigen.
    """
    log: List[Dict[str, Any]] = read_log()
    candidates = [
        e for e in log
        if e.get("file") == file and e.get("action") in ("approved", "draft_saved")
    ]
    if not candidates:
        raise HTTPException(status_code=404, detail="Keine Einträge für diese Datei")

    latest = sorted(candidates, key=lambda e: e.get("timestamp", ""), reverse=True)[0]
    return {
        "file": latest.get("file"),
        "user": latest.get("user"),
        "action": latest.get("action"),
        "timestamp": latest.get("timestamp"),
        "details": latest.get("details") or {},
    }


@router.get("/folders")
def folders(site: str = Query(..., description="Bereichsname z.B. schaden")):
    return {"ok": True, "site": site, "folders": list_folder_paths(REPO_ROOT, site)}
