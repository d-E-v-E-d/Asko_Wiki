from typing import Callable, TypedDict
from fastapi import Depends, HTTPException, Request, status
from app.security import decode_token
from app.config import config

COOKIE_NAME = config.get("security", "cookie_name", default="editor_session")

class CurrentUser(TypedDict):
    username: str
    role: str

def _extract_token(req: Request) -> str | None:
    # 1) Cookie
    token = req.cookies.get(COOKIE_NAME)
    if token:
        return token
    # 2) Authorization: Bearer <token>
    auth = req.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None

def get_current_user(request: Request) -> CurrentUser:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_token(token)
    return {
        "username": data.get("sub"),
        "role": data.get("role"),
        "name": data.get("name") or data.get("sub"),
    }


def require_role(required: str) -> Callable[..., CurrentUser]:
    def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        role = user["role"]
        order = {"reader": 1, "editor": 2, "admin": 3}
        if order.get(role, 0) < order.get(required, 0):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dep
