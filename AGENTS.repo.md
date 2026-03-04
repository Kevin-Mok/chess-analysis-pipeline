# AGENTS.repo.md

Repository-specific strict additions for `/home/kevin/Documents/chess`.

These rules extend `AGENTS.md` and do not relax any baseline requirement.

## README Sync Trigger (Required)

Update `README.md` in the same change whenever any of the following happens:

1. A game or analysis artifact is added, removed, renamed, or materially changed.
2. Analysis script behavior, defaults, CLI flags, or output format changes.
3. Local setup/runtime requirements for analysis change.

Treat these as trigger paths:

- `games/**/*.pgn`
- `analysis/**/*.md`
- `analyze_pgn.py`
- `scripts/**/*.sh`
- `docs/LOCAL_AI_SETUP.md`

If a trigger path changes, README updates are mandatory in that same change set.

## README Source Of Truth

All README claims must come from repository artifacts only:

- `games/*.pgn`
- `analysis/*.md`
- `analyze_pgn.py`
- `scripts/analyze_game.sh`
- `docs/LOCAL_AI_SETUP.md`
- `media/*`
- Existing public game/study links already tracked in this repo

Never invent games, moves, links, percentages, or outcomes.

## README Output Contract (Required)

`README.md` must be recruiter-readable and evidence-backed. Use this structure:

1. `# Chess Highlights`
2. `## Overview`
3. `## SWE Recruiter View`
4. `## AI Tooling Stack`
5. `## Local Analysis Pipeline`
6. `## Chess Improvement View`
7. `## Highlight Games`
8. `## Key Moves and Turning Points`
9. `## High Win% Comeback Evidence`
10. `## Study/Analysis Links`
11. `## How to View the Games`
12. Optional visual highlight image
13. `## Next goals` (max 3 bullets)

README length policy:

- Do not optimize for shortness.
- Include enough detail to explain tooling behavior, reproducibility, and evidence-backed outcomes.
- Prefer completeness over brevity when analysis pipeline or results are non-trivial.

## Recruiter View Requirements

`## SWE Recruiter View` must explicitly explain what the code does:

1. PGN parsing + POV-oriented move-by-move engine table (`Win%`, `Loss%`, `Draw%`, eval).
2. Expected-score swing detection with configurable threshold/scope/max-events.
3. Forensic mode behavior (`Stockfish` + `Lc0` best-move comparison and PV evidence).
4. Optional local LLM rewrite path for forensic explanations (`forensic-llm` + `llama-cli` model).
5. Deterministic fallback behavior when optional components are missing/fail.

## AI Tooling Emphasis (Required)

README must strongly emphasize local AI/engine tooling and each tool's role.

`## AI Tooling Stack` must include:

1. Tool inventory with responsibilities:
   - `stockfish` for baseline evaluation/WDL.
   - `lc0` + weights for forensic second-opinion move quality.
   - `llama-cli` + GGUF model for optional local rewrite in `forensic-llm`.
2. Why local execution matters (reproducibility, no external API dependency, controllable latency/cost).
3. Degradation behavior:
   - Forensic requirements (`lc0` and weights) and fail-fast behavior.
   - `forensic-llm` fallback to deterministic forensic text when LLM assets are unavailable.
4. Evidence linkage to current `analysis/*.md` outputs.

## Local Pipeline Requirements

`## Local Analysis Pipeline` must include runnable commands from this repo:

- Direct analyzer usage: `python3 analyze_pgn.py <pgn-path>`
- Helper script usage: `scripts/analyze_game.sh <game-name-or-path>`
- At least one advanced mode example (`--cause-mode forensic` or `--cause-mode forensic-llm`)
- Preferred: include both advanced modes (`forensic` and `forensic-llm`) when available.

If CLI flags change in `analyze_pgn.py`, update README command examples immediately.

## Chess View Requirements

`## Chess Improvement View` + following sections must include:

1. `Highlight Games` table with: Date, Opponent, Platform, Result, Why it matters.
   - Include a direct game URL column/link to the live game page on the source site (for example Chess.com or Lichess) for each row.
2. At least 2 concrete SAN move references in `Key Moves and Turning Points`.
3. At least one evidence-backed comeback item in `High Win% Comeback Evidence`:
   - Include explicit expected-score before/after values from `analysis/*.md`.
   - Final expected score must be `>= 0.80`.
4. If no qualifying comeback exists in current analysis files, state that explicitly and do not fabricate one.

## Completion Gate

Before marking a task done, if trigger paths changed, verify:

1. `README.md` is updated in the same change.
2. README command examples match current script interfaces.
3. Numeric claims in README match current `analysis/*.md`.
4. All required sections in the output contract are present.
