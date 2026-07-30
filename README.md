# OOTP 27 Radio Companion

This repository currently contains Milestone 5: an on-demand pipeline that
validates a live save, detects and stabilizes its latest played game, parses the
official OOTP recap, adds the mapped station introduction, and speaks it using
macOS text-to-speech.

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
37 passed
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

## Manual Milestone 5 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli recap-latest \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

The Mac should read the newest completed played-game recap, beginning with:

```text
This is WBAL News Radio. Your Baltimore Orioles postgame report.
```

The command deliberately allows the same latest game to be replayed whenever
it is run. Automatic watching and duplicate prevention remain out of scope
until Milestone 6.
