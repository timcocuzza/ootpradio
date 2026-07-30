# OOTP 27 Radio Companion

This repository currently contains Milestone 6: automatic polling, stable-file
checks, recap narration, atomic persistent state, and duplicate prevention.
Watcher state is always stored outside the read-only OOTP save.

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
50 passed
```

## Preview the narration

To print exactly what would be spoken without producing audio:

```bash
python3 -m ootp_radio.cli speak-recap tests/fixtures/game_1596/game_box_1596.html --dry-run
```

The narration begins with WBAL News Radio because the recap mentions the
Baltimore Orioles. Baltimore is currently the only team-to-station mapping.

## Preview the latest live recap

To print the narration without producing audio, add `--dry-run`:

```bash
python3 -m ootp_radio.cli recap-latest \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg" \
  --dry-run
```

## Manual Milestone 6 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli watch \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

The watcher records the current game as its baseline without speaking it. After
you complete or simulate one new played game, it should narrate exactly one
recap beginning with:

```text
This is WBAL News Radio. Your Baltimore Orioles postgame report.
```

Leave the watcher running briefly to confirm the recap does not repeat, then
stop it with Control+C. Restarting the same command should not replay the last
processed game. State is stored atomically at `./var/state.json` by default.

To deliberately narrate the already-current game when starting, add
`--play-current`.
