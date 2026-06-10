from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from app.config import config


COOKIE_NAME = config.get('security', 'cookie_name', default='editor_session')


def add_middlewares(app: FastAPI):
    app.add_middleware(SessionMiddleware, secret_key='session-secret-change-me', same_site='lax', https_only=True)
    return app