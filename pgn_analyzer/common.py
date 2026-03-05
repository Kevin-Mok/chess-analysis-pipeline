from __future__ import annotations

import os
import re
import shutil
import sys

import chess

from .constants import (
    CRITICAL_SWING_THRESHOLD_SCORE,
    DEFAULT_ANALYSIS_DIR,
    DEFAULT_LC0_WEIGHTS_CANDIDATES,
    EVAL_COL_WIDTH,
    LESSON_BANNED_RE,
    MATERIAL_VALUES,
    MAX_COACHING_CHARS,
    MOVE_COL_WIDTH,
    PCT_COL_WIDTH,
    PLY_COL_WIDTH,
    TURN_COL_WIDTH,
)

def pct(x, total):
    return round(100.0 * x / total, 1) if total else 0.0


def log(message):
    print(message, file=sys.stderr, flush=True)


def format_row(ply_label, turn, san, win, loss, draw, eval_str):
    def fmt_pct(value):
        if isinstance(value, (int, float)):
            return f"{value:>{PCT_COL_WIDTH}.1f}"
        return f"{value:>{PCT_COL_WIDTH}}"

    return (
        f"{ply_label:<{PLY_COL_WIDTH}} "
        f"{turn:<{TURN_COL_WIDTH}} "
        f"{san:<{MOVE_COL_WIDTH}} "
        f"{fmt_pct(win)} "
        f"{fmt_pct(loss)} "
        f"{fmt_pct(draw)} "
        f"{eval_str:>{EVAL_COL_WIDTH}}"
    )


def format_wld(win, loss, draw):
    return f"{win:.1f}/{loss:.1f}/{draw:.1f}"

def normalize_player_name(name):
    return " ".join((name or "").split()).casefold()


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_player_name(value))
    return slug.strip("-") or "unknown"


def resolve_pov(game, pov_player):
    white = game.headers.get("White", "?")
    black = game.headers.get("Black", "?")
    if pov_player:
        target = normalize_player_name(pov_player)
        if normalize_player_name(white) == target:
            return chess.WHITE, white, black, True
        if normalize_player_name(black) == target:
            return chess.BLACK, black, white, True
    return chess.WHITE, white, black, False


def default_output_md_path(white, black, pov_name, opponent_name, pov_found):
    if pov_found:
        left = pov_name
        right = opponent_name
    else:
        left = white
        right = black
    filename = f"{slugify(left)}-vs-{slugify(right)}.md"
    return os.path.join(DEFAULT_ANALYSIS_DIR, filename)


def to_pov(board, cp, mate, wdl, pov_color):
    if cp is not None and board.turn != pov_color:
        cp = -cp
    if mate is not None and board.turn != pov_color:
        mate = -mate
    if wdl is not None and board.turn != pov_color:
        wdl = (wdl[2], wdl[1], wdl[0])
    return cp, mate, wdl


def expected_score(win_pct, draw_pct):
    return (win_pct + 0.5 * draw_pct) / 100.0


def should_track_swing(swing_scope, mover_is_pov):
    if swing_scope == "both":
        return True
    if swing_scope == "pov":
        return mover_is_pov
    return not mover_is_pov


def swing_severity(abs_delta):
    if abs_delta >= CRITICAL_SWING_THRESHOLD_SCORE:
        return "Critical"
    if abs_delta >= 0.20:
        return "Major"
    return "Notable"


def is_critical_swing(abs_delta):
    return abs_delta >= CRITICAL_SWING_THRESHOLD_SCORE


def select_swing_events(swing_events, swing_max_events):
    if swing_max_events <= 0:
        return []
    ranked = sorted(swing_events, key=lambda event: (-abs(event["delta"]), event["ply"]))
    top_events = ranked[:swing_max_events]
    return sorted(top_events, key=lambda event: event["ply"])


def swing_polarity_label(delta_points):
    if delta_points > 0:
        return "positive"
    if delta_points < 0:
        return "negative"
    return "neutral"


def captured_piece_type(board_before, move):
    if not board_before.is_capture(move):
        return None
    if board_before.is_en_passant(move):
        captured_square = move.to_square - 8 if board_before.turn == chess.WHITE else move.to_square + 8
    else:
        captured_square = move.to_square
    piece = board_before.piece_at(captured_square)
    return piece.piece_type if piece is not None else None


def infer_swing_reason(board_before, board_after, move, mate_after, delta, mover_is_pov):
    if mate_after is not None:
        if mate_after > 0:
            return "Likely cause: forced mating sequence appeared for POV."
        return "Likely cause: forced mating threat appeared against POV."

    if move.promotion:
        promoted = chess.piece_name(move.promotion)
        captured = captured_piece_type(board_before, move)
        expected_delta_sign = 1 if mover_is_pov else -1
        if delta * expected_delta_sign < 0:
            return (
                f"Likely cause: despite promoting to {promoted}, "
                "the move allowed a tactical/positional reversal."
            )
        if captured is not None:
            return (
                f"Likely cause: promotion to {promoted} with capture of a "
                f"{chess.piece_name(captured)}."
            )
        return f"Likely cause: pawn promotion to {promoted} changed the material balance."

    captured = captured_piece_type(board_before, move)
    if captured is not None:
        piece_name = chess.piece_name(captured)
        value = MATERIAL_VALUES.get(captured, 0)
        actor = "POV player" if mover_is_pov else "opponent"
        expected_delta_sign = 1 if mover_is_pov else -1
        if delta * expected_delta_sign < 0:
            return (
                f"Likely cause: despite capturing a {piece_name}, "
                f"{actor} allowed a tactical/positional reversal."
            )
        if value >= 5:
            return f"Likely cause: {actor} captured a {piece_name} (major material swing)."
        if value >= 3:
            return f"Likely cause: {actor} won a {piece_name} (piece-level material gain)."
        return f"Likely cause: {actor} won a pawn and shifted structure/initiative."

    if board_after.is_check():
        if mover_is_pov:
            return "Likely cause: checking move seized initiative and forced a reply."
        return "Likely cause: opponent checking move seized initiative."

    if board_before.is_castling(move):
        if mover_is_pov:
            return "Likely cause: castling improved king safety and rook activity."
        return "Likely cause: opponent castled and improved coordination."

    if delta > 0:
        if mover_is_pov:
            return "Likely cause: stronger piece coordination/initiative in this line."
        return "Likely cause: opponent inaccuracy created a positional swing for POV."
    if mover_is_pov:
        return "Likely cause: inaccuracy led to a positional/initiative drop."
    return "Likely cause: opponent improved coordination/initiative in the resulting position."


def orient_score_to_color(cp, mate, turn_color, target_color):
    if cp is not None and turn_color != target_color:
        cp = -cp
    if mate is not None and turn_color != target_color:
        mate = -mate
    return cp, mate


def score_to_cp(cp, mate):
    if cp is not None:
        return cp
    if mate is not None:
        return 100000 if mate > 0 else -100000
    return None


def cp_to_eval_str(cp, mate):
    if mate is not None:
        return f"M{mate:+d}"
    if cp is not None:
        return f"{cp / 100:.2f}"
    return "?"


def cp_delta_to_text(delta_cp):
    if delta_cp is None:
        return "n/a"
    if delta_cp >= 0:
        return f"{delta_cp / 100:.2f} pawns worse"
    return f"{abs(delta_cp) / 100:.2f} pawns better"


def cp_value_to_text(cp):
    if cp is None:
        return "n/a"
    return f"{cp / 100:.2f}"


def resolve_executable(explicit_path, candidates):
    if explicit_path:
        expanded = os.path.expanduser(explicit_path)
        if os.path.sep in expanded:
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                return os.path.abspath(expanded)
            return None
        return shutil.which(expanded)

    probes = list(candidates)
    for probe in probes:
        if not probe:
            continue
        expanded = os.path.expanduser(probe)
        if os.path.sep in expanded:
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                return os.path.abspath(expanded)
            continue
        found = shutil.which(expanded)
        if found:
            return found
    return None


def resolve_lc0_weights(explicit_path):
    if explicit_path:
        expanded = os.path.abspath(os.path.expanduser(explicit_path))
        return expanded if os.path.isfile(expanded) else None

    for probe in DEFAULT_LC0_WEIGHTS_CANDIDATES:
        expanded = os.path.abspath(os.path.expanduser(probe))
        if os.path.isfile(expanded):
            return expanded

    scan_dirs = [
        "/usr/local/share/lc0",
        os.path.expanduser("~/.local/share/lc0"),
        os.path.abspath("models"),
        os.path.abspath(os.path.join("models", "lc0")),
    ]
    for directory in scan_dirs:
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith(".pb.gz"):
                path = os.path.join(directory, name)
                if os.path.isfile(path):
                    return path
    return None


def material_balance(board, color):
    score = 0
    for piece_type, value in MATERIAL_VALUES.items():
        score += len(board.pieces(piece_type, color)) * value
    return score


def material_delta_for_line(fen, line_uci, actor_color, max_plies):
    board = chess.Board(fen)
    start = material_balance(board, actor_color)
    for uci in line_uci[:max_plies]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        board.push(move)
    end = material_balance(board, actor_color)
    return end - start


def pv_to_san(fen, pv_uci, max_plies):
    board = chess.Board(fen)
    san_moves = []
    for uci in pv_uci[:max_plies]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        san_moves.append(board.san(move))
        board.push(move)
    return " ".join(san_moves)


def first_info(details):
    infos = details.get("infos") or []
    for info in infos:
        if info.get("multipv") == 1:
            return info
    return infos[0] if infos else {"pv": []}


def derive_bestmove(details):
    if details.get("bestmove") and details["bestmove"] != "(none)":
        return details["bestmove"]
    info = first_info(details)
    pv = info.get("pv") or []
    return pv[0] if pv else None


def san_for_uci_move(fen, move_uci):
    if not move_uci:
        return "?"
    board = chess.Board(fen)
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        return move_uci
    if move not in board.legal_moves:
        return move_uci
    return board.san(move)


def normalize_whitespace(text):
    return " ".join((text or "").split())


def contains_engine_language(text):
    return bool(LESSON_BANNED_RE.search(text or ""))


def sanitize_human_text(text):
    text = normalize_whitespace(text)
    if not text:
        return ""
    replacements = (
        (r"\bstockfish\b", "analysis"),
        (r"\blc0\b", "analysis"),
        (r"\bengine\b", "analysis"),
        (r"\bpv\b", "line"),
        (r"\beval\b", "position score"),
        (r"\bcentipawn(s)?\b", "score"),
        (r"\bbest move\b", "safer continuation"),
        (r"\btop line\b", "main continuation"),
    )
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def enforce_human_field(text, fallback, max_chars=MAX_COACHING_CHARS):
    cleaned = sanitize_human_text(text)
    if not cleaned or contains_engine_language(cleaned):
        cleaned = sanitize_human_text(fallback)
    if not cleaned:
        cleaned = normalize_whitespace(fallback)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip(" ,;:")
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
    return cleaned

