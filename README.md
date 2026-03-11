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
- A POV move table with W/L/D probabilities and eval deltas.
- A `## Significant Swings` block with:
  - severity,
  - expected-score before/after,
  - engine comparison (Stockfish + Lc0),
  - PV evidence,
  - concise training lesson text.
- Markdown output to `analysis/*.md` by default, or a custom path via `--output-md`.

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
Current artifacts highlight tactical conversion and practical game management under rapid time controls.

- Fast tactical finish in `2026-02-27-fast-checkmate`.
- Conversion sequence in `2026-03-03-comeback-vs-gaju33333` ending in a decisive queen trade.
- Tense, drawn-out 76-move win vs `NickGen_Eral` with 88% accuracy maintained deep into the endgame.

## Highlight Games
| Date | Opponent | Platform | Result | Game Link | Why it matters |
| --- | --- | --- | --- | --- | --- |
| 2026-02-27 | Woaheee | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/165298129986?move=0) | Fast tactical finish ending with `15. Qxe7#`. |
| 2026-03-03 | gaju33333 | Lichess | Win (Black, 0-1) | [Lichess game](https://lichess.org/nujVa4n7) | Clean conversion featuring `18...Nxb2` and `34...Qxc7`. |
| 2026-03-11 | NickGen_Eral | Lichess | Win (White, 1-0) | [Lichess game](https://lichess.org/lY26zNo7) | Long 76-move win with 88% accuracy, showing steady practical play deep into a drawn-out endgame. |

## Key Moves and Turning Points
- [**15. Qxe7#** (Chess.com analysis)](https://www.chess.com/analysis/game/live/165298129986/analysis?move=29): immediate checkmate conversion.
- [**18...Nxb2** (Lichess)](https://lichess.org/nujVa4n7#36): practical material gain in the conversion phase.
- [**34...Qxc7** (Lichess)](https://lichess.org/nujVa4n7#68): decisive queen trade that closes the game.

## High Win% Comeback Evidence
Current `analysis/*.md` artifacts include a high-confidence conversion sequence in `analysis/2026-03-03-comeback-vs-gaju33333.md` (SoloPistol POV).

- From the move table:
  - `28...Qxd8`: W/L/D `67.8/0.0/32.2` -> expected score `0.84`.
  - `34...Qxc7`: W/L/D `100.0/0.0/0.0` -> expected score `1.00`.
- Before/after snapshot: `0.84 -> 1.00` (final expected score `>= 0.80`).

### Why This Matters
- Shows a clear conversion path from already-strong winning chances to a fully winning final position.
- Keeps the section evidence-backed with explicit values derived from current analysis artifacts.

## Study/Analysis Links
- Game sources:
  - [Chess.com game: 2026-02-27](https://www.chess.com/game/live/165298129986?move=0)
  - [Chess.com analysis: 2026-02-27](https://www.chess.com/analysis/game/live/165298129986/analysis)
  - [Lichess game: 2026-03-03](https://lichess.org/nujVa4n7)
  - [Lichess game: 2026-03-06](https://lichess.org/jdooSl0M)
  - [Lichess study chapter: 2026-03-03](https://lichess.org/study/9tKdUwCn/7y3AQeFe)
- Local artifacts:
  - [analysis/2026-02-27-fast-checkmate.md](analysis/2026-02-27-fast-checkmate.md)
  - [analysis/2026-03-03-comeback-vs-gaju33333.md](analysis/2026-03-03-comeback-vs-gaju33333.md)
  - [analysis/3.6-tough.md](analysis/3.6-tough.md)

## How to View the Games
- Open PGNs from `games/*.pgn` in Chess.com, Lichess, or any local PGN viewer.
- Run `bash scripts/analyze_game.sh <game-name-or-path>` to regenerate matching markdown under `analysis/`.
- If your shell prints `command not found` for a flag (for example `--ollama-max-tokens`), the previous line likely missed a continuation character.

Visual highlight:

![Lichess comeback highlight](media/2026-03-03-lichess-comeback.gif)

## Next goals
- Fix shell command UX around `--ollama-max-tokens` with shell-safe docs/examples (single-line first, multiline with explicit continuation).
- Refactor `scripts/analyze_game.sh` path resolution and command assembly without behavior regressions for name lookup, absolute paths, and scratch-game routing.
- Add `gemini` as an opt-in `forensic-llm` backend while preserving deterministic fallback when credentials/runtime are unavailable.
