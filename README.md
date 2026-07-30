# OOTP 27 Radio Companion

This repository currently contains Milestone 4: static recap parsing and
speech, read-only save validation, and detection of the latest played game from
its numeric replay file. It does not speak a live game yet.

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
32 passed
```

## Preview the narration

To print exactly what would be spoken without producing audio:

```bash
python3 -m ootp_radio.cli speak-recap tests/fixtures/game_1596/game_box_1596.html --dry-run
```

The narration begins with WBAL News Radio because the recap mentions the
Baltimore Orioles. Baltimore is currently the only team-to-station mapping.

## Manual Milestone 4 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli latest-game \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

For the current save snapshot, the command should report:

```text
Game ID: 1596
Box score: game_box_1596.html
Replay: replay_1596.rpl
Game log: log_1596.txt
Highlight: highlight_1596.rpl
```

Detection is anchored to the newest numeric `replay_<GAME_ID>.rpl`, not the
newest box score. The replay and required matching box score must retain the
same size and modification time across two polls before the command reports
them ready. Game-log and highlight files remain optional. This milestone does
not parse or speak the detected live game.
