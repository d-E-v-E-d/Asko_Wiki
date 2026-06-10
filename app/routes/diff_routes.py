# app/routes/diff_routes.py (optional)
from fastapi import APIRouter, Depends, Query
from difflib import HtmlDiff
from pathlib import Path
from app.config import config
from app.auth.deps import require_role


router = APIRouter(prefix='/diff', tags=['diff'])


@router.get('/')
async def diff(file: str = Query(...), user=Depends(require_role('admin'))):
    docs = Path(config.get('paths','docs')) / file
    draft = Path(config.get('paths','docs_draft')) / file
    if not docs.exists() or not draft.exists():
        return {'html': '<p>Datei fehlt in docs oder draft.</p>'}
    a = docs.read_text(encoding='utf-8').splitlines()
    b = draft.read_text(encoding='utf-8').splitlines()
    html = HtmlDiff().make_file(a, b, fromdesc='Live', todesc='Draft')
    return {'html': html}