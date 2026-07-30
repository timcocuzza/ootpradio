# OOTP 27 Radio Companion

This repository currently contains Milestone 10: the recap and score broadcast,
printed MLB news filtering, and experimental printed extraction of OOTP's
binary highlight commentary. News and highlights are not connected to speech.

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
97 passed
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

## Manual Milestone 10 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli highlights-preview \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

The command should identify the latest game, report how many highlight sequences
were found, and print each sequence in game order. Standalone roster metadata,
binary noise, and the raw filename are excluded. Sentences that legitimately
mention a repeated player name remain intact.

The extractor is pure Python and read-only; it does not invoke the external
`strings` utility or modify the OOTP file. Recap mode does not depend on this
experimental parser. Highlight speech remains disabled until the preview text
is approved across multiple games.
