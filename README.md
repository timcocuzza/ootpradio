# OOTP 27 Radio Companion

This repository currently contains Milestone 1: a minimal Python package, the
four game-1596 regression fixtures, and deterministic extraction of the recap
subject and body from OOTP's explicit HTML comment markers. It does not speak
game data or access a live save yet.

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
7 passed
```

## Manual Milestone 1 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli parse-recap tests/fixtures/game_1596/game_box_1596.html
```

The command should exit successfully. Its first line should be:

```text
Baltimore Gets 7-4 Win
```

The recap should contain readable paragraphs and no HTML tags or recap-marker
comments. This milestone only prints the static fixture; speech and live-save
access deliberately remain out of scope.
