#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import chess.pgn


TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2}) GMT(?P<offset>[+-]\d{4})$"
)
FIELDNAMES = [
    "game_index",
    "source_index",
    "played_at_utc",
    "game_date",
    "game_time_utc",
    "timezone_offset",
    "has_end_time",
    "player",
    "player_color",
    "player_elo",
    "elo_change",
    "opponent",
    "opponent_elo",
    "opponent_is_bot",
    "site",
    "event",
    "time_control",
    "result",
    "player_result",
    "player_score",
    "termination",
]


@dataclass
class ExportRow:
    row: dict[str, str]
    sort_key: tuple[int, datetime, int]
    player_elo_value: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export a combined PGN file to a CSV table for OpenOffice/LibreOffice "
            "rating-over-time graphs."
        )
    )
    parser.add_argument("pgn_path", help="Path to the combined PGN file")
    parser.add_argument(
        "--player",
        help=(
            "Player name to graph. If omitted, the script auto-detects the most "
            "frequent player name in the PGN."
        ),
    )
    parser.add_argument(
        "--output-csv",
        help=(
            "Output CSV path. Defaults to <pgn-stem>_elo_history.csv next to the PGN. "
            "Use '-' to write CSV to stdout."
        ),
    )
    parser.add_argument(
        "--exclude-bots",
        action="store_true",
        help="Exclude games where the opponent or event indicates a bot game.",
    )
    return parser.parse_args()


def load_games(pgn_path: Path) -> list[dict[str, str]]:
    games: list[dict[str, str]] = []
    with pgn_path.open(encoding="utf-8", errors="replace") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            games.append(dict(game.headers))
    return games


def infer_player_name(games: list[dict[str, str]]) -> str:
    counts: Counter[str] = Counter()
    for headers in games:
        for side in ("White", "Black"):
            name = headers.get(side, "").strip()
            if name and name != "?":
                counts[name] += 1

    if not counts:
        raise SystemExit("Could not infer player name because the PGN has no named players.")

    top_count = counts.most_common(1)[0][1]
    candidates = sorted(name for name, count in counts.items() if count == top_count)
    if len(candidates) != 1:
        joined = ", ".join(candidates)
        raise SystemExit(
            f"Could not infer a single player name automatically. Pass --player. Candidates: {joined}"
        )
    return candidates[0]


def normalize_date(raw_date: str) -> tuple[str, datetime | None]:
    value = (raw_date or "").strip()
    if not value or "?" in value:
        return "", None
    try:
        parsed = datetime.strptime(value, "%Y.%m.%d")
    except ValueError:
        return value.replace(".", "-"), None
    return parsed.strftime("%Y-%m-%d"), parsed


def normalize_end_time(raw_time: str) -> tuple[str, str, bool]:
    value = (raw_time or "").strip()
    if not value:
        return "00:00:00", "", False
    match = TIME_RE.match(value)
    if not match:
        return value, "", False
    clock = (
        f"{int(match.group('hour')):02d}:{match.group('minute')}:{match.group('second')}"
    )
    return clock, match.group("offset"), True


def player_score_for_result(result: str, player_color: str) -> tuple[str, str]:
    if result == "1-0":
        if player_color == "White":
            return "win", "1.0"
        return "loss", "0.0"
    if result == "0-1":
        if player_color == "Black":
            return "win", "1.0"
        return "loss", "0.0"
    if result == "1/2-1/2":
        return "draw", "0.5"
    return "unknown", ""


def parse_elo(raw_elo: str) -> int | None:
    value = (raw_elo or "").strip()
    if not value.isdigit():
        return None
    return int(value)


def is_bot_game(headers: dict[str, str], opponent: str) -> bool:
    event = headers.get("Event", "")
    return "bot" in event.lower() or opponent.upper().endswith("-BOT")


def build_export_rows(games: list[dict[str, str]], player_name: str) -> list[ExportRow]:
    rows: list[ExportRow] = []

    for source_index, headers in enumerate(games, start=1):
        white = headers.get("White", "").strip()
        black = headers.get("Black", "").strip()
        if player_name == white:
            player_color = "White"
            opponent = black
            player_elo_raw = headers.get("WhiteElo", "")
            opponent_elo_raw = headers.get("BlackElo", "")
        elif player_name == black:
            player_color = "Black"
            opponent = white
            player_elo_raw = headers.get("BlackElo", "")
            opponent_elo_raw = headers.get("WhiteElo", "")
        else:
            continue

        game_date, parsed_date = normalize_date(headers.get("EndDate") or headers.get("Date", ""))
        game_time, timezone_offset, has_end_time = normalize_end_time(headers.get("EndTime", ""))
        if parsed_date is not None:
            parsed_timestamp = datetime.strptime(f"{game_date} {game_time}", "%Y-%m-%d %H:%M:%S")
            sort_key = (0, parsed_timestamp, source_index)
        else:
            parsed_timestamp = datetime.max
            sort_key = (1, parsed_timestamp, source_index)

        player_result, player_score = player_score_for_result(headers.get("Result", ""), player_color)
        player_elo_value = parse_elo(player_elo_raw)

        row = {
            "game_index": "",
            "source_index": str(source_index),
            "played_at_utc": f"{game_date} {game_time}".strip(),
            "game_date": game_date,
            "game_time_utc": game_time,
            "timezone_offset": timezone_offset,
            "has_end_time": "true" if has_end_time else "false",
            "player": player_name,
            "player_color": player_color,
            "player_elo": player_elo_raw.strip(),
            "elo_change": "",
            "opponent": opponent,
            "opponent_elo": opponent_elo_raw.strip(),
            "opponent_is_bot": "true" if is_bot_game(headers, opponent) else "false",
            "site": headers.get("Site", "").strip(),
            "event": headers.get("Event", "").strip(),
            "time_control": headers.get("TimeControl", "").strip(),
            "result": headers.get("Result", "").strip(),
            "player_result": player_result,
            "player_score": player_score,
            "termination": headers.get("Termination", "").strip(),
        }
        rows.append(ExportRow(row=row, sort_key=sort_key, player_elo_value=player_elo_value))

    return rows


def apply_running_fields(rows: list[ExportRow]) -> list[dict[str, str]]:
    export_rows = sorted(rows, key=lambda item: item.sort_key)
    previous_elo: int | None = None

    for game_index, export_row in enumerate(export_rows, start=1):
        export_row.row["game_index"] = str(game_index)
        if previous_elo is not None and export_row.player_elo_value is not None:
            export_row.row["elo_change"] = str(export_row.player_elo_value - previous_elo)
        else:
            export_row.row["elo_change"] = ""

        if export_row.player_elo_value is not None:
            previous_elo = export_row.player_elo_value

    return [item.row for item in export_rows]


def output_path_for(pgn_path: Path, output_csv: str | None) -> str:
    if output_csv:
        return output_csv
    return str(pgn_path.with_name(f"{pgn_path.stem}_elo_history.csv"))


def write_csv(rows: list[dict[str, str]], output_csv: str) -> None:
    if output_csv == "-":
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
        return

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    pgn_path = Path(args.pgn_path).expanduser().resolve()
    if not pgn_path.is_file():
        raise SystemExit(f"PGN file not found: {pgn_path}")

    games = load_games(pgn_path)
    if not games:
        raise SystemExit("No games found in PGN.")

    player_name = args.player or infer_player_name(games)
    rows = build_export_rows(games, player_name)
    if not rows:
        raise SystemExit(f"No games found for player '{player_name}'.")

    if args.exclude_bots:
        rows = [row for row in rows if row.row["opponent_is_bot"] != "true"]
        if not rows:
            raise SystemExit("No rows remain after applying --exclude-bots.")

    rendered_rows = apply_running_fields(rows)
    output_csv = output_path_for(pgn_path, args.output_csv)
    write_csv(rendered_rows, output_csv)

    if output_csv == "-":
        print(
            f"Detected player: {player_name}. Exported {len(rendered_rows)} rows to stdout.",
            file=sys.stderr,
        )
    else:
        print(f"Detected player: {player_name}")
        print(f"Exported {len(rendered_rows)} rows to {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
