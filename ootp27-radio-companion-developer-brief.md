# OOTP 27 Radio Companion — Developer Brief

## 1. Purpose of this document

This document introduces the entire project from scratch and defines the order in which it must be built.

**The most important development rule is: do not build the whole product at once.**

This project must be implemented as a sequence of small, testable milestones. At the end of every milestone:

1. Stop development.
2. Give Tim one short command or action to test.
3. State the exact result he should see or hear.
4. Wait for Tim to confirm that the milestone works.
5. Only then begin the next milestone.

Do not combine milestones into one large pull request. Do not quietly continue into later features because the earlier step “seems to work.” Tim needs to test each layer against his real OOTP installation before more complexity is added.

---

## 2. Project summary

Tim plays **Out of the Park Baseball 27** on macOS. He wants a local companion application that can read his most recently completed game recap aloud while he does other work.

The longer-term vision is an immersive, personalized radio station for his fictional baseball universe. After narrating his own game, it could continue with:

- Highlights from the game
- Scores from around Major League Baseball
- League news
- Injuries and transactions
- Awards and statistical leaders
- Power rankings
- Important stories involving his organization
- Eventually, a full OOTP-style replay broadcast

The application should begin as a **read-only local companion**, not a Steam Workshop mod and not an in-game modification.

OOTP already writes the required information into readable files inside each saved league directory. We should consume those files without changing them.

---

## 3. User environment and confirmed save path

Tim is currently using macOS.

His OOTP saved league is located at:

```text
/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg
```

Important:

- The unusual location is correct. It is directly under `/Users/timcocuzza/Application Support`, not under `~/Library/Application Support`.
- The production application must **not hardcode this path**.
- It may be the default in Tim's local development configuration, but the user must be able to choose or change the `.lg` directory.
- Paths contain spaces and must be handled using proper path APIs, not hand-built shell strings.

The project should use `pathlib.Path` if Python is selected.

---

## 4. What has already been confirmed from the real save

A real completed game was collected as a development fixture: **game ID 1596**.

The sample game was:

```text
Sunday, August 1, 2032
Baltimore Orioles 7
Detroit Tigers 4
Comerica Park
```

The save produced four matching files:

```text
news/html/box_scores/game_box_1596.html
news/txt/leagues/log_1596.txt
replays/highlight_1596.rpl
replays/replay_1596.rpl
```

The shared number `1596` is the game ID and connects all four representations of the game.

The sample collection also contained:

```text
12 same-slate MLB box scores
47 recently written message files
13 recently refreshed league power-ranking reports
```

The application should use these readable files instead of trying to decode OOTP's main binary database files.

---

## 5. Confirmed file behavior

### 5.1 Box score HTML

The primary box score is:

```text
news/html/box_scores/game_box_<GAME_ID>.html
```

OOTP places a polished prose recap inside explicit HTML comments:

```html
<!--RECAP_SUBJECT_START-->
Baltimore Gets 7-4 Win
<!--RECAP_SUBJECT_END-->

<!--RECAP_TEXT_START-->
...recap HTML...
<!--RECAP_TEXT_END-->
```

This is the safest and easiest first data source.

For game 1596, the recap identifies:

- DJ Layton as the main offensive contributor
- Parker Hutyra as the winning pitcher
- Cody Laweryson with his 29th save
- Thomas Sosa's two-run double as a major play
- Baltimore improving to 63-43

The first release should extract this existing recap and narrate it. Do not generate a replacement recap with AI.

### 5.2 Structured game log

The structured game log is:

```text
news/txt/leagues/log_<GAME_ID>.txt
```

Despite the `.txt` extension, its content includes HTML links and tagged event records.

Observed record prefixes include:

```text
[%T] inning/half-inning header
[%B] batter or pitcher context
[%N] pitch or play event
[%F] end-of-half-inning summary
```

Example:

```text
[%T] Top of the 1st - Baltimore Orioles batting ...
[%B] Batting: SHB Aron Estrada
[%N] 3-2: SINGLE ...
[%F] Top of the 1st over - 0 runs, 1 hit ...
```

This source is useful later for structured play-by-play analysis. It is not required for the first audible recap.

### 5.3 Highlight replay

The highlight replay is:

```text
replays/highlight_<GAME_ID>.rpl
```

It is a binary file, but it contains long readable strings in their original order. Those strings include OOTP's natural-language commentary for selected important plays.

For game 1596, readable commentary included:

```text
Cardozo delivers an RBI double.
The score is 1-0, Orioles in front.

It's a 2-RBI double by Sosa.
The Orioles add to their lead -- it's 5-1.
```

This source should become a later “Highlights” mode only after the ordinary recap is stable.

### 5.4 Full replay

The full replay is:

```text
replays/replay_<GAME_ID>.rpl
```

It also contains readable OOTP broadcast text, including:

- Pregame setup
- Team records and standings context
- Weather
- Starting pitchers
- Batter introductions
- Pitch and play descriptions
- Inning summaries
- Score updates
- Final-game language

The full replay began with text similar to:

```text
Welcome to this afternoon's game at Comerica Park!
Today, the Tigers will battle the Orioles.
Baltimore holds down first place in the American League East Division...
```

This makes a full radio-replay mode possible, but parsing a binary replay reliably is more fragile than parsing the HTML recap. It must not be part of the first milestone.

### 5.5 Message files

League and organization news is stored in individual files such as:

```text
messages/message2201.txt
messages/message2220.txt
```

The first line is generally a headline, followed by a body.

OOTP embeds references using syntax such as:

```text
<Yadier Munoz:player#130290>
<Baltimore Orioles:team#3>
```

For narration, convert those references to their visible names:

```text
Yadier Munoz
Baltimore Orioles
```

A suitable transformation is conceptually:

```regex
<([^:>]+):(?:player|team|league|coach)#[^>]+>  ->  $1
```

Do not read every new message. The sample contained MLB stories mixed with a large amount of minor-league news. Filtering is mandatory before “Around the League” is useful.

### 5.6 Same-slate box scores

When Tim completed game 1596, OOTP wrote multiple MLB box scores at nearly the same timestamp:

```text
game_box_1593.html through game_box_1604.html
```

There were 12 same-slate MLB games in the sample.

These can power an “Around the League” score segment. The simulated games may not contain polished prose recap sections, so the application should create short deterministic summaries from the box-score fields.

Example target sentence:

```text
Elsewhere around the league, Seattle defeated Texas 10 to 3, while Miami shut out Philadelphia 12 to nothing.
```

No AI is required for this.

---

## 6. Non-negotiable engineering constraints

### 6.1 Read-only access

The application must not write to, rename, move, delete, lock, or modify anything inside the `.lg` save directory.

All application state must be stored outside the OOTP save, for example:

```text
~/Library/Application Support/OOTPRadio/
```

or, during development:

```text
./var/
```

### 6.2 No `.dat` reverse engineering for the MVP

Do not parse or modify these files for the initial product:

```text
players.dat
teams.dat
world.dat
messages.dat
text_data.dat
```

They are unnecessary for the first useful version.

### 6.3 No AI dependency in the MVP

Do not add an OpenAI API, local LLM, prompt system, embeddings, vector database, or generated commentary until the deterministic pipeline works.

The initial recap already exists in OOTP's HTML. macOS already provides text-to-speech through `say`.

### 6.4 No UI before the core pipeline works

Do not begin with:

- A menu-bar application
- SwiftUI screens
- Electron
- A web dashboard
- Settings windows
- Artwork or branding
- Steam Workshop packaging

The first implementation should be a small command-line tool. A UI can wrap it later.

### 6.5 Do not combine milestones

A pull request should address one milestone only. Every milestone should include:

- Implementation
- Automated tests
- One manual test command for Tim
- Expected output
- Notes about known limitations

---

## 7. Recommended initial technology

The recommended MVP stack is:

```text
Python 3.11+
Standard library where practical
BeautifulSoup optional for HTML parsing
pytest for tests
macOS `say` command for speech
```

Reasons:

- Fast iteration
- Excellent filesystem support
- Easy HTML parsing
- Easy subprocess integration with `say`
- Easy conversion into a packaged Mac application later
- Core logic remains independent of the final UI

Do not select Electron or Swift merely to create a polished shell before the data pipeline works.

A reasonable project structure is:

```text
ootp-radio/
├── README.md
├── pyproject.toml
├── src/
│   └── ootp_radio/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── paths.py
│       ├── recap_parser.py
│       ├── game_detector.py
│       ├── watcher.py
│       ├── speech.py
│       ├── box_score_parser.py
│       ├── message_parser.py
│       ├── replay_strings.py
│       └── state.py
├── tests/
│   ├── fixtures/
│   │   └── game_1596/
│   ├── test_recap_parser.py
│   ├── test_game_detector.py
│   ├── test_box_score_parser.py
│   ├── test_message_parser.py
│   └── test_replay_strings.py
└── var/
    └── state.json
```

This is a target structure, not permission to create every module immediately. Add modules only when their milestone begins.

---

## 8. Minimal internal data models

Do not pass raw HTML strings throughout the application. Parse files into small typed models.

Suggested models:

```python
@dataclass(frozen=True)
class GameFiles:
    game_id: int
    replay_path: Path
    box_score_path: Path
    game_log_path: Path | None
    highlight_path: Path | None


@dataclass(frozen=True)
class GameRecap:
    game_id: int
    subject: str
    body: str
    narration_text: str


@dataclass(frozen=True)
class GameResult:
    game_id: int
    date: str | None
    away_team: str
    away_score: int
    home_team: str
    home_score: int
```

Keep parsing, narration formatting, and speech output separate.

---

# 9. Required milestone plan

## Milestone 0 — Repository and fixture setup

### Goal

Create the smallest runnable Python project and add the supplied game-1596 files as test fixtures.

### Build only

- Python package skeleton
- `pytest` configuration
- A fixture directory containing copies of:
  - `game_box_1596.html`
  - `log_1596.txt`
  - `highlight_1596.rpl`
  - `replay_1596.rpl`
- One smoke test that confirms the four fixture files exist

Do not parse anything yet.

### Automated test

```bash
pytest -q
```

Expected result:

```text
1 passed
```

### Tim's manual test

Give Tim:

```bash
python3 -m ootp_radio.cli --help
```

Expected result:

- Command exits successfully
- Shows a very small help page
- Does not require an OOTP save path yet

### Stop condition

Stop and wait for Tim's confirmation.

---

## Milestone 1 — Parse one static OOTP recap

### Goal

Parse the recap subject and body from the static `game_box_1596.html` fixture.

### Build only

- `recap_parser.py`
- HTML comment-marker extraction
- HTML tag removal
- HTML entity decoding
- Whitespace normalization
- A CLI command that prints parsed JSON or plain text

Use the explicit markers:

```text
<!--RECAP_SUBJECT_START-->
<!--RECAP_SUBJECT_END-->
<!--RECAP_TEXT_START-->
<!--RECAP_TEXT_END-->
```

Do not use broad CSS selectors when explicit markers are available.

### Expected parsed values

Subject:

```text
Baltimore Gets 7-4 Win
```

The body must include these facts:

```text
DJ Layton
Parker Hutyra
Cody Laweryson
Thomas Sosa
63-43
```

The output must not include:

```text
<a href=
<!--RECAP
<br>
```

### Automated tests

At minimum:

1. Extracts the exact subject.
2. Body includes the expected names and record.
3. HTML tags are removed.
4. `<br><br>` becomes sensible paragraph spacing or pauses.
5. Missing recap markers produce a clear typed error, not a cryptic exception.

### Tim's manual test

Give Tim one command similar to:

```bash
python3 -m ootp_radio.cli parse-recap tests/fixtures/game_1596/game_box_1596.html
```

Expected first line:

```text
Baltimore Gets 7-4 Win
```

### Stop condition

Do not add speech yet. Stop and wait for Tim to confirm that the printed recap is correct and readable.

---

## Milestone 2 — Speak the static recap

### Goal

Read the already parsed static recap aloud with macOS text-to-speech.

### Build only

- `speech.py`
- A `MacSaySpeaker` implementation
- Voice option
- Rate option
- Safe subprocess argument handling
- A `--dry-run` mode that prints the final narration without speaking

Use subprocess argument arrays. Do not construct a shell command by concatenating recap text.

Example concept:

```python
subprocess.run(
    ["say", "-v", voice, "-r", str(rate), narration_text],
    check=True,
)
```

### Default narration format

Something similar to:

```text
Your OOTP postgame report. Baltimore Gets 7-4 Win. [recap body]
```

Do not add invented analysis.

### Automated tests

- Mock subprocess; do not make automated tests speak.
- Confirm voice and rate are passed as separate arguments.
- Confirm recap text is passed safely as one argument.
- Confirm a missing `say` executable produces a useful error.

### Tim's manual test

```bash
python3 -m ootp_radio.cli speak-recap tests/fixtures/game_1596/game_box_1596.html
```

Expected result:

- The Mac reads the game-1596 recap aloud.
- No HTML is spoken.
- Names and score sound understandable.

Ask Tim specifically to confirm:

1. Does the voice work?
2. Is the speed comfortable?
3. Does the recap contain unwanted text?

### Stop condition

Stop and wait for Tim's confirmation before touching his live save.

---

## Milestone 3 — Validate a selected live `.lg` directory

### Goal

Accept Tim's real `.lg` path and confirm that required directories exist.

### Build only

- Configuration loading
- `doctor` command
- Path validation
- No game detection yet

Required directories for the first release:

```text
replays/
news/html/box_scores/
```

Optional directories to report:

```text
news/txt/leagues/
messages/
news/html/leagues/
```

### Configuration

Support either:

```bash
--save-dir "/path/to/league.lg"
```

or a small local configuration file.

For Tim's machine, use:

```text
/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg
```

Do not save absolute paths in source control.

### Tim's manual test

```bash
python3 -m ootp_radio.cli doctor \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

Expected output should clearly show:

```text
PASS: save directory exists
PASS: replays directory exists
PASS: box_scores directory exists
PASS: messages directory exists
```

### Stop condition

Stop and wait for confirmation. Do not detect or speak the latest game in this milestone.

---

## Milestone 4 — Detect the latest played game

### Goal

Identify the most recently played game and resolve its matching files.

### Confirmed detection strategy

1. Find files matching:

   ```text
   replays/replay_*.rpl
   ```

2. Select the most recently modified replay file.
3. Extract the numeric game ID from its filename.
4. Resolve:

   ```text
   news/html/box_scores/game_box_<ID>.html
   news/txt/leagues/log_<ID>.txt
   replays/highlight_<ID>.rpl
   ```

5. Require the matching box score for recap mode.
6. Treat the game log and highlight replay as optional for now.

Why use a replay file as the primary signal?

OOTP writes box scores for the entire simulated slate at the same time. The newest box score alone does not reliably identify Tim's played game. The matching full replay identifies the game that OOTP retained as the played game.

### Stability requirement

Do not read a file while OOTP may still be writing it.

Before parsing, require at least one of these protections:

- File size and modification time remain unchanged across two polls
- Or a short debounce delay followed by a second stat check

Do not use a fixed sleep as the only correctness mechanism.

### Automated tests

Create temporary fake save directories that test:

1. Latest replay ID is selected correctly.
2. Matching box score is resolved.
3. Spaces in paths work.
4. Missing matching box score returns a clear “not ready” state.
5. Unrelated `.rpl` files are ignored.
6. Non-numeric filenames are ignored.

### Tim's manual test

```bash
python3 -m ootp_radio.cli latest-game \
  --save-dir "/Users/timcocuzza/Application Support/Out of the Park Developments/OOTP Baseball 27/saved_games/first os.lg"
```

For the current fixture/save snapshot, expected output includes:

```text
Game ID: 1596
Box score: game_box_1596.html
Replay: replay_1596.rpl
Game log: log_1596.txt
Highlight: highlight_1596.rpl
```

### Stop condition

Stop and wait for Tim's confirmation that the correct latest game is detected.

---

## Milestone 5 — Speak the latest real recap on demand

### Goal

Connect milestones 1–4 into one manual command.

### Build only

A command such as:

```bash
python3 -m ootp_radio.cli recap-latest --save-dir "..."
```

Pipeline:

```text
validate save
→ detect latest played game
→ wait for stable files
→ parse matching recap
→ create narration text
→ speak it
```

### State behavior

At this milestone, it is acceptable to replay the same latest recap whenever the command is run. Automatic duplicate prevention belongs in the watcher milestone.

### Tim's manual test

Tim should:

1. Run the command against the real save.
2. Confirm the latest completed game is narrated.
3. Complete another OOTP game.
4. Run the command again.
5. Confirm the newly completed game is narrated instead of game 1596.

### Stop condition

This is the first genuinely useful MVP. Stop and let Tim use it before adding automatic watching.

---

## Milestone 6 — Automatic watcher and duplicate prevention

### Goal

Automatically narrate a recap after a newly completed played game appears.

### Build only

- Polling watcher or filesystem event watcher
- Debounce/stability check
- Persistent last-processed game ID
- Clear logs
- Graceful shutdown with Control+C

For reliability, a simple polling loop is acceptable initially.

Suggested flow:

```text
poll replays/
→ identify newest replay_<ID>.rpl
→ compare ID with last processed ID
→ wait until replay and box score are stable
→ parse recap
→ speak recap
→ persist processed ID only after successful speech command
```

### State file

Store state outside the save directory, such as:

```json
{
  "last_processed_game_id": 1596,
  "last_processed_at": "2032-08-01T..."
}
```

Use atomic writes for the state file.

### Required behavior

- Starting the watcher must not immediately replay old games unless `--play-current` is explicitly supplied.
- A failed parse must not mark the game processed.
- A failed speech command must be logged clearly.
- Multiple filesystem events for the same game must produce one narration.
- Restarting the application must not repeat the last processed game.

### Tim's manual test

1. Start watcher.
2. Complete or simulate one game in OOTP.
3. Confirm exactly one recap begins after the game files finish writing.
4. Leave watcher running for several minutes.
5. Confirm the recap does not repeat.
6. Restart watcher.
7. Confirm the old game still does not repeat.

### Stop condition

Stop here for an initial release candidate. Fix watcher reliability before adding highlights or league news.

---

## Milestone 7 — Parse same-slate MLB scores

### Goal

Create a deterministic “Around the League” score segment.

### Build only

- Parse team names and final scores from box-score HTML
- Discover box scores written in the same slate as the played game
- Generate concise score sentences
- No messages and no replay commentary yet

### Same-slate discovery

Initial acceptable method:

- Use the played replay's modification time
- Include box scores whose modification times fall within a small tested window, such as ±5 seconds
- Validate that game date/league fields match where available

Do not assume game IDs are always contiguous.

### Required parser output

```python
GameResult(
    game_id=1596,
    away_team="Baltimore Orioles",
    away_score=7,
    home_team="Detroit Tigers",
    home_score=4,
)
```

### Narration rules

Prefer deterministic phrasing:

```text
Seattle defeated Texas, 10 to 3.
Miami shut out Philadelphia, 12 to nothing.
The White Sox edged the Yankees, 8 to 7.
```

It is acceptable to begin with one neutral template for all games. Do not spend this milestone building a sophisticated language engine.

### Tim's manual test

```bash
python3 -m ootp_radio.cli scores-latest --save-dir "..."
```

Expected for the game-1596 sample:

- 12 games found
- Includes Baltimore 7, Detroit 4
- Does not include minor-league games
- Does not duplicate a game

### Stop condition

Stop and let Tim confirm that the slate is correct before connecting it to speech.

---

## Milestone 8 — Narrate “Around the League” scores

### Goal

After Tim's recap finishes, optionally read the same-slate MLB results.

### Build only

- `--around-league` option
- A short transition sentence
- Score narration
- Pause/cancel behavior if practical

Example:

```text
Now, around the league. Seattle defeated Texas, 10 to 3...
```

### Configuration

Allow:

```text
recap only
recap plus scores
```

Do not force a long league segment every time.

### Tim's manual test

Complete one game and confirm:

1. His recap plays first.
2. Around-the-league scores begin afterward.
3. His own result is either omitted from the second segment or clearly not repeated unnecessarily.

### Stop condition

Stop before adding news messages.

---

## Milestone 9 — Parse and filter recent league messages

### Goal

Extract useful MLB-level headlines without reading dozens of irrelevant minor-league stories.

### Build only

- Parse headline and body
- Strip OOTP entity references
- Detect recently modified messages
- Conservative filtering
- Printed preview only; no speech yet

### Initial filtering policy

Start narrowly. Include a message only when at least one condition is true:

- It explicitly says `Major League Baseball`
- It references Tim's configured organization/team
- It is a major injury or transaction involving the configured team
- It is an MLB weekly award or MLB power-ranking message

Do not include every minor-league power ranking, weekly award, statistical leader, or injury.

### Example cleanup

Input:

```text
<Baltimore Orioles:team#3>
```

Output:

```text
Baltimore Orioles
```

### Tim's manual test

```bash
python3 -m ootp_radio.cli news-preview --save-dir "..."
```

The command should print a short selected list and also report counts:

```text
47 recent messages examined
4 selected
43 filtered out
```

The exact selected count may differ, but the output must explain why each message was selected.

### Stop condition

Tim must approve the filter quality before news is spoken.

---

## Milestone 10 — Highlight narration from `.rpl`

### Goal

Extract OOTP's existing natural-language highlight commentary from `highlight_<ID>.rpl`.

### Important warning

This is the first feature that touches a binary-formatted file. Treat the extraction as experimental and isolated.

Do not make recap mode depend on replay parsing.

### Suggested extraction approach

- Open the file in binary mode
- Extract ordered runs of printable UTF-8/ASCII characters above a minimum length
- Preserve order
- Remove obvious metadata and repeated noise
- Keep commentary lines
- Join lines into narration-friendly paragraphs

Do not modify the file.

Do not require the external Unix `strings` command in core production logic unless there is a documented fallback. A pure-Python extractor is more portable and testable.

### Known noise

The sample replay repeatedly contains the string:

```text
Bradfield Jr.
```

This may be metadata or an internal substitution artifact and should not be blindly narrated every time.

Filtering must be rule-based and tested. Do not simply remove all repeated names globally because repetition can be legitimate commentary.

### Automated fixture assertions

Extracted game-1596 highlights should include phrases equivalent to:

```text
Cardozo delivers an RBI double.
The score is 1-0, Orioles in front.
It's a 2-RBI double by Sosa.
The Orioles add to their lead -- it's 5-1.
```

Output should not begin with the raw filename.

### Tim's manual test

First provide a preview command:

```bash
python3 -m ootp_radio.cli highlights-preview --save-dir "..."
```

Only after Tim approves the text should a separate speech command be enabled.

### Stop condition

Do not begin full replay mode until highlights work across multiple games.

---

## Milestone 11 — Full replay broadcast

### Goal

Narrate OOTP's full replay commentary.

This is a later enhancement, not MVP work.

### Requirements before starting

- Recap watcher is stable
- At least several different `.rpl` files have been tested
- Highlight parser is reliable
- Tim approves the pacing and voice

### Expected challenges

- Very long output
- Repeated internal strings
- Pronunciation
- Natural pause placement
- Ability to pause, resume, skip, and stop
- Avoiding speech queue overload
- File-format changes in future OOTP updates

Full replay should be chunked, not sent to `say` as one enormous uninterruptible string.

### Stop condition

This milestone requires separate design approval before implementation.

---

## Milestone 12 — User interface and packaging

Only begin this after the CLI pipeline is reliable.

Potential form:

- macOS menu-bar application
- Buttons for:
  - Recap
  - Highlights
  - Full Broadcast
  - Around the League
  - Stop
- Save-folder selector
- Voice selector
- Speech-rate selector
- Automatic mode toggle

The UI should call the already tested core services. It should not duplicate parser or watcher logic.

Steam Workshop integration is not required for the first product and may not be the right distribution method at all.

---

## 10. Configuration requirements

A future configuration object may contain:

```toml
save_dir = "/path/to/league.lg"
team_id = 3
team_name = "Baltimore Orioles"
voice = "Samantha"
speech_rate = 185
auto_watch = true
play_current_on_start = false
include_around_league = false
include_news = false
poll_interval_seconds = 2
```

Do not require all fields immediately.

Important:

- Team ID `3` and Baltimore are values observed in the supplied fixture.
- They must not be permanently hardcoded.
- The application should eventually identify or ask for the controlled team.

---

## 11. Error handling expectations

Every user-facing error should explain the failed step and likely remedy.

Good:

```text
The latest replay is game 1605, but game_box_1605.html is not ready yet. Retrying.
```

Bad:

```text
FileNotFoundError: [Errno 2]
```

Required conditions to handle:

- Save path does not exist
- Selected folder is not an `.lg` directory
- Missing `replays` directory
- No replay files yet
- Matching box score not written yet
- Empty recap markers
- Malformed HTML
- OOTP is still writing files
- macOS `say` unavailable or fails
- State file corrupted
- Permissions denied
- Game already processed

Do not crash the watcher permanently because one game has a malformed or temporarily incomplete file.

---

## 12. Logging expectations

Use structured, concise logs.

Example:

```text
INFO save_validated path=".../first os.lg"
INFO replay_detected game_id=1605
INFO waiting_for_stable_file path=".../game_box_1605.html"
INFO recap_parsed game_id=1605 subject="..."
INFO speech_started game_id=1605 mode=recap
INFO game_marked_processed game_id=1605
```

Never log the entire save contents or enormous recap/replay bodies by default.

A `--verbose` flag may expose more details during development.

---

## 13. Testing philosophy

Tests must be fixture-based and filesystem-safe.

### Unit tests

Cover:

- Marker extraction
- HTML cleanup
- Entity-reference cleanup
- Game-ID parsing
- Path matching
- File-stability checks
- Narration formatting
- Message filtering
- Replay printable-string extraction

### Integration tests

Create temporary fake `.lg` directory trees. Do not point automated tests at Tim's live save.

### Manual tests

Every milestone must give Tim exactly one primary test command and expected result.

Do not give Tim five commands with no explanation. Do not say “it should work.” State what he should see or hear.

### Regression fixtures

After the initial game-1596 fixture works, collect several more games covering:

- Home and away games
- Wins and losses
- Extra innings
- Shutouts
- Games without a recap section, if possible
- Games with unusual team names
- Postseason games
- Doubleheaders

Do not generalize from one fixture without regression tests.

---

## 14. Definition of MVP

The MVP is complete when all of the following are true:

1. Tim can configure his `.lg` save directory.
2. The application identifies his newest played game through `replay_<ID>.rpl`.
3. It waits until the matching box score is stable.
4. It extracts the official OOTP recap subject and body.
5. It reads the recap aloud with a selected macOS voice and rate.
6. Watch mode narrates each new game exactly once.
7. Restarting the watcher does not replay the previously processed game.
8. The OOTP save remains untouched.
9. Errors are understandable.
10. Tim has personally confirmed each milestone before the next one was started.

The following are **not required for MVP**:

- Full-game broadcast
- Highlights
- Around-the-league news
- AI-generated writing
- GUI
- Steam Workshop
- Cross-platform packaging
- `.dat` parsing

---

## 15. Explicit instructions to the developer

Please follow these rules even when later features appear easy to add:

1. **Do not implement the entire roadmap in one pass.**
2. **Do not create a polished interface before the CLI works.**
3. **Do not add AI before deterministic extraction works.**
4. **Do not reverse-engineer OOTP `.dat` files for this version.**
5. **Do not write inside Tim's save directory.**
6. **Do not hardcode game ID 1596, Baltimore, team ID 3, or Tim's absolute path into application logic.**
7. **Do use game 1596 as a regression fixture.**
8. **Do give Tim one clear test after every milestone.**
9. **Do wait for Tim's confirmation before proceeding.**
10. **Do keep each pull request limited to one milestone.**

A smaller working step is more valuable than a large partially working system.

---

## 16. First assignment

Begin with **Milestone 0 only**.

Deliver:

- Minimal Python project
- Four game-1596 fixture files
- One fixture-presence test
- CLI help command
- Setup instructions
- One manual test for Tim

Do not implement recap parsing, speech, live save access, a watcher, highlights, league scores, news, or a UI in the first assignment.

After Tim confirms Milestone 0, proceed to Milestone 1.
