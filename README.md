# OOTP 27 Radio Companion

This repository currently contains Milestone 3: deterministic extraction and
speech for the static game-1596 recap plus read-only validation of a selected
live `.lg` save directory. It does not detect or speak a live game yet.

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
22 passed
```

## Preview the narration

To print exactly what would be spoken without producing audio:

```bash
python3 -m ootp_radio.cli speak-recap tests/fixtures/game_1596/game_box_1596.html --dry-run
```

The narration begins with WBAL News Radio because the recap mentions the
Baltimore Orioles. Baltimore is currently the only team-to-station mapping.

## Manual Milestone 3 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli doctor \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

The command should report at least these successful checks:

```text
PASS: save directory exists
PASS: replays directory exists
PASS: box_scores directory exists
PASS: messages directory exists
```

Missing required directories are reported as `FAIL` and produce a nonzero exit
status. Missing optional game-log, message, or league-report directories are
reported as `WARN` without failing validation. This command only checks path
structure; live-game detection and narration deliberately remain out of scope.
