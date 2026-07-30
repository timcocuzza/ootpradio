# OOTP 27 Radio Companion

This repository currently contains Milestone 8: the automatic recap watcher
plus optional narration of same-slate MLB scores after the played-game recap.

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
68 passed
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

## Manual Milestone 8 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli recap-latest \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg" \
  --around-league
```

The played Orioles recap should be spoken first. After a short paragraph pause,
the Mac should say `Now, around the league` and narrate the other 14 MLB games.
The Orioles result must not be repeated in the score segment. Score sentences
use articles, such as `The Seattle Mariners defeated the Los Angeles Dodgers`.

Recap-only remains the default. Add `--around-league` to either `recap-latest`
or `watch` to enable the optional score segment.
