# SoloPistol vs Ironmike3982 (SoloPistol POV)

- White: `SoloPistol`
- Black: `Ironmike3982`
- POV: `SoloPistol` (White)
- Turn labels: `me` = `SoloPistol`, `opp` = `Ironmike3982`

## How The Game Was Won

- Result: `SoloPistol` beat `Ironmike3982` by checkmate on `27. Qh5#`.
- Final sequence: `26... Kh7` allowed `27. Qh5#` immediately.
- Finish detail: the queen on `h5` delivered mate, and Black's king on `h7` had no legal escape.

## Significant Swings

- Config: threshold=20.0 pts, scope=pov, max-events=8, cause-mode=forensic, severity=Critical only

- [Critical] 9. b3 (me): W/L/D 83.9/0.0/16.1 -> 0.0/16.2/83.8, eval 1.25 -> -0.65, expected score 0.92 -> 0.42 (-50.0 pts)
  Impact: me=negative (-50.0 pts), opp=positive (+50.0 pts)
  Best: f4 (Stockfish+Lc0) | Played: b3 | Opportunity cost: 2.36 pawns worse
  Engines: Stockfish=1.72 pawns worse, Lc0=2.99 pawns worse, confidence=Medium
  Evidence: SF PV f4 Qxb2 Nb5 Bb8 Rb1 Qxa2 | Lc0 PV f4
  Cause: 9. b3 was inferior to f4; it weakened coordination and handed over initiative. Evidence: expected score 0.92 -> 0.42 (-50.0 pts), Stockfish 1.72 pawns worse, Lc0 2.99 pawns worse.
  What you likely thought: The move looked playable, but a deeper safety/coordination check would have flagged the downside.
  What you missed on the board: You likely missed piece coordination and loose-piece tension after the move. After your move, the opponent also had 3 capture(s), increasing tactical volatility.
  How to decide better next time: 1) Check king safety. 2) Check loose pieces. 3) Prefer moves that improve both activity and stability.
  Practice habit: Use a fixed three-step blunder check before committing.
  Lesson: Solid coordination beats speculative activity.


- [Critical] 15. Bf2 (me): W/L/D 99.0/0.0/1.0 -> 0.0/100.0/0.0, eval 1.80 -> -5.73, expected score 0.99 -> 0.00 (-99.5 pts)
  Impact: me=negative (-99.5 pts), opp=positive (+99.5 pts)
  Best: Bxd4 (Stockfish+Lc0) | Played: Bf2 | Opportunity cost: 18.16 pawns worse
  Engines: Stockfish=7.59 pawns worse, Lc0=28.72 pawns worse, confidence=Medium
  Evidence: SF PV Bxd4 cxd4 O-O-O Re8 Qxd4 Re4 | Lc0 PV Bxd4
  Cause: 15. Bf2 was inferior to Bxd4; it missed a tactical resource and allowed avoidable material damage. Evidence: expected score 0.99 -> 0.00 (-99.5 pts), Stockfish 7.59 pawns worse, Lc0 28.72 pawns worse.
  What you likely thought: Humans often lock onto one plan and fail to refresh candidate moves after the position changes. That causes tactical resources to be overlooked.
  What you missed on the board: The missed cue was tactical forcing order: checks and captures changed the material outcome quickly. After your move, the opponent had 2 checking idea(s), which is a forcing-warning signal. After your move, the opponent also had 3 capture(s), increasing tactical volatility.
  How to decide better next time: 1) Rebuild candidate moves from scratch. 2) Prioritize forcing moves before quiet plans. 3) Compare resulting material after each forcing branch.
  Practice habit: When the position is tactical, restart candidate generation every move.
  Lesson: In tactical positions, forcing move order decides material outcomes.

```text
Ply   Turn Move    Win% Loss% Draw%    Eval
-------------------------------------------
1.    me  e4       4.3   0.1  95.6    0.33
1...  opp e5       4.5   0.1  95.4    0.35
2.    me  Nf3      2.2   0.2  97.6    0.21
2...  opp Nf6      7.4   0.1  92.5    0.46
3.    me  d4       2.7   0.2  97.1    0.26
3...  opp Nc6     66.8   0.0  33.2    1.07
4.    me  Nc3      1.1   0.4  98.5    0.08
4...  opp Bd6     60.3   0.0  39.7    1.02
5.    me  Be3      9.4   0.0  90.6    0.52
5...  opp exd4     9.3   0.0  90.7    0.52
6.    me  Nxd4     9.0   0.0  91.0    0.51
6...  opp Nxd4    30.1   0.0  69.9    0.79
7.    me  Bxd4    25.4   0.0  74.6    0.75
7...  opp c5     100.0   0.0   0.0    2.53
8.    me  Be3     31.0   0.0  69.0    0.80
8...  opp Qb6     83.9   0.0  16.1    1.25
9.    me  b3       0.0  16.2  83.8   -0.65
9...  opp Be5      0.0   9.7  90.3   -0.54
10.   me  Qd2      0.0 100.0   0.0   -3.41
10... opp O-O      0.0  36.1  63.9   -0.85
11.   me  Bc4      0.0 100.0   0.0   -3.82
11... opp d6       0.0  26.6  73.4   -0.77
12.   me  Nd5      0.0 100.0   0.0   -5.46
12... opp Nxd5     0.0 100.0   0.0   -5.36
13.   me  exd5     0.0 100.0   0.0   -5.65
13... opp f5       0.0 100.0   0.0   -2.76
14.   me  f4       0.0 100.0   0.0   -5.91
14... opp Bd4     99.0   0.0   1.0    1.80
15.   me  Bf2      0.0 100.0   0.0   -5.73
15... opp Bxa1     0.0 100.0   0.0   -5.50
16.   me  O-O      0.0 100.0   0.0   -5.67
16... opp Bf6      0.0 100.0   0.0   -5.63
17.   me  Re1      0.0 100.0   0.0   -5.71
17... opp Bd7      0.0 100.0   0.0   -5.50
18.   me  Re3      0.0 100.0   0.0   -5.74
18... opp h5       0.0 100.0   0.0   -5.38
19.   me  h3       0.0 100.0   0.0   -5.46
19... opp a5       0.0 100.0   0.0   -4.75
20.   me  Rg3      0.0 100.0   0.0   -5.69
20... opp Rad8     0.0 100.0   0.0   -5.11
21.   me  Re3      0.0 100.0   0.0   -5.24
21... opp g5       0.0 100.0   0.0   -3.95
22.   me  fxg5     0.0 100.0   0.0   -4.42
22... opp Bxg5   100.0   0.0   0.0    M+11
23.   me  Rg3    100.0   0.0   0.0    M+10
23... opp Qb4    100.0   0.0   0.0     M+4
24.   me  Qe2    100.0   0.0   0.0    5.92
24... opp Rde8   100.0   0.0   0.0    6.79
25.   me  Qxh5   100.0   0.0   0.0    6.74
25... opp b6     100.0   0.0   0.0     M+1
26.   me  Qxg5+  100.0   0.0   0.0     M+1
26... opp Kh7    100.0   0.0   0.0     M+1
27.   me  Qh5#   100.0   0.0   0.0     M+0
```
