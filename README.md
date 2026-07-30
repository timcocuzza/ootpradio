# OOTP 27 Radio Companion

This repository currently contains Milestone 12C: reorderable, cancellable,
latest-wins playback for both controlled-team games and off days. A stable
newer day terminates obsolete audio, replaces pending work, and begins only the
newest broadcast. The GUI is the next milestone.

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
147 passed
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

## Preview the latest complete day

This command automatically distinguishes a Baltimore game from a Baltimore
off day:

```bash
python3 -m ootp_radio.cli broadcast-preview \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg" \
  --team-name "Baltimore Orioles" \
  --segment highlights \
  --segment team-recap \
  --segment scores \
  --segment news
```

On a game day, all selected segments are eligible. On an off day, Highlights
and Team Recap are omitted, every MLB result in the slate is included under
Scores, and qualifying new headlines remain last. If the slate contains
Baltimore but its replay is still being written, classification waits rather
than leaking Baltimore's final score as an apparent off day.

## Manual Milestone 12C test

With the environment active, run:

```bash
python3 -m ootp_radio.cli watch-broadcast \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg" \
  --team-name "Baltimore Orioles" \
  --segment highlights \
  --segment team-recap \
  --segment scores \
  --segment news \
  --play-current
```

The current complete day begins immediately. On a game day it starts with
Highlights. On a Baltimore off day it silently omits Highlights and Team Recap,
then starts with every available score around the league. While it is speaking,
complete another game or advance through an off day. As soon as the newer event
is stable, the old `say` process must stop and only the newest event may begin;
intermediate work is replaced rather than queued. Press `Control-C` to stop
listening and terminate active audio.

The monitor rejects partially written score batches, never replays the same
game or off-day date, and continues listening after a manual playback stop.
News remains lazily prepared last, so it cannot delay earlier selected
segments. The production speaker uses `subprocess.Popen` without a shell and
distinguishes deliberate cancellation from a genuine text-to-speech failure.

## Current module structure

- `box_score_parser.py` parses MLB finals and discovers replay-anchored or
  replay-free stable league slates.
- `radio_event.py` resolves the selected OOTP team ID and safely classifies the
  latest slate as a game day or off day.
- `broadcast.py` lazily composes ordered game-day and off-day sections; News is
  always pinned last.
- `broadcast_controller.py` owns the single latest-wins playback slot and
  interrupts obsolete macOS speech.
- `speech.py` controls the macOS `say` process without changing OOTP files.
- `cli.py` exposes previews and the watcher while the GUI is being built.
