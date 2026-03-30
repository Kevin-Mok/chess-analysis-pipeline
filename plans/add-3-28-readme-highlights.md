# ExecPlan: Add 2026-03-28 README Highlights

## Goal
Add README coverage for the March 28 game artifacts so the PGN and analysis files can be committed without failing the repo's README sync gate.

## Assumptions
1. The March 28 artifacts should be grouped together as one README-triggered update.
2. The strongest supported highlight angles are the terminal mates `45. Qb8#` vs `jinkry6` and `53. Ra7#` vs `Ethagain`.
3. Existing `## Next goals` bullets already match `docs/TODO.md`, so this task only needs highlight/link updates.

## Plan
- [x] Verify the March 28 PGN and analysis facts for both games.
- [x] Add concise March 28 entries to the README highlight sections.
- [x] Add the new analysis artifacts to the README local-artifacts list.
- [x] Verify the README wording remains evidence-backed and chronologically placed.

## Review
- Added March 28 bullets under `## Chess Improvement View` for the `jinkry6` and `Ethagain` wins.
- Added two `## Highlight Games` rows, two `## Key Moves and Turning Points` bullets, and two `## Study/Analysis Links` entries using the tracked Chess.com game URLs from the PGNs.
- Added the March 28 analysis markdown files to the README local-artifacts list.
- Refreshed `docs/RECRUITER_REPO_IDEAS.md` because the recruiter-ideas cadence was due for a README-triggered update.
