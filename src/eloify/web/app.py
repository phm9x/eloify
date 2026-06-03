"""FastAPI app: a server-rendered view over the Eloify core.

Routes mirror the CLI commands (board / players / history / odds / last /
models) for reads. The real logic lives in `data.py` (cache + engine) and the
core modules; this file is just routing + templates.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import elo
from ..sheets import SheetsError
from . import charts, data

_HERE = Path(__file__).parent
app = FastAPI(title="Eloify")
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
templates = Jinja2Templates(directory=_HERE / "templates")
templates.env.filters["elo"] = lambda r: f"{r:.0f}"
templates.env.globals["sparkline_svg"] = charts.sparkline_svg

MODEL_COOKIE = "model"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


@app.middleware("http")
async def remember_model(request: Request, call_next):
    """Persist a `?model=` choice in a cookie so it sticks across navigation."""
    response = await call_next(request)
    chosen = request.query_params.get("model")
    if chosen:
        response.set_cookie(MODEL_COOKIE, chosen, max_age=COOKIE_MAX_AGE)
    return response


def _model_key(request: Request) -> str | None:
    return request.query_params.get("model") or request.cookies.get(MODEL_COOKIE)


def _current_model(request: Request):
    return data.resolve_model(_model_key(request))


def page(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
    """Render a full page with the common nav context (model selector etc.)."""
    model = ctx.get("model") or _current_model(request)
    ctx.update(
        model=model,
        model_key=model.key,
        models=elo.all_models(),
    )
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


@app.exception_handler(SheetsError)
async def sheets_error(request: Request, exc: SheetsError):
    return page(request, "error.html", status_code=503, message=str(exc))


# --- reads -----------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def board(request: Request, which: str = "overall", top: int | None = None):
    model = _current_model(request)
    return page(request, "board.html", **data.board(model, which, top), top=top)


@app.get("/players", response_class=HTMLResponse)
def players(request: Request):
    model = _current_model(request)
    return page(request, "players.html", ranked=data.players(model))


@app.get("/history/{player}", response_class=HTMLResponse)
def history(request: Request, player: str, opponent: str | None = None):
    model = _current_model(request)
    who = data.resolve_player(player)
    if who is None:
        return page(request, "error.html", status_code=404,
                    message=f"No player matches {player!r}.")
    rival = data.resolve_player(opponent) if opponent else None
    if rival and rival == who:
        rival = None
    ctx = data.history(who, rival, model)
    return page(request, "history.html", names=data.player_names(), **ctx)


@app.get("/odds", response_class=HTMLResponse)
def odds(request: Request, p1: str | None = None, p2: str | None = None):
    model = _current_model(request)
    names = data.player_names()
    r1 = data.resolve_player(p1) if p1 else None
    r2 = data.resolve_player(p2) if p2 else None
    ctx: dict = {"names": names, "p1_in": p1 or "", "p2_in": p2 or ""}
    if r1 and r2 and r1 != r2:
        ctx["result"] = data.odds(r1, r2, model)
    elif p1 and p2:
        ctx["message"] = "Pick two different known players."
    return page(request, "odds.html", **ctx)


@app.get("/last", response_class=HTMLResponse)
def last(request: Request, n: int = 5):
    games = list(reversed(data.last(n)))  # newest first
    return page(request, "last.html", games=games, n=n)


@app.get("/models", response_class=HTMLResponse)
def models(request: Request):
    return page(request, "models.html", active=_current_model(request))


@app.get("/headshot/{player}", response_class=HTMLResponse)
def headshot(request: Request, player: str):
    from .. import headshot as hs

    who = data.resolve_player(player) or player
    return page(request, "headshot.html", player=who, art=hs.art_text(who))


def run() -> None:
    """Console-script entry point (`elo-web`): launch uvicorn for local use."""
    import uvicorn

    uvicorn.run("eloify.web.app:app", host="0.0.0.0", port=8000, workers=1)
