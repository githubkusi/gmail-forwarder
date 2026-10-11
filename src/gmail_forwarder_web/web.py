from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from .config import ConfigurationError, Settings
from .gam_client import GamClient, GamOperationError
from .service import ForwarderService, Gateway

_PACKAGE_DIR = Path(__file__).parent
_templates = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
_logger = logging.getLogger("uvicorn.error")


def _media_directory(package_dir: Path = _PACKAGE_DIR) -> Path:
    for parent in package_dir.parents:
        media_directory = parent / "media"
        if (media_directory / "icon.png").is_file():
            return media_directory
    return package_dir / "media"


def create_app(settings: Settings | None = None, gateway: Gateway | None = None) -> FastAPI:
    configured = settings or Settings.from_env()
    gam_gateway = gateway or GamClient()
    service = ForwarderService(configured, gam_gateway)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configured.validate()
        await run_in_threadpool(gam_gateway.setup)
        port = os.getenv("PORT") or "8000"
        _logger.info("Gmail Forwarder is available at http://127.0.0.1:%s", port)
        yield

    app = FastAPI(title="Gmail Forwarder", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(_PACKAGE_DIR / "static")), name="static")
    app.mount("/media", StaticFiles(directory=str(_media_directory())), name="media")

    def render(
        request: Request,
        *,
        notice: str | None = None,
        error: str | None = None,
        name: str = "",
        query: str = "",
        results: list[str] | None = None,
        copy_address: str | None = None,
        selected_recipient: str | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        return _templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "recipients": configured.recipients,
                "selected_recipient": selected_recipient or (configured.recipients[0] if configured.recipients else ""),
                "selected_domain": configured.domain_for_recipient(selected_recipient or configured.recipients[0]) if configured.recipients else "",
                "notice": notice,
                "error": error,
                "name": name,
                "query": query,
                "results": results,
                "copy_address": copy_address,
            },
            status_code=status_code,
        )

    async def form_data(request: Request) -> dict[str, str]:
        raw = (await request.body()).decode("utf-8", errors="replace")
        parsed = parse_qs(raw, keep_blank_values=True, max_num_fields=10)
        return {key: values[-1] for key, values in parsed.items() if values}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return render(request)

    @app.post("/create", response_class=HTMLResponse)
    async def create(request: Request):
        data = await form_data(request)
        name = data.get("name", "")
        recipient = data.get("recipient", "")
        try:
            address, _ = await run_in_threadpool(service.create, name, recipient)
            return render(
                request,
                notice=f"Forwarder created: {address}",
                copy_address=address,
                selected_recipient=recipient,
            )
        except ValueError as exc:
            return render(
                request,
                error=str(exc),
                name=name,
                selected_recipient=recipient if any(recipient.casefold() == item.casefold() for item in configured.recipients) else None,
            )
        except GamOperationError as exc:
            return render(
                request,
                error=str(exc),
                name=name,
                selected_recipient=recipient,
                status_code=502,
            )
        except Exception:
            return render(
                request,
                error="GAM could not complete the request. Check the server logs and GAM authorization.",
                name=name,
                selected_recipient=recipient,
                status_code=502,
            )

    @app.post("/search", response_class=HTMLResponse)
    async def search(request: Request):
        data = await form_data(request)
        query = data.get("query", "").strip()
        try:
            results = await run_in_threadpool(service.search, query)
            message = "No matching forwarders found." if not results else None
            return render(request, notice=message, query=query, results=results)
        except ValueError as exc:
            return render(request, error=str(exc), query=query)
        except Exception:
            return render(
                request,
                error="GAM could not search groups. Check the server logs and GAM authorization.",
                query=query,
                status_code=502,
            )

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz():
        return "ok"

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(_: Request, exc: ConfigurationError):
        return PlainTextResponse(str(exc), status_code=500)

    return app


app = create_app()