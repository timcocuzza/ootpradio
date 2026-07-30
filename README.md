# OOTP 27 Radio Companion

This repository currently contains Milestone 2: deterministic extraction of
the static game-1596 recap and safe narration through macOS text-to-speech. It
does not access a live OOTP save yet.

## Requirements

- Python 3.11 or newer

## Setup

From this directory, create an isolated environment and install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

Run the automated smoke test:

```bash
pytest -q
```

Expected result:

```text
14 passed
```

## Preview the narration

To print exactly what would be spoken without producing audio:

```bash
python3 -m ootp_radio.cli speak-recap tests/fixtures/game_1596/game_box_1596.html --dry-run
```

The narration begins with WBAL News Radio because the recap mentions the
Baltimore Orioles. Baltimore is currently the only team-to-station mapping.

## Manual Milestone 2 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli speak-recap tests/fixtures/game_1596/game_box_1596.html
```

The Mac should read the cleaned recap aloud, beginning with:

```text
This is WBAL News Radio. Your Baltimore Orioles postgame report.
```

By default, the application does not pass a voice or rate to `say`, allowing
macOS to use the user's configured text-to-speech settings. `--voice` and
`--rate` can explicitly override those settings. No HTML should be spoken.

This milestone only speaks the static fixture. Live-save access deliberately
remains out of scope.
