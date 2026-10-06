from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.db import init_db
from app.errors import AppError
from app.templating import render
from app.web import LoginRedirect, SetupRedirect
from app.web import router as web_router

STATIC = Path(__file__).parent / "static"


def create_app(db_path: str | None = None) -> FastAPI:
    init_db(db_path)
    app = FastAPI(title="Shop CRM", version="1.0.0")
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    app.include_router(api_router)
    app.include_router(web_router)

    @app.exception_handler(AppError)
    def handle_app_error(request: Request, exc: AppError):
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": exc.message}, status_code=exc.status)
        return render(request, "error.html", {"title": "Shop CRM", "message": exc.message}, exc.status)

    @app.exception_handler(RequestValidationError)
    def handle_validation(request: Request, exc: RequestValidationError):
        message = "Check the form and try again"
        errors = exc.errors()
        if errors:
            message = str(errors[0].get("msg", message))
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": message}, status_code=422)
        return render(request, "error.html", {"title": "Shop CRM", "message": message}, 422)

    @app.exception_handler(LoginRedirect)
    def handle_login(_request: Request, _exc: LoginRedirect):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(SetupRedirect)
    def handle_setup(_request: Request, _exc: SetupRedirect):
        return RedirectResponse("/setup", status_code=303)

    return app


app = create_app()
