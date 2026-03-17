from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


def test_export_elo_history_csv_sorts_and_normalizes_rows(repo_root: Path, tmp_path: Path):
    pgn_path = tmp_path / "combined.pgn"
    output_csv = tmp_path / "elo_history.csv"
    pgn_path.write_text(
        """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.02.15"]
[Round "-"]
[White "hamzo3"]
[Black "SoloPistol"]
[Result "1-0"]
[WhiteElo "332"]
[BlackElo "318"]
[TimeControl "900+10"]
[EndTime "15:34:07 GMT+0000"]
[Termination "hamzo3 won by resignation"]

1. e4 e5 2. Nf3 Nc6 1-0

[Event "Play vs Bot"]
[Site "Chess.com"]
[Date "2026.02.14"]
[Round "4"]
[White "SoloPistol"]
[Black "Filip-BOT"]
[Result "0-1"]
[WhiteElo "339"]
[BlackElo "400"]
[TimeControl "?"]
[EndDate "2026.02.14"]
[Termination "Filip-BOT won by resignation"]

1. e4 e5 2. Nf3 Nf6 0-1

[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.02.15"]
[Round "-"]
[White "SoloPistol"]
[Black "Crazydude_18"]
[Result "1-0"]
[WhiteElo "339"]
[BlackElo "374"]
[TimeControl "900+10"]
[EndTime "3:13:18 GMT+0000"]
[Termination "SoloPistol won by checkmate"]

1. e4 Nf6 2. d4 Nxe4 1-0
""",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "export_elo_history_csv.py"),
        str(pgn_path),
        "--output-csv",
        str(output_csv),
    ]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert output_csv.exists()

    with output_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["played_at_utc"] for row in rows] == [
        "2026-02-14 00:00:00",
        "2026-02-15 03:13:18",
        "2026-02-15 15:34:07",
    ]
    assert [row["player_color"] for row in rows] == ["White", "White", "Black"]
    assert [row["player_elo"] for row in rows] == ["339", "339", "318"]
    assert [row["elo_change"] for row in rows] == ["", "0", "-21"]
    assert [row["opponent_is_bot"] for row in rows] == ["true", "false", "false"]
    assert [row["player_result"] for row in rows] == ["loss", "win", "loss"]
    assert [row["has_end_time"] for row in rows] == ["false", "true", "true"]
