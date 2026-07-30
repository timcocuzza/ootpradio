# OOTP 27 Radio Companion

This repository currently contains Milestone 9: the recap and score broadcast
plus printed parsing and conservative filtering of recent OOTP messages. News
is not connected to speech yet.

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
89 passed
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

## Manual Milestone 9 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli news-preview \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg" \
  --team-name "Baltimore Orioles"
```

For the current latest-game batch, the command should report `5 recent messages
examined`, `1 selected`, and `4 filtered out`. The selected headline is `Busch
Tags Marlins for 5 Hits`; the three minor-league stories and one scouting report
are filtered out.

Selected messages include a cleaned headline and the exact selection reason.
Bodies and entity tags are parsed only to classify whether a story belongs to
MLB; they are not included in the headline-only output. News remains a printed
preview and is never spoken in this milestone.

Message batches are associated with the latest replay using a tested 30-second
modification-time window; the current save writes messages roughly 12 seconds
after its replay and box-score files.
