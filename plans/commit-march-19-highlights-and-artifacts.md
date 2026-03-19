# ExecPlan: Commit March 19 Highlights And Dirty Artifacts

## Goal
Commit the current dirty worktree as a small set of coherent commits, then push them to `origin main`.

## Assumptions
1. The current branch `main` is the intended target branch.
2. The March 19 README update, PGN, and analysis artifact should land together as one highlight-focused commit.
3. The March 19 GIF, site prompt draft, and March 15 evidence artifacts should stay in separate commits so each group remains reviewable.
4. The draft prompt should be cleaned enough to remove obvious paste corruption before it is committed.

## Plan
- [x] Recheck the dirty worktree and inspect every changed or untracked file.
- [x] Confirm sensible commit boundaries for the README/game update, GIF, docs draft, and evidence artifacts.
- [x] Clean the malformed prompt draft enough to remove obvious citation debris and align its input path with the repo.
- [x] Stage and verify the March 19 highlight commit:
  - `README.md`
  - `analysis/3.19-mate.md`
  - `games/3.19-21-move-mate.pgn`
- [x] Stage and verify the March 19 replay GIF commit:
  - `media/3.19-21-move-mate.gif`
- [x] Stage and verify the site-prompt docs commit:
  - `docs/site-prompt.md`
- [x] Stage and verify the March 15 evidence artifact commit, along with this ExecPlan:
  - `games/all/chess_com_games_2026-03-15_combined_elo_history.ods`
  - `media/3.15-1150-rating.png`
  - `media/3.15-88-accuracy.png`
  - `plans/commit-march-19-highlights-and-artifacts.md`
- [ ] Push each successful commit to `origin main`, per repo policy.

## Review
- Completed so far:
  - `423c048` `feat: add March 19 mate highlight`
  - `2c69737` `chore: add March 19 mate replay GIF`
  - `caf3ec4` `docs: add chess analytics site prompt`
- Each completed commit was verified with `git diff --cached --check` before commit.
- The prompt draft was cleaned before commit to remove paste debris and fix the repo-local PGN path.
- The final staged commit contains the March 15 ODS export, two screenshot artifacts, and this ExecPlan.
- Remaining work at the time of this plan snapshot is pushing the final artifact commit.
