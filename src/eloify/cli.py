"""Eloify command-line interface (invoked as `elo` or `eloify`)."""

from __future__ import annotations

import sys

import click
import questionary
from rich.console import Console
from rich.table import Table

from . import config, elo, engine
from .chart import line_chart
from .elo import Model
from .parse import ParseError, parse_add
from .sheets import SheetsError, Store
from .validate import ScoreError, validate_score

console = Console()
err = Console(stderr=True)


def _store() -> Store:
    try:
        return Store()
    except SheetsError as e:
        err.print(f"[bold red]✗[/] {e}")
        sys.exit(1)


def model_option(f):
    """Shared --model option: pick a rating model (see `elo models`)."""
    return click.option(
        "-m",
        "--model",
        "model_key",
        default=None,
        metavar="KEY",
        help="Rating model: a key or number from `elo models`. Defaults to ELOIFY_MODEL or 'mov'.",
    )(f)


def _resolve_model(model_key: str | None) -> Model:
    """Resolve a --model key (or the configured default) to a Model, or exit."""
    try:
        return elo.get_model(model_key or config.DEFAULT_MODEL)
    except KeyError as e:
        bad = e.args[0] if e.args else model_key
        choices = ", ".join(elo.model_keys())
        err.print(f"[bold red]✗[/] Unknown model {bad!r}. Available: {choices}.")
        sys.exit(1)


def _fmt(rating: float) -> str:
    return f"{rating:.0f}"


def _resolve_name(token: str, known: list[str]) -> tuple[str, bool]:
    """Map a typed token to a canonical name. Returns (name, is_new)."""
    candidates = engine.match_candidates(token, known)
    if len(candidates) == 1:
        return candidates[0], False
    if not candidates:
        return token, True  # new player
    # Ambiguous: prompt if interactive, else fail loudly.
    if not sys.stdin.isatty():
        raise click.ClickException(
            f"'{token}' is ambiguous: {', '.join(candidates)}. Type more letters."
        )
    console.print(f"[yellow]'{token}'[/] matches several players:")
    for i, name in enumerate(candidates, 1):
        console.print(f"  {i}) {name}")
    choice = click.prompt("Pick", type=click.IntRange(1, len(candidates)))
    return candidates[choice - 1], False


@click.group()
@click.version_option(package_name="eloify")
def main() -> None:
    """Eloify — office ping pong ELO tracker."""


ADD_NEW = "\x00add-new"  # sentinel value for the "add a new player" choice


def _prompt_new_player(taken: list[str]) -> str | None:
    """Ask for a brand-new player name. Returns None if cancelled/invalid."""
    name = questionary.text("New player name:").ask()
    if name is None:
        return None
    name = name.strip()
    if not name:
        err.print("[yellow]Name can't be empty.[/]")
        return None
    if name in taken:
        err.print(f"[yellow]{name} is already in this game.[/]")
        return None
    return name


def _pick_team(label: str, pool: list[str], size: int) -> list[str] | None:
    """Pick `size` players for a team, allowing new names. None if cancelled."""
    team: list[str] = []
    while len(team) < size:
        slot = f"{label} (player {len(team) + 1} of {size})" if size > 1 else label
        choices = [questionary.Choice(n, value=n) for n in pool if n not in team]
        choices.append(questionary.Choice("➕ Add a new player…", value=ADD_NEW))
        pick = questionary.select(slot, choices=choices).ask()
        if pick is None:
            return None
        if pick == ADD_NEW:
            name = _prompt_new_player(pool + team)
            if name is None:
                continue
            team.append(name)
        else:
            team.append(pick)
    return team


def _prompt_scores(a_label: str, b_label: str) -> tuple[int, int] | None:
    """Prompt for both scores, re-asking until they form a legal result."""
    while True:
        raw_a = questionary.text(f"{a_label} score:").ask()
        if raw_a is None:
            return None
        raw_b = questionary.text(f"{b_label} score:").ask()
        if raw_b is None:
            return None
        try:
            score_a, score_b = int(raw_a), int(raw_b)
        except ValueError:
            err.print("[yellow]Scores must be whole numbers.[/]")
            continue
        try:
            validate_score(score_a, score_b)
        except ScoreError as e:
            err.print(f"[yellow]{e}[/]")
            continue
        return score_a, score_b


def _interactive_add(known: list[str]):
    """Walk the user through logging a game. Returns the game tuple or None."""
    mode = questionary.select(
        "Game type:",
        choices=[
            questionary.Choice("1v1 (singles)", value="1v1"),
            questionary.Choice("2v2 (doubles)", value="2v2"),
        ],
    ).ask()
    if mode is None:
        return None
    size = 1 if mode == "1v1" else 2

    team_a = _pick_team("Team A", known, size)
    if team_a is None:
        return None
    team_b = _pick_team("Team B", [n for n in known if n not in team_a], size)
    if team_b is None:
        return None

    a_label = " & ".join(team_a)
    b_label = " & ".join(team_b)
    scores = _prompt_scores(a_label, b_label)
    if scores is None:
        return None
    score_a, score_b = scores

    new_players = [n for n in team_a + team_b if n not in known]
    return mode, team_a, team_b, new_players, score_a, score_b


@main.command()
@click.argument("tokens", nargs=-1)
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation prompt.")
@model_option
def add(tokens: tuple[str, ...], yes: bool, model_key: str | None) -> None:
    """Log a game:  elo add duncan peter 21 18  (1v1)  ·  ...sam alex 21 15 (2v2).

    Run `elo add` with no arguments for a guided, interactive flow.
    """
    model = _resolve_model(model_key)
    store = _store()
    games = store.read_games()
    known = store.player_names()

    if tokens:
        try:
            pg = parse_add(list(tokens))
            validate_score(pg.score_a, pg.score_b)
        except (ParseError, ScoreError) as e:
            err.print(f"[bold red]✗[/] {e}")
            sys.exit(1)

        # Resolve typed names to canonical players (or flag as new).
        team_a, team_b, new_players = [], [], []
        for token in pg.team_a:
            name, is_new = _resolve_name(token, known)
            team_a.append(name)
            if is_new:
                new_players.append(name)
        for token in pg.team_b:
            name, is_new = _resolve_name(token, known)
            team_b.append(name)
            if is_new:
                new_players.append(name)
        mode, score_a, score_b = pg.mode, pg.score_a, pg.score_b
    else:
        if not sys.stdin.isatty():
            err.print(
                "[bold red]✗[/] No game given. e.g. elo add duncan peter 21 18 "
                "(or run `elo add` in a terminal for the guided flow)."
            )
            sys.exit(1)
        result = _interactive_add(known)
        if result is None:
            console.print("[dim]Cancelled.[/]")
            return
        mode, team_a, team_b, new_players, score_a, score_b = result

    stats = engine.replay(known, [engine.record_to_game(g) for g in games], model)
    preview = engine.preview_game(stats, team_a, team_b, score_a, score_b, model)

    # Confirmation view.
    def side(names: list[str], score: int, winner: bool) -> str:
        tag = " [green]← winner[/]" if winner else ""
        labelled = [
            (f"[yellow]⚠ NEW: {n}[/]" if n in new_players else n) for n in names
        ]
        return f"{' & '.join(labelled)}  [bold]{score}[/]{tag}"

    a_won = score_a > score_b
    console.print()
    console.print(f"  [dim]{mode} · {model.label}[/]")
    console.print("  Team A:  " + side(team_a, score_a, a_won))
    console.print("  Team B:  " + side(team_b, score_b, not a_won))
    console.print("  [dim]projected:[/] " + "   ".join(
        f"{n} {d:+.0f}" for n, (_, _, d) in preview.items()
    ))
    console.print()

    if not yes and not click.confirm("Confirm", default=True):
        console.print("[dim]Cancelled.[/]")
        return

    for name in new_players:
        store.add_player(name)
    game_id = store.next_game_id(games)
    store.append_game(game_id, mode, team_a, team_b, score_a, score_b)

    console.print(f"[green]✓[/] Logged game #{game_id}.")
    for name, (before, after, delta) in preview.items():
        colour = "green" if delta >= 0 else "red"
        console.print(
            f"   {name}: {_fmt(before)} → {_fmt(after)} "
            f"([{colour}]{delta:+.0f}[/])"
        )


@main.command()
@click.argument(
    "which",
    required=False,
    type=click.Choice(["overall", "singles", "doubles"], case_sensitive=False),
)
@click.option("--top", type=int, default=None, help="Show only the top N players.")
@model_option
def board(which: str | None, top: int | None, model_key: str | None) -> None:
    """Show the leaderboard.

    `elo board` shows overall ELO with singles & doubles columns.
    `elo board singles` / `elo board doubles` rank by that game type only.
    Use `--model KEY` to score the same games with a different rating model.
    """
    model = _resolve_model(model_key)
    store = _store()
    games = [engine.record_to_game(g) for g in store.read_games()]
    modes = engine.replay_modes(store.player_names(), games, model)
    which = (which or "overall").lower()

    # Filtered board: rank by one game type, only its W/L and ELO.
    if which in ("singles", "doubles"):
        stats = modes[which]
        ranked = [s for s in engine.leaderboard(stats) if s.games > 0]
        if top:
            ranked = ranked[:top]
        label = "Singles (1v1)" if which == "singles" else "Doubles (2v2)"
        table = Table(title=f"🏓 {label} Leaderboard", caption=f"model: {model.label}")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Player")
        table.add_column("ELO", justify="right", style="bold")
        table.add_column("W-L", justify="right")
        table.add_column("Win%", justify="right")
        table.add_column("Games", justify="right", style="dim")
        for i, s in enumerate(ranked, 1):
            table.add_row(
                str(i), s.name, _fmt(s.rating),
                f"{s.wins}-{s.losses}", f"{s.win_pct:.0f}%", str(s.games),
            )
        console.print(table if ranked else f"[dim]No {which} games logged yet.[/]")
        return

    # Overall board: headline ELO plus singles/doubles columns.
    overall, singles, doubles = modes["overall"], modes["singles"], modes["doubles"]
    ranked = [s for s in engine.leaderboard(overall) if s.games > 0]
    if top:
        ranked = ranked[:top]

    def cell(stats: dict, name: str) -> str:
        s = stats.get(name)
        return _fmt(s.rating) if s and s.games > 0 else "[dim]–[/]"

    table = Table(title="🏓 Eloify Leaderboard", caption=f"model: {model.label}")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Player")
    table.add_column("Overall", justify="right", style="bold")
    table.add_column("Singles", justify="right")
    table.add_column("Doubles", justify="right")
    table.add_column("W-L", justify="right")
    table.add_column("Win%", justify="right")
    table.add_column("Games", justify="right", style="dim")
    for i, s in enumerate(ranked, 1):
        table.add_row(
            str(i), s.name, _fmt(s.rating),
            cell(singles, s.name), cell(doubles, s.name),
            f"{s.wins}-{s.losses}", f"{s.win_pct:.0f}%", str(s.games),
        )
    console.print(table if ranked else "[dim]No players yet. Log a game with `elo add`.[/]")


@main.command()
@model_option
def players(model_key: str | None) -> None:
    """List registered players and their current ELO."""
    model = _resolve_model(model_key)
    store = _store()
    names = store.player_names()
    stats = engine.replay(
        names, [engine.record_to_game(g) for g in store.read_games()], model
    )
    if not names:
        console.print("[dim]No players yet.[/]")
        return
    for s in engine.leaderboard(stats):
        console.print(f"  {s.name}  [dim]{_fmt(s.rating)} · {s.games} games[/]")


@main.command(name="add-player")
@click.argument("name")
def add_player(name: str) -> None:
    """Register a player (optional — `add` auto-creates unknown names)."""
    store = _store()
    if name.lower() in {n.lower() for n in store.player_names()}:
        console.print(f"[yellow]{name}[/] already exists.")
        return
    store.add_player(name)
    console.print(f"[green]✓[/] Added {name}.")


def _resolve_player(name: str, known: list[str]) -> str:
    """Resolve a name to a known player, or exit with an error."""
    resolved = engine.match_candidates(name, known)
    if not resolved:
        err.print(f"[bold red]✗[/] No player matches '{name}'.")
        sys.exit(1)
    return resolved[0]


@main.command()
@click.argument("name")
@click.argument("opponent", required=False)
@click.option("--no-graph", is_flag=True, help="Hide the rating-trend graph.")
@model_option
def history(
    name: str, opponent: str | None, no_graph: bool, model_key: str | None
) -> None:
    """Show a player's recent games and rating trend.

    Pass a second name for head-to-head:  elo history peter duncan
    """
    model = _resolve_model(model_key)
    store = _store()
    games = [engine.record_to_game(g) for g in store.read_games()]
    known = store.player_names()
    player = _resolve_player(name, known)
    rival = _resolve_player(opponent, known) if opponent else None
    if rival and rival == player:
        err.print("[bold red]✗[/] Pick two different players for head-to-head.")
        sys.exit(1)

    # Replay incrementally to capture this player's rating after each game.
    stats = {n: engine.PlayerStats(name=n, rating=model.start_rating) for n in known}
    rows = []
    for g in games:
        before = stats[player].rating if player in stats else model.start_rating
        engine.apply_game(stats, g, model)
        after = stats[player].rating if player in stats else before
        if player not in (g.team_a + g.team_b):
            continue
        on_a = player in g.team_a
        their_team = g.team_b if on_a else g.team_a
        # Head-to-head: only games where the rival was on the opposing side.
        if rival and rival not in their_team:
            continue
        opp = " & ".join(their_team)
        mine = g.score_a if on_a else g.score_b
        theirs = g.score_b if on_a else g.score_a
        res = "W" if mine > theirs else "L"
        rows.append((g.id, res, mine, theirs, opp, before, after))

    if not rows:
        if rival:
            console.print(f"[dim]{player} hasn't faced {rival} yet.[/]")
        else:
            console.print(f"[dim]{player} hasn't played any games yet.[/]")
        return

    wins = sum(1 for r in rows if r[1] == "W")
    losses = len(rows) - wins

    # Rating-trend graph: start rating, then the rating after each game.
    if not no_graph:
        trend = [rows[0][5]] + [r[6] for r in rows]
        graph = line_chart(trend)
        if graph:
            scope = f"{player} vs {rival}" if rival else player
            console.print(f"[bold]📈 {scope}[/] [dim]· {model.label}[/]")
            for line in graph:
                console.print(line, style="cyan", highlight=False)
            console.print(
                f"[dim]games #{rows[0][0]} → #{rows[-1][0]} · {len(rows)} played[/]"
            )
            console.print()

    title = f"📜 {player} vs {rival}" if rival else f"📜 {player}"
    table = Table(title=title, caption=f"{player} {wins}-{losses} {rival}" if rival else None)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Result")
    table.add_column("Score", justify="right")
    table.add_column("Opponent")
    table.add_column("ELO", justify="right")
    for gid, res, mine, theirs, opp, before, after in rows[-15:]:
        colour = "green" if res == "W" else "red"
        table.add_row(
            str(gid), f"[{colour}]{res}[/]", f"{mine}-{theirs}", opp,
            f"{_fmt(before)}→{_fmt(after)}",
        )
    console.print(table)


@main.command()
@click.argument("n", type=int, default=5)
def last(n: int) -> None:
    """Show the last N games (default 5)."""
    store = _store()
    games = store.read_games()[-n:]
    if not games:
        console.print("[dim]No games logged yet.[/]")
        return
    for g in games:
        a_won = int(g["score_a"]) > int(g["score_b"])
        a = f"[green]{g['team_a']}[/]" if a_won else g["team_a"]
        b = g["team_b"] if a_won else f"[green]{g['team_b']}[/]"
        console.print(f"  #{g['id']}  {a}  {g['score_a']}–{g['score_b']}  {b}")


@main.command()
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation prompt.")
def undo(yes: bool) -> None:
    """Remove the most recently logged game."""
    store = _store()
    games = store.read_games()
    if not games:
        console.print("[dim]No games to undo.[/]")
        return
    g = games[-1]
    console.print(
        f"About to remove #{g['id']}: {g['team_a']} {g['score_a']}–{g['score_b']} {g['team_b']}"
    )
    if not yes and not click.confirm("Delete it?", default=False):
        console.print("[dim]Kept.[/]")
        return
    store.delete_last_game()
    console.print("[green]✓[/] Removed. Ratings will recompute from the remaining log.")


@main.command()
def init() -> None:
    """One-time setup: write header rows to empty tabs."""
    store = _store()
    created = store.ensure_headers()
    if created:
        console.print(f"[green]✓[/] Initialised headers on: {', '.join(created)}.")
    else:
        console.print("[dim]Both tabs already have headers — nothing to do.[/]")


@main.command()
def models() -> None:
    """List the available rating models for `--model`."""
    active = _resolve_model(None)
    table = Table(title="🧮 Rating models")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Key")
    table.add_column("Name")
    table.add_column("Description")
    for i, m in enumerate(elo.all_models(), 1):
        tag = " [green](default)[/]" if m.key == active.key else ""
        table.add_row(str(i), f"[bold]{m.key}[/]{tag}", m.label, m.description)
    console.print(table)
    console.print(
        "[dim]Pick one per command with --model KEY (or its #), "
        "or set ELOIFY_MODEL to change the default.[/]"
    )


if __name__ == "__main__":
    main()
