# OOTP 27 Radio Companion

This repository currently contains Milestone 0: a minimal Python package and
the four game-1596 regression fixtures. It does not parse or speak game data
yet.

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
1 passed
```

## Manual Milestone 0 test

With the environment active, run:

```bash
python3 -m ootp_radio.cli --help
```

The command should exit successfully and display a short help page beginning
with `usage: ootp-radio`. It does not require an OOTP save path.

