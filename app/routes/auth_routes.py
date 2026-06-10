# app/routes/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from starlette.responses import Response
from pydantic import BaseModel, Field

from app.security import verify_password, create_token
from app.auth.users import get_user
from app.auth.deps import COOKIE_NAME, get_current_user, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- Modelle ----------

class LoginReq(BaseModel):
    username: str = Field(..., examples=["admin"])
    password: str = Field(..., min_length=1)
    # Anzeigename, der ins Token und ins Log geht
    name: str | None = Field(None, examples=["Max Mustermann"])


class GuestReq(BaseModel):
    # nur für Editor: Name reicht
    name: str = Field(..., min_length=2, max_length=80)


# ---------- Admin-Login (Name + Admin-Passwort) ----------

@router.post("/login")
def login(req: LoginReq, resp: Response):
    """
    Admin-Login:
    - username: z.B. "admin"
    - password: Admin-Passwort
    - name: Anzeigename für Log / UI
    """
    user = get_user(req.username)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    display_name = (req.name or req.username).strip()

    token = create_token(
        sub=req.username,
        role="admin",
        name=display_name,
    )

    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # bei HTTPS/IIS auf True drehen
        path="/",
    )

    return {"ok": True, "role": "admin", "name": display_name}


# ---------- Editor-Gast-Login (nur Name) ----------

@router.post("/guest")
def guest(req: GuestReq, resp: Response):
    """
    Gast-Login für Editor:
    - kein Passwort
    - Name wird als "name" im Token gespeichert
    - Rolle = editor
    """
    display = req.name.strip()

    token = create_token(
        sub=f"guest:{display}",
        role="editor",
        name=display,
    )

    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )

    return {"ok": True, "role": "editor", "name": display}


# ---------- Who am I ----------

@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    """
    Liefert aktuelle Session-Infos für Frontend:
    - username aus Token.sub
    - role
    - name (Anzeigename, falls vorhanden)
    """
    return {
        "username": user["username"],
        "role": user["role"],
        "name": user.get("name") or user["username"],
    }


# ---------- Logout ----------

@router.post("/logout")
def logout(resp: Response):
    resp.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
