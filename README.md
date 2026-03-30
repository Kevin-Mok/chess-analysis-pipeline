# Chess Highlights

## Overview
This repository tracks rapid-game highlights and a local-first analysis pipeline that turns PGNs into reproducible markdown reports.

### Why I Built This
I built this to replace closed, subscription-heavy review workflows with a local stack I can inspect, tune, and extend.

- Platform shift:
  - I moved most analysis toward Lichess studies and local PGN tooling.
- Tooling ownership:
  - Every analysis artifact is generated from scripts and engines in this repo.
- Cost model:
  - Baseline and advanced analysis run locally, so core workflows do not require paid API calls.
- Engineering value:
  - The project demonstrates reproducible CLI automation, multi-engine orchestration, and deterministic fallback behavior.

## SWE Recruiter View
This is an engineering project, not only a game archive: it automates chess forensics from PGN input to evidence-backed outputs.

- PGN parsing + POV-oriented move-by-move engine table (`Win%`, `Loss%`, `Draw%`, eval) via `analyze_pgn.py`.
- Critical expected-score swing detection (Critical-only) with configurable threshold, scope, and max events.
- Forensic mode behavior: Stockfish + Lc0 best-move comparison, PV evidence, and opportunity-cost estimates.
- Optional local `forensic-llm` rewrite path (`ollama` or `llama-cli`) for human-coaching style explanations.
- Deterministic fallback behavior when optional AI components are unavailable.

### Engineering Signals
- End-to-end pipeline:
  - `games/*.pgn` input to `analysis/*.md` output with a stable report structure.
- Modular analyzer internals:
  - `pgn_analyzer/` now separates constants, engine control, forensic logic, pipeline flow, and CLI parsing while preserving `python3 analyze_pgn.py ...` usage.
- Multi-runtime orchestration:
  - Integrates local binaries (`stockfish`, `lc0`, `ollama`, `llama-cli`) with explicit flags and auto-detection.
- Resilience:
  - Forensic and rewrite paths keep deterministic report generation available.
- Reproducibility:
  - Local execution avoids external API coupling for core analysis paths.

### What The Main Script Produces
- A `## How The Game Was Won` section for decisive games, with terminal mate geometry when the PGN ends in checkmate.
- A POV move table with W/L/D probabilities, `me`/`opp` turn labels, and eval deltas.
- A `## Significant Swings` block with:
  - severity,
  - expected-score before/after,
  - engine comparison (Stockfish + Lc0),
  - PV evidence,
  - concise training lesson text.
- Exact terminal-result handling for checkmate/stalemate positions before swing classification.
- Markdown output to `analysis/<game-stem>.md` by default for PGNs under `games/`, or a custom path via `--output-md`.

## AI Tooling Stack
The stack is intentionally local-first so analysis quality and runtime behavior are measurable and reproducible.

### Tool Roles
- `stockfish`:
  - Baseline evaluator for move table and forensic comparisons.
- `lc0` + `.pb.gz` weights:
  - Second-opinion engine used in forensic verification.
- `ollama` + `qwen3:14b`:
  - Default local rewrite backend for `--cause-mode forensic-llm`.
- `llama-cli` + GGUF model:
  - Optional local fallback rewrite backend when Ollama is not used.

### AI/Engine Execution Modes
- `heuristic`:
  - Fast deterministic cause labels.
- `forensic`:
  - Deterministic Stockfish + Lc0 evidence path with PV-based comparisons.
- `forensic-llm`:
  - Forensic evidence plus optional local rewrite for coaching-oriented wording.

### Why This Tooling Matters
- Local control:
  - Baseline analysis does not depend on external API availability.
- Evidence quality:
  - Reports include explicit before/after expected scores plus best-move deltas.
- Degradation behavior:
  - If forensic engine probes are unavailable, output uses deterministic text.
  - If `forensic-llm` rewrite assets are unavailable, output uses deterministic forensic text.
- Current artifact evidence:
  - `analysis/2026-03-03-comeback-vs-gaju33333.md` shows full forensic swing output and move-table evidence.
  - `analysis/2026-02-27-fast-checkmate.md` captures tactical conversion ending with `15. Qxe7#`.

## Local Analysis Pipeline
```bash
# direct analyzer usage
python3 analyze_pgn.py games/2026-03-03-comeback-vs-gaju33333.pgn

# helper script usage (name/path lookup -> analysis/<name>.md)
bash scripts/analyze_game.sh 2026-03-03-comeback-vs-gaju33333

# export an OpenOffice/LibreOffice-ready rating history CSV from the combined PGN
python3 scripts/export_elo_history_csv.py games/all/chess_com_games_2026-03-15_combined.pgn

# deterministic forensic mode (default)
python3 analyze_pgn.py games/3.4-play-well.pgn --cause-mode forensic

# forensic + local rewrite (single-line example; shell-safe)
python3 analyze_pgn.py games/3.4-play-well.pgn --cause-mode forensic-llm --llm-backend ollama --ollama-model qwen3:14b --ollama-timeout-ms 0 --ollama-max-tokens 120

# forensic + local rewrite (multiline; keep trailing \ continuations)
python3 analyze_pgn.py games/3.4-play-well.pgn \
  --cause-mode forensic-llm \
  --llm-backend ollama \
  --ollama-model qwen3:14b \
  --ollama-timeout-ms 0 \
  --ollama-max-tokens 120

# live split-stream run for 3.4-play-well
bash scripts/test_play_well_live.sh
```

### Key CLI Controls
- Core runtime:
  - `--pov-player`, `--output-md`, `--max-seconds`, `--threads`, `--hash-mb`
- Swing extraction:
  - `--swing-threshold-score`, `--swing-max-events`, `--swing-scope` (reports only `Critical` swings, with an effective minimum threshold of `0.50`)
- Forensic controls:
  - `--cause-mode heuristic|forensic|forensic-llm`, `--forensic-time-ms`, `--forensic-multipv`, `--forensic-max-pv-plies`
  - `--lc0-path`, `--lc0-weights`
- Local rewrite controls:
  - `--llm-backend auto|ollama|llama-cli`
  - `--ollama-host`, `--ollama-model`, `--ollama-timeout-ms`, `--ollama-max-tokens`, `--ollama-temperature`
  - `--llama-cli-path`, `--llama-model`, `--llama-timeout-ms`, `--llama-max-tokens`, `--llama-temperature`

### Local Setup
- Bootstrap local engine/LLM tooling:
  - `bash scripts/install_local_ai_stack.sh`
- Pull/start default Ollama model path:
  - `bash scripts/pull_qwen3_14b.sh`
- Full setup details and troubleshooting:
  - [docs/LOCAL_AI_SETUP.md](docs/LOCAL_AI_SETUP.md)

## Chess Improvement View
Current win artifacts are highlighted from tracked PGNs plus the `## How The Game Was Won` summaries in `analysis/*.md`.

- Fast tactical finish vs `Woaheee`, where `14...Nxf1` allowed `15. Qxe7#` immediately.
- Comeback mate vs `Ironmike3982` on Chess.com, where `15. Bf2` dropped the rook but the attack still finished with `27. Qh5#` about ten moves later.
- Domination win vs `creppyG` on Chess.com, where the move table reached `100.0/0.0/0.0` by move 9 and held there through `56...Qa8#`.
- Conversion win vs `gaju33333`, ending with `34...Qxc7` and an immediate resignation.
- Practical resignation win vs `AmeerIrfan`, where `40. Rc2` ended a volatile tactical race.
- Back-rank mate win as Black vs `juliok22`, finishing a compact tactical game with `26...Re1#`.
- Tense 76-move win vs `NickGen_Eral`, ending with `76. Qfh4#` after a long endgame grind.
- 14-move checkmate vs `Abhijeetnegi123`, where `13...Nxc2` allowed `14. Qxf7#` immediately.
- 80% accuracy win vs `newbie060806` on Chess.com, a game Chess.com estimated at 1150 Elo and that finished with `45. Qbb8#`.
- Mate win as Black vs `sozplayschess05` on Chess.com, where `21. Qf4` allowed `21...Qd2#` immediately.
- 34-move mate vs `rrr3009` on Lichess, where `4. Qxh8` grabbed the rook early but the attack still finished with `34...Qb4#`.
- 45-move mate vs `jinkry6` on Chess.com, where `44...Kb6` allowed `45. Qb8#` immediately.
- 53-move passed-pawn mate vs `Ethagain` on Chess.com, where `52...Ka5` allowed `53. Ra7#` right after the `b`-pawn promoted on `52. b8=Q`.

## Highlight Games
| Date | Opponent | Platform | Result | Game Link | Why it matters |
| --- | --- | --- | --- | --- | --- |
| 2026-02-27 | Woaheee | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/165298129986?move=0) | Fast tactical finish where `14...Nxf1` allowed `15. Qxe7#`. |
| 2026-03-03 | gaju33333 | Lichess | Win (Black, 0-1) | [Lichess game](https://lichess.org/nujVa4n7) | Conversion ending with `34...Qxc7`, after which White resigned. |
| 2026-03-06 | AmeerIrfan | Lichess | Win (White, 1-0) | [Lichess game](https://lichess.org/jdooSl0M) | Practical resignation win where `40. Rc2` ended the tactical race. |
| 2026-03-11 | juliok22 | Chess.com | Win (Black, 0-1) | [Chess.com game](https://www.chess.com/game/live/165814123450) | Compact back-rank mate highlight via `26...Re1#`. |
| 2026-03-11 | NickGen_Eral | Lichess | Win (White, 1-0) | [Lichess game](https://lichess.org/lY26zNo7) | Long 76-move endgame win capped by `76. Qfh4#`. |
| 2026-03-13 | Abhijeetnegi123 | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/165901228132) | Short tactical finish where `13...Nxc2` allowed `14. Qxf7#`. |
| 2026-03-15 | creppyG | Chess.com | Win (Black, 0-1) | [Chess.com analysis](https://www.chess.com/analysis/game/live/165996433052/analysis) | Move-table domination reached `100.0/0.0/0.0` by move 9 and held through `56...Qa8#`. |
| 2026-03-15 | Ironmike3982 | Chess.com | Win (White, 1-0) | [Chess.com review](https://www.chess.com/analysis/game/live/165995086288/review?move=29&move=29&tab=review&classification=greatfind&autorun=true) | Comeback mate where `15. Bf2` lost the rook but the attack still converted with `27. Qh5#`. |
| 2026-03-17 | newbie060806 | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/166077521478) | 80% accuracy game that Chess.com estimated at 1150 Elo, finished by `45. Qbb8#`. |
| 2026-03-19 | sozplayschess05 | Chess.com | Win (Black, 0-1) | [Chess.com game](https://www.chess.com/game/live/166156046882) | Clean mate finish where `21. Qf4` allowed `21...Qd2#` immediately. |
| 2026-03-22 | rrr3009 | Lichess | Win (Black, 0-1) | [Lichess game](https://lichess.org/i19C7n9W) | After `4. Qxh8` grabbed the rook early, the attack still converted with `34...Qb4#` on move 34. |
| 2026-03-28 | jinkry6 | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/166542891282?move=0) | 45-move mate where `44...Kb6` allowed `45. Qb8#` immediately. |
| 2026-03-28 | Ethagain | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/166559236480) | Passed-pawn conversion that promoted on `52. b8=Q` and finished with `53. Ra7#`. |

## Key Moves and Turning Points
- [**15. Qxe7#** (Chess.com analysis)](https://www.chess.com/analysis/game/live/165298129986/analysis?move=29): immediate mate after `14...Nxf1`.
- [**27. Qh5#** (Chess.com review)](https://www.chess.com/analysis/game/live/165995086288/review?move=29&move=29&tab=review&classification=greatfind&autorun=true): `SoloPistol` finished the comeback against `Ironmike3982` after `15. Bf2` allowed `...Bxa1`.
- [**56...Qa8#** (Chess.com analysis)](https://www.chess.com/analysis/game/live/165996433052/analysis): capped the March 15 domination game against `creppyG` after the move table had stayed at `100.0/0.0/0.0` from move 9 onward.
- [**34...Qxc7** (Lichess)](https://lichess.org/nujVa4n7#68): decisive queen trade that ended the comeback win by resignation.
- [**40. Rc2** (Lichess)](https://lichess.org/jdooSl0M): final practical move before Black resigned in the `AmeerIrfan` game.
- [**26...Re1#** (Chess.com game)](https://www.chess.com/game/live/165814123450): clean back-rank mate to finish a compact tactical win.
- [**76. Qfh4#** (Lichess)](https://lichess.org/lY26zNo7): mate finish at the end of a 76-move endgame grind.
- [**14. Qxf7#** (Chess.com analysis)](https://www.chess.com/analysis/game/live/165901228132/analysis?move=23): 14-move checkmate after `13...Nxc2`.
- [**45. Qbb8#** (Chess.com game)](https://www.chess.com/game/live/166077521478): finished the March 17 win against `newbie060806` in the 80% accuracy game Chess.com estimated at 1150 Elo.
- [**21...Qd2#** (Chess.com game)](https://www.chess.com/game/live/166156046882): immediate mate after `21. Qf4` in the March 19 win against `sozplayschess05`.
- [**34...Qb4#** (Lichess)](https://lichess.org/i19C7n9W#68): 34-move mate against `rrr3009` after the early rook grab on `4. Qxh8`.
- [**45. Qb8#** (Chess.com game)](https://www.chess.com/game/live/166542891282?move=0): immediate mate against `jinkry6` after `44...Kb6`.
- [**53. Ra7#** (Chess.com game)](https://www.chess.com/game/live/166559236480): passed-pawn conversion against `Ethagain`, with `52. b8=Q` setting up the final rook mate.

## High Win% Comeback Evidence
Current `analysis/*.md` artifacts include a high-confidence conversion sequence in `analysis/2026-03-03-comeback-vs-gaju33333.md` (SoloPistol POV).

- From the move table:
  - `28...Qxd8`: W/L/D `45.1/0.0/54.9` -> expected score `0.73`.
  - `34...Qxc7`: W/L/D `100.0/0.0/0.0` -> expected score `1.00`.
- Before/after snapshot: `0.73 -> 1.00` (final expected score `>= 0.80`).

### Why This Matters
- Shows a clear conversion path from already-strong winning chances to a fully winning final position.
- Keeps the section evidence-backed with explicit values derived from current analysis artifacts.

### Tactical Comeback Mate
- [analysis/3.15-comeback-mate.md](analysis/3.15-comeback-mate.md) captures a different comeback arc: `15. Bf2` allowed `15...Bxa1`, but the attack rebuilt into a forced mating net that finished with `27. Qh5#`.
- The same artifact shows the position had already flipped to a forced mate by `22...Bxg5`, so the rook loss did not stop the attack from converting.

## Study/Analysis Links
- Game sources:
  - [Chess.com game: 2026-02-27](https://www.chess.com/game/live/165298129986?move=0)
  - [Chess.com analysis: 2026-02-27](https://www.chess.com/analysis/game/live/165298129986/analysis)
  - [Lichess game: 2026-03-03](https://lichess.org/nujVa4n7)
  - [Lichess game: 2026-03-06](https://lichess.org/jdooSl0M)
  - [Chess.com game: 2026-03-11](https://www.chess.com/game/live/165814123450)
  - [Lichess game: 2026-03-11](https://lichess.org/lY26zNo7)
  - [Chess.com game: 2026-03-13](https://www.chess.com/game/live/165901228132)
  - [Chess.com analysis: 2026-03-13](https://www.chess.com/analysis/game/live/165901228132/analysis?move=23)
  - [Chess.com analysis: 2026-03-15 domination](https://www.chess.com/analysis/game/live/165996433052/analysis)
  - [Chess.com review: 2026-03-15](https://www.chess.com/analysis/game/live/165995086288/review?move=29&move=29&tab=review&classification=greatfind&autorun=true)
  - [Chess.com game: 2026-03-17](https://www.chess.com/game/live/166077521478)
  - [Chess.com game: 2026-03-19](https://www.chess.com/game/live/166156046882)
  - [Lichess game: 2026-03-22](https://lichess.org/i19C7n9W)
  - [Chess.com game: 2026-03-28 vs jinkry6](https://www.chess.com/game/live/166542891282?move=0)
  - [Chess.com game: 2026-03-28 vs Ethagain](https://www.chess.com/game/live/166559236480)
  - [Lichess study chapter: 2026-03-03](https://lichess.org/study/9tKdUwCn/7y3AQeFe)
- Local artifacts:
  - [analysis/2026-02-27-fast-checkmate.md](analysis/2026-02-27-fast-checkmate.md)
  - [analysis/3.15-domination.md](analysis/3.15-domination.md)
  - [analysis/3.15-comeback-mate.md](analysis/3.15-comeback-mate.md)
  - [analysis/2026-03-03-comeback-vs-gaju33333.md](analysis/2026-03-03-comeback-vs-gaju33333.md)
  - [analysis/3.6-tough.md](analysis/3.6-tough.md)
  - [analysis/3.11-back-rank-mate.md](analysis/3.11-back-rank-mate.md)
  - [analysis/3.11-tense-endgame.md](analysis/3.11-tense-endgame.md)
  - [analysis/14-move-checkmate-SoloPistol_vs_Abhijeetnegi123_2026.03.13.md](analysis/14-move-checkmate-SoloPistol_vs_Abhijeetnegi123_2026.03.13.md)
  - [analysis/3.17-80-accuracy.md](analysis/3.17-80-accuracy.md)
  - [analysis/3.19-mate.md](analysis/3.19-mate.md)
  - [analysis/3.22-rook-loss-mate.md](analysis/3.22-rook-loss-mate.md)
  - [analysis/3.28-1000-vs-950-elo-plays.md](analysis/3.28-1000-vs-950-elo-plays.md)
  - [analysis/3.28-passed-pawn.md](analysis/3.28-passed-pawn.md)
  - [games/all/chess_com_games_2026-03-15_combined.pgn](games/all/chess_com_games_2026-03-15_combined.pgn)
  - [games/all/chess_com_games_2026-03-15_combined_elo_history.csv](games/all/chess_com_games_2026-03-15_combined_elo_history.csv)

## How to View the Games
- Open PGNs from `games/**/*.pgn` in Chess.com, Lichess, or any local PGN viewer.
- The March 15 raw Chess.com export bundle is also available as one 119-game PGN at `games/all/chess_com_games_2026-03-15_combined.pgn`.
- For spreadsheeting and ELO-over-time charts in OpenOffice Calc or LibreOffice Calc, import `games/all/chess_com_games_2026-03-15_combined_elo_history.csv` or regenerate it with `python3 scripts/export_elo_history_csv.py games/all/chess_com_games_2026-03-15_combined.pgn`.
- Run `bash scripts/analyze_game.sh <game-name-or-path>` to regenerate matching markdown under `analysis/`.
- Direct `python3 analyze_pgn.py games/<name>.pgn` runs also mirror the PGN stem under `analysis/` unless `--output-md` is set.
- If your shell prints `command not found` for a flag (for example `--ollama-max-tokens`), the previous line likely missed a continuation character.

Visual highlight:

![Lichess comeback highlight](media/2026-03-03-lichess-comeback.gif)

## Next goals
- Fix shell command UX around `--ollama-max-tokens` with shell-safe docs/examples (single-line first, multiline with explicit continuation).
- Refactor `scripts/analyze_game.sh` path resolution and command assembly without behavior regressions for name lookup, absolute paths, and scratch-game routing.
- Add `gemini` as an opt-in `forensic-llm` backend while preserving deterministic fallback when credentials/runtime are unavailable.
