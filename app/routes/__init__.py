# app/routes/__init__.py
from . import auth_routes, editor_routes, admin_routes, preview_routes, meta_routes, sync_routes

__all__ = [
    "auth_routes",
    "editor_routes",
    "admin_routes",
    "preview_routes",
    "meta_routes",
    "sync_routes",
]
