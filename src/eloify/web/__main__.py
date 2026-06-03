"""`python -m eloify.web` — launch the web UI with the active interpreter.

Equivalent to the `elo-web` console script, but immune to PATH/shebang issues:
it always runs in whatever Python you invoked it with (e.g. the active venv),
rather than resolving a possibly-stale `elo-web` from somewhere else on PATH.
"""

from .app import run

run()
