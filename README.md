# OOTP 27 Radio Companion

This repository currently contains Milestone 12A: a tested, reorderable
broadcast composer on top of the recap, highlights, MLB scores, and filtered
news parsers. It is a printed preview foundation for the GUI; the automatic
watcher has not yet been switched to the new segment pipeline.

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
112 passed
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

## Manual Milestone 12A test

With the environment active, run:

```bash
python3 -m ootp_radio.cli broadcast-preview \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg" \
  --team-name "Baltimore Orioles" \
  --segment news \
  --segment highlights \
  --segment team-recap \
  --segment scores
```

The requested order deliberately puts News first. The effective order must move
it to the end while preserving the relative order of Highlights, Team Recap,
and Scores. The Highlights section must begin directly with OOTP action and
contain no WBAL introduction. WBAL appears only when the Team Recap section is
reached. The News section prints selected headlines only, never message bodies.

Optional segments with no content are reported as `Skipped` without removing
ready sections. Composition is lazy: the future player can begin an earlier
segment before the delayed News parser is invoked. No speech or automatic
watcher behavior changes in this milestone.
