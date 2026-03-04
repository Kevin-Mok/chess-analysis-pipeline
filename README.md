# Chess Highlights

## Overview
This repo tracks my best rapid games and an automated local analysis pipeline that turns PGNs into evidence-backed coaching and swing reports.

### Why I Built This
I built this to replace a proprietary Chess.com learning workflow with something I fully control and can extend.

- Platform shift:
  - I moved active study and game review toward Lichess because it aligns better with FOSS values and transparent tooling.
- Tooling ownership:
  - Instead of relying on closed premium features, I built a local pipeline around engines + scripts + markdown artifacts so I can inspect every step.
- Cost model:
  - I use local LLMs and local engine analysis to avoid recurring premium subscription costs while still getting high-quality feedback.
- Engineering upside:
  - The same setup doubles as a practical software project: reproducible CLI workflows, configurable analysis depth, and evidence-backed output.

## SWE Recruiter View
AI-first engineering focus: this project is a local multi-engine + LLM analysis system, not just a PGN notes repo.

- Designed and integrated a local AI tooling chain (`stockfish` + `lc0` + `llama-cli`) to produce explainable chess analysis artifacts.
- Built a reproducible CLI workflow that parses PGNs and outputs POV-oriented move tables (`Win%`, `Loss%`, `Draw%`, eval) via `analyze_pgn.py`.
- Added significant swing detection based on expected-score deltas, with configurable threshold (`--swing-threshold-score`), scope (`--swing-scope`), and cap (`--swing-max-events`).
- Implemented forensic mode that cross-checks swing causes with Stockfish + Lc0 and prints PV evidence plus opportunity-cost estimates.
- Added optional `forensic-llm` layer that rewrites forensic findings with local `llama-cli` while preserving deterministic fallback if LLM tooling is unavailable.
- Current analysis artifacts:
  - [2026-03-03-comeback-vs-gaju33333 analysis](analysis/2026-03-03-comeback-vs-gaju33333.md)
  - [2026-02-27-fast-checkmate analysis](analysis/2026-02-27-fast-checkmate.md)

### Engineering Signals
- End-to-end automation:
  - PGN input -> engine passes -> markdown report with consistent schema.
- Deterministic baseline plus optional AI augmentation:
  - `heuristic` and `forensic` modes are deterministic.
  - `forensic-llm` is additive and optional, not a hard dependency.
- Tooling depth:
  - Integrates multiple local binaries (Stockfish, Lc0, llama-cli) with path auto-detection and explicit override flags.
- Failure handling:
  - Forensic failures are surfaced in output and gracefully fall back to heuristic cause text.

### What The Main Script Produces
- Move-by-move WDL/eval table from POV (`SoloPistol` by default, override with `--pov-player`).
- `## Significant Swings` section with:
  - event severity,
  - expected-score before/after,
  - engine disagreement/cost evidence,
  - concise coaching lesson.
- Markdown output path control with `--output-md`, including stdout mode (`--output-md -`).

## AI Tooling Stack
This project is intentionally local-first: engine and LLM tooling run on-device without remote API dependencies.

### Tool Roles
- `stockfish`:
  - Primary evaluator for move-by-move WDL/eval output.
  - Baseline engine in both standard and forensic flows.
- `lc0` + network weights (`.pb.gz`):
  - Secondary engine for forensic cross-checking.
  - Used to confirm or challenge Stockfish-based swing-cause conclusions.
- `llama-cli` + local GGUF model:
  - Optional post-processing layer in `--cause-mode forensic-llm`.
  - Rewrites forensic cause/lesson text while preserving factual constraints.

### AI/Engine Execution Modes
- `heuristic`:
  - Fast labels only, no forensic cross-engine validation.
- `forensic` (default):
  - Deterministic Stockfish + Lc0 evidence path.
  - Produces best-move deltas, PV evidence, confidence labels, and coaching lessons.
- `forensic-llm`:
  - Same forensic evidence plus optional local LLM rewriting.
  - Falls back to deterministic forensic text if LLM binary/model are missing.

### Why This Tooling Matters
- Reproducibility:
  - Same local binaries + same PGN inputs produce stable markdown artifacts.
- Cost/control:
  - No per-call remote inference/API fees required for baseline or forensic analysis.
- Explainability:
  - Forensic output includes explicit PV evidence and opportunity-cost estimates, not just black-box labels.
- Practical resilience:
  - Missing optional AI components degrade gracefully instead of breaking the full pipeline.

## Local Analysis Pipeline
```bash
# analyze a PGN directly (default cause mode: forensic)
python3 analyze_pgn.py games/2026-03-03-comeback-vs-gaju33333.pgn

# analyze by game name/path and write analysis/<game>.md
bash scripts/analyze_game.sh 2026-03-03-comeback-vs-gaju33333

# fast deterministic labels only
python3 analyze_pgn.py games/2026-03-03-comeback-vs-gaju33333.pgn \
  --cause-mode heuristic

# deterministic forensic evidence (Stockfish + Lc0)
python3 analyze_pgn.py games/2026-03-03-comeback-vs-gaju33333.pgn \
  --cause-mode forensic

# forensic + local llm rewrite (optional local model)
python3 analyze_pgn.py games/2026-03-03-comeback-vs-gaju33333.pgn \
  --cause-mode forensic-llm \
  --llama-model ~/models/gemma-3-1b-it-Q4_K_M.gguf
```

### Key CLI Controls
- Core:
  - `--pov-player`, `--output-md`, `--max-seconds`, `--threads`, `--hash-mb`
- Swing extraction:
  - `--swing-threshold-score` (default `0.15`)
  - `--swing-max-events` (default `8`)
  - `--swing-scope both|pov|opponent` (default `both`)
- Forensic evidence:
  - `--cause-mode heuristic|forensic|forensic-llm` (default `forensic`)
  - `--lc0-path`, `--lc0-weights`
  - `--forensic-time-ms`, `--forensic-multipv`, `--forensic-max-pv-plies`
- Optional local LLM rewrite:
  - `--llama-cli-path`, `--llama-model`
  - `--llama-timeout-ms`, `--llama-max-tokens`, `--llama-temperature`

### Local Setup
- One-command local stack bootstrap:
  - `bash scripts/install_local_ai_stack.sh`
- Detailed setup and troubleshooting:
  - [docs/LOCAL_AI_SETUP.md](docs/LOCAL_AI_SETUP.md)

## Chess Improvement View
Two wins with different improvement signals: fast tactical conversion and a high-variance comeback with engine-verified turning points.

## Highlight Games
| Date | Opponent | Platform | Result | Game Link | Why it matters |
| --- | --- | --- | --- | --- | --- |
| 2026-02-27 | Woaheee | Chess.com | Win (White, 1-0) | [Chess.com game](https://www.chess.com/game/live/165298129986?move=0) | Clean tactical finish with a direct king attack and forced mate. |
| 2026-03-03 | gaju33333 | Lichess | Win (Black, 0-1) | [Lichess game](https://lichess.org/nujVa4n7) | Comeback win against 1101 after early pressure and material swings. |

## Key Moves and Turning Points
- [**15. Qxe7#** (Chess.com analyzer)](https://www.chess.com/analysis/game/live/165298129986/analysis?move=29): immediate checkmate after queen infiltration.
- [**18...Nxb2** (Lichess)](https://lichess.org/nujVa4n7#36): wins queenside material and flips initiative.
- [**26...Qxe2** (Lichess)](https://lichess.org/nujVa4n7#52): tactical conversion of central pressure into a clear advantage.
- [**34...Qxc7** (Lichess)](https://lichess.org/nujVa4n7#68): forces queen simplification and leads directly to resignation.

## High Win% Comeback Evidence
- From [analysis/2026-03-03-comeback-vs-gaju33333.md](analysis/2026-03-03-comeback-vs-gaju33333.md):
  - `34. Qxc7 (op.)`: expected score `0.00 -> 1.00` (`+100.0` pts), eval `-5.28 -> 5.28`.
  - This meets the high-probability comeback condition (final expected score `1.00 >= 0.80`).
- Same game also shows volatility before conversion:
  - `29... Qb8 (me)`: expected score `0.72 -> 0.00` (`-72.5` pts), then later recovered to a winning state.

### Why This Matters
- The comeback was not a smooth conversion; the report captures both collapse risk and recovery evidence.
- Swing-level evidence makes this useful for both chess training and engineering storytelling:
  - clear metric definitions,
  - concrete turning points,
  - reproducible artifact trail.

## Study/Analysis Links
- [Chess.com game](https://www.chess.com/game/live/165298129986?move=0)
- [Chess.com analysis](https://www.chess.com/analysis/game/live/165298129986/analysis)
- [Lichess game](https://lichess.org/nujVa4n7)
- [Lichess study chapter](https://lichess.org/study/9tKdUwCn/7y3AQeFe)

## How to View the Games
Open either PGN from `games/2026-02-27-fast-checkmate.pgn` or `games/2026-03-03-comeback-vs-gaju33333.pgn` in Chess.com or Lichess analysis boards, or import into any PGN viewer.

Visual highlight:

![Lichess comeback highlight](media/2026-03-03-lichess-comeback.gif)

## Next goals
- Reduce early opening inaccuracies in Sicilian structures.
- Convert winning positions with fewer time-pressure blunders.
- Add one annotated highlight game each week.
