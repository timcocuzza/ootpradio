# OOTP 27 Radio Companion

This repository currently contains Milestone 12B: the reorderable broadcast
composer plus cancellable, latest-wins automatic playback. A stable newer game
terminates obsolete audio, replaces pending work, and begins only the newest
broadcast. The GUI and off-day detection are not connected yet.

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
127 passed
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

## Manual Milestone 12B test

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

The current game begins immediately with Highlights. While it is speaking,
complete or simulate another game. As soon as the newer replay and box score
are stable, the old `say` process must stop and only the newest game may begin;
intermediate pending games are replaced rather than queued. Press `Control-C`
to stop listening and terminate active audio.

The monitor rejects partially written replacements, never replays the same game,
and continues listening after a manual playback stop. News remains lazily
prepared last, so it cannot delay earlier selected segments. The production
speaker uses `subprocess.Popen` without a shell and distinguishes deliberate
cancellation from a genuine text-to-speech failure.
