"""FastAPI app: a server-rendered view over the Eloify core.

Routes mirror the CLI commands (board / players / history / odds / last /
models) for reads, plus an HTMX log-a-game flow (preview → submit), add-player
and undo for writes. All the real logic lives in `data.py` (cache + engine) and
the core modules; this file is just routing + templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import elo
from ..sheets import SheetsError
from ..validate import ScoreError, validate_score
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


@app.get("/game/new", response_class=HTMLResponse)
def game_new(request: Request):
    return page(request, "game_new.html", names=data.player_names(),
                form=_blank_form())


# --- add-game form handling ------------------------------------------------


@dataclass
class AddForm:
    mode: str = "1v1"
    raw: dict = field(default_factory=dict)
    team_a: list[str] = field(default_factory=list)
    team_b: list[str] = field(default_factory=list)
    new_players: list[str] = field(default_factory=list)
    score_a: int | None = None
    score_b: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        size = 1 if self.mode == "1v1" else 2
        return (
            not self.errors
            and len(self.team_a) == size
            and len(self.team_b) == size
            and self.score_a is not None
            and self.score_b is not None
        )


def _blank_form(mode: str = "1v1") -> AddForm:
    return AddForm(mode=mode, raw={"a1": "", "a2": "", "b1": "", "b2": "",
                                   "score_a": "", "score_b": ""})


def _parse_add_form(
    mode: str, a1: str, a2: str, b1: str, b2: str, score_a: str, score_b: str
) -> AddForm:
    """Resolve typed names + scores into an AddForm, collecting any errors.

    Empty slots are simply left out (so a half-filled form previews nothing
    rather than erroring); ambiguity, bad scores and duplicate players do error.
    """
    mode = "2v2" if mode == "2v2" else "1v1"
    f = AddForm(mode=mode, raw={
        "a1": a1, "a2": a2, "b1": b1, "b2": b2,
        "score_a": score_a, "score_b": score_b,
    })
    size = 1 if mode == "1v1" else 2
    a_tokens = [a1, a2][:size]
    b_tokens = [b1, b2][:size]

    def resolve_into(tokens: list[str], team: list[str]) -> None:
        for tok in tokens:
            tok = (tok or "").strip()
            if not tok:
                continue
            name, is_new, cands = data.resolve_name(tok)
            if cands:
                f.errors.append(
                    f"{tok!r} is ambiguous: {', '.join(cands)}. Type more letters."
                )
                continue
            team.append(name)
            if is_new and name not in f.new_players:
                f.new_players.append(name)

    resolve_into(a_tokens, f.team_a)
    resolve_into(b_tokens, f.team_b)

    everyone = f.team_a + f.team_b
    dupes = {n for n in everyone if everyone.count(n) > 1}
    if dupes:
        f.errors.append(f"A player can't be on both sides: {', '.join(sorted(dupes))}.")

    for key, label in (("score_a", "Team A"), ("score_b", "Team B")):
        raw = (f.raw[key] or "").strip()
        if not raw:
            continue
        try:
            setattr(f, key, int(raw))
        except ValueError:
            f.errors.append(f"{label} score must be a whole number.")

    if f.score_a is not None and f.score_b is not None:
        try:
            validate_score(f.score_a, f.score_b)
        except ScoreError as e:
            f.errors.append(str(e))
    return f


@app.post("/games/preview", response_class=HTMLResponse)
def games_preview(
    request: Request,
    mode: str = Form("1v1"),
    a1: str = Form(""), a2: str = Form(""),
    b1: str = Form(""), b2: str = Form(""),
    score_a: str = Form(""), score_b: str = Form(""),
    model: str | None = Form(None),
):
    f = _parse_add_form(mode, a1, a2, b1, b2, score_a, score_b)
    mdl = data.resolve_model(model or _model_key(request))
    preview = None
    if f.complete:
        preview = data.preview(f.team_a, f.team_b, f.score_a, f.score_b, mdl)
    return templates.TemplateResponse(
        request, "_preview.html", {"form": f, "preview": preview, "model": mdl}
    )


@app.post("/games")
def games_create(
    request: Request,
    mode: str = Form("1v1"),
    a1: str = Form(""), a2: str = Form(""),
    b1: str = Form(""), b2: str = Form(""),
    score_a: str = Form(""), score_b: str = Form(""),
    model: str | None = Form(None),
):
    f = _parse_add_form(mode, a1, a2, b1, b2, score_a, score_b)
    mdl = data.resolve_model(model or _model_key(request))
    if not f.complete:
        if not f.errors:
            f.errors.append("Fill in both teams and a valid score.")
        return page(request, "game_new.html", status_code=400,
                    names=data.player_names(), form=f, model=mdl)
    data.log_game(f.mode, f.team_a, f.team_b, f.score_a, f.score_b, f.new_players)
    return RedirectResponse(url=f"/?model={mdl.key}", status_code=303)


@app.post("/players")
def players_create(request: Request, name: str = Form(...),
                   model: str | None = Form(None)):
    name = name.strip()
    mdl = data.resolve_model(model or _model_key(request))
    if name:
        data.add_player(name)
    return RedirectResponse(url=f"/players?model={mdl.key}", status_code=303)


@app.post("/games/undo")
def games_undo(request: Request, model: str | None = Form(None)):
    mdl = data.resolve_model(model or _model_key(request))
    data.undo_last()
    return RedirectResponse(url=f"/last?model={mdl.key}", status_code=303)


def run() -> None:
    """Console-script entry point (`elo-web`): launch uvicorn for local use."""
    import uvicorn

    uvicorn.run("eloify.web.app:app", host="0.0.0.0", port=8000, workers=1)
