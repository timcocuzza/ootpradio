# OOTP 27 Radio Companion

This repository currently contains Milestone 12D: a native macOS GUI over the
reorderable, cancellable, latest-wins game/off-day broadcast engine. A stable
newer day terminates obsolete audio, replaces pending work, and begins only the
newest broadcast.

## Requirements

- Python 3.11 or newer
- Tk support matching the selected Python version
- macOS `say` for speech playback

## Setup

From this directory, create an isolated environment and install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

If Homebrew Python reports `No module named '_tkinter'`, install its matching
Tk package. This workspace uses Python 3.13:

```bash
brew install python-tk@3.13
```

Run the automated smoke test:

```bash
pytest -q
```

Expected result:

```text
169 passed
```

## Open the desktop app

```bash
python3 -m ootp_radio.cli gui
```

The window provides the save folder, controlled team, macOS voice and optional
speech rate, enabled broadcast options, drag ordering, off-day behavior, and
the file-check interval. `macOS System Default` passes no voice override to
`say`, so playback uses the user's configured Mac voice.

`Start Listening` validates the selected `.lg` folder and saves settings to
`~/Library/Application Support/OOTP Radio/settings.json`, never inside the
OOTP save. `Stop Playback` ends only current speech. `Stop Listening` ends both
speech and file monitoring.

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

## Manual Milestone 12D test

Launch the desktop app:

```bash
python3 -m ootp_radio.cli gui
```

Choose the live `.lg` save, leave the voice on `macOS System Default`, enable
`Play current day when starting`, and drag Highlights above Team Radio. Press
`Start Listening`. The controls lock and the status changes to Listening while
the current game begins with OOTP play-by-play. `Stop Playback` must end speech
without changing the Listening status. `Stop Listening` must end the monitor,
return the status to Stopped, and unlock configuration. Relaunching the app
must restore the saved folder, order, toggles, voice, and rate.

## Command-line listener

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
- `app_settings.py` validates and atomically persists GUI configuration and
  provides the pure drag/toggle ordering rules.
- `listening_session.py` runs the blocking listener off Tk's event thread and
  implements Start, Stop Playback, and Stop Listening as a tested state machine.
- `gui.py` renders the native Tk window and maps its controls onto settings and
  the listening session.
- `speech.py` controls the macOS `say` process without changing OOTP files.
- `cli.py` exposes the desktop app, previews, and command-line watcher.
