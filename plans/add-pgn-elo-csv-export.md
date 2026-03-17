# ExecPlan: Export PGN ELO History CSV

## Goal
Add a reusable script that converts a combined PGN export into an OpenOffice-friendly CSV table for spreadsheeting and plotting player ELO over time.

## Assumptions
1. The output should contain one row per game, with the player's rating normalized into a single column regardless of White/Black side.
2. The combined PGN may include bot games and incomplete time headers, so the export should preserve those rows while exposing enough metadata to filter them later.
3. Adding a new script requires a same-change `README.md` update under this repo's trigger rules.

## Plan
- [x] Inspect combined PGN headers and define a stable CSV schema for OpenOffice import.
- [x] Add a regression test covering chronological sorting, POV rating extraction, and missing `EndTime` fallback.
- [x] Implement the converter script and generate a CSV artifact from the current combined PGN.
- [x] Update `README.md` with converter usage and output guidance, keeping `## Next goals` aligned with `docs/TODO.md`.
- [x] Verify with targeted tests and a real script run.

## Review
- Added `scripts/export_elo_history_csv.py`, which auto-detects the player name when possible, normalizes White/Black ratings into one `player_elo` column, sorts games chronologically, and writes an OpenOffice-friendly CSV.
- Added `tests/test_export_elo_history_csv.py` to lock chronological sorting, POV field normalization, bot tagging, and single-digit-hour `EndTime` handling.
- Generated `games/all/chess_com_games_2026-03-15_combined_elo_history.csv` with 119 rows from the current combined archive.
- Updated `README.md` with the new export command, linked CSV artifact, and Calc/OpenOffice import guidance.
- Read `docs/TODO.md` during the README sync and left `## Next goals` unchanged because its current three bullets still match the highest-priority items there.
