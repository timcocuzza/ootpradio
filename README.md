# OOTP 27 Radio Companion

This repository currently contains Milestone 7: the automatic recap watcher
plus deterministic parsing and printed preview of same-slate MLB scores. Score
previews are not connected to speech yet.

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
60 passed
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

## Manual Milestone 7 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli scores-latest \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

For the current August 3 slate, the command should report `15 games found` and
print one deterministic sentence per MLB result, including Baltimore's latest
game. It should not include minor-league games or produce audio.

Discovery uses the played replay's modification time, includes box scores
within five seconds, and requires the same MLB game date. IDs do not need to be
contiguous. All candidate files must remain unchanged across two metadata polls
before they are parsed.
