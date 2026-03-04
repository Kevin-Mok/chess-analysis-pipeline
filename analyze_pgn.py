#!/usr/bin/env python3
import argparse
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

import chess
import chess.pgn

ENGINE = "/usr/games/stockfish"
CPU_THREADS = os.cpu_count() or 1
DEFAULT_THREADS = max(1, CPU_THREADS - 1)
DEFAULT_HASH_MB = 8192
DEFAULT_MAX_SECONDS = 60
DEFAULT_MIN_MS = 80
DEFAULT_MAX_MS = 2500
DEFAULT_POV_PLAYER = "SoloPistol"
PLY_COL_WIDTH = 5
TURN_COL_WIDTH = 3
MOVE_COL_WIDTH = 6
EVAL_COL_WIDTH = 7
PCT_COL_WIDTH = 5
DEFAULT_ANALYSIS_DIR = "analysis"
DEFAULT_SWING_THRESHOLD_SCORE = 0.20
DEFAULT_SWING_MAX_EVENTS = 8
DEFAULT_SWING_SCOPE = "both"
DEFAULT_CAUSE_MODE = "forensic"
DEFAULT_FORENSIC_TIME_MS = 700
DEFAULT_FORENSIC_MULTIPV = 3
DEFAULT_FORENSIC_MAX_PV_PLIES = 6
DEFAULT_LC0_CANDIDATES = (
    "/usr/local/bin/lc0",
    "/usr/bin/lc0",
    "lc0",
)
DEFAULT_LC0_WEIGHTS_CANDIDATES = (
    "/usr/local/share/lc0/best.pb.gz",
    "~/.local/share/lc0/best.pb.gz",
    "models/lc0/best.pb.gz",
    "models/best.pb.gz",
)
DEFAULT_LLAMA_CLI_CANDIDATES = (
    "/usr/local/bin/llama-cli",
    "/usr/bin/llama-cli",
    "llama-cli",
)
DEFAULT_LLAMA_TIMEOUT_MS = 6000
DEFAULT_LLAMA_MAX_TOKENS = 180
DEFAULT_LLAMA_TEMP = 0.2
MATERIAL_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


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


def parse_info_line(line):
    tokens = line.split()
    info = {
        "cp": None,
        "mate": None,
        "wdl": None,
        "multipv": 1,
        "pv": [],
    }
    i = 1  # Skip "info"
    while i < len(tokens):
        tok = tokens[i]
        if tok == "score" and i + 2 < len(tokens):
            if tokens[i + 1] == "cp":
                try:
                    info["cp"] = int(tokens[i + 2])
                    info["mate"] = None
                except ValueError:
                    pass
            elif tokens[i + 1] == "mate":
                try:
                    info["mate"] = int(tokens[i + 2])
                    info["cp"] = None
                except ValueError:
                    pass
            i += 3
            continue
        if tok == "wdl" and i + 3 < len(tokens):
            try:
                info["wdl"] = (int(tokens[i + 1]), int(tokens[i + 2]), int(tokens[i + 3]))
            except ValueError:
                pass
            i += 4
            continue
        if tok == "multipv" and i + 1 < len(tokens):
            try:
                info["multipv"] = max(1, int(tokens[i + 1]))
            except ValueError:
                pass
            i += 2
            continue
        if tok == "pv" and i + 1 < len(tokens):
            info["pv"] = tokens[i + 1 :]
            break
        i += 1
    return info


def approx_wdl_from_cp(cp_white):
    # Lightweight fallback if Stockfish omits WDL in a short search.
    win = 100.0 / (1.0 + math.exp(-cp_white / 180.0))
    loss = 100.0 - win
    draw = max(0.0, min(25.0, 25.0 - abs(cp_white) / 40.0))
    scale = max(1e-9, win + loss)
    factor = (100.0 - draw) / scale
    return round(win * factor, 1), round(draw, 1), round(loss * factor, 1)


class UCIEngine:
    def __init__(
        self,
        engine_path,
        name,
        threads=None,
        hash_mb=None,
        show_wdl=False,
        extra_options=None,
    ):
        self.name = name
        self.proc = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._lines = queue.Queue()
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()
        self.threads = None if threads is None else max(1, int(threads))
        self.hash_mb = None if hash_mb is None else max(16, int(hash_mb))
        self.show_wdl = bool(show_wdl)
        self.extra_options = extra_options or {}
        self._init_uci()

    def _reader_loop(self):
        if self.proc.stdout is None:
            return
        for line in self.proc.stdout:
            self._lines.put(line.rstrip("\n"))
        self._lines.put(None)

    def _send(self, cmd):
        if self.proc.stdin is None:
            raise RuntimeError(f"{self.name} stdin is unavailable.")
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _readline(self, timeout_s):
        timeout_s = max(0.0, timeout_s)
        try:
            line = self._lines.get(timeout=timeout_s)
        except queue.Empty:
            return None
        if line is None:
            raise RuntimeError(f"{self.name} exited unexpectedly.")
        return line

    def _wait_for(self, expected, timeout_s):
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for '{expected}' from {self.name}.")
            line = self._readline(remaining)
            if line is None:
                continue
            if line == expected or line.startswith(expected + " "):
                return

    def _set_option(self, name, value):
        self._send(f"setoption name {name} value {value}")

    def _init_uci(self):
        self._send("uci")
        self._wait_for("uciok", 8.0)
        if self.threads is not None:
            self._set_option("Threads", self.threads)
        if self.hash_mb is not None:
            self._set_option("Hash", self.hash_mb)
        if self.show_wdl:
            self._set_option("UCI_ShowWDL", "true")
        for name, value in self.extra_options.items():
            self._set_option(name, value)
        self._send("isready")
        self._wait_for("readyok", 12.0)

    def analyse_fen(self, fen, movetime_ms, hard_timeout_ms):
        details = self.analyse_fen_detailed(
            fen,
            movetime_ms=movetime_ms,
            hard_timeout_ms=hard_timeout_ms,
            multipv=1,
        )
        return details["cp"], details["mate"], details["wdl"]

    def analyse_fen_detailed(
        self,
        fen,
        movetime_ms,
        hard_timeout_ms,
        multipv=1,
        moves_uci=None,
    ):
        moves_uci = moves_uci or []
        if moves_uci:
            self._send(f"position fen {fen} moves {' '.join(moves_uci)}")
        else:
            self._send(f"position fen {fen}")

        requested_multipv = max(1, int(multipv))
        self._set_option("MultiPV", requested_multipv)
        self._send("isready")
        self._wait_for("readyok", 6.0)

        self._send(f"go movetime {max(1, int(movetime_ms))}")

        best_by_mpv = {}
        bestmove = None
        cp = None
        mate = None
        wdl = None

        deadline = time.monotonic() + (hard_timeout_ms / 1000.0)
        stop_sent = False

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if not stop_sent:
                    self._send("stop")
                    stop_sent = True
                    deadline = time.monotonic() + 1.5
                    continue
                raise TimeoutError(f"Timed out waiting for bestmove from {self.name}.")

            line = self._readline(remaining)
            if line is None:
                continue

            if line.startswith("info "):
                info = parse_info_line(line)
                mpv = info["multipv"] or 1
                entry = best_by_mpv.setdefault(
                    mpv,
                    {
                        "multipv": mpv,
                        "cp": None,
                        "mate": None,
                        "wdl": None,
                        "pv": [],
                    },
                )
                if info["cp"] is not None:
                    entry["cp"] = info["cp"]
                    entry["mate"] = None
                if info["mate"] is not None:
                    entry["mate"] = info["mate"]
                    entry["cp"] = None
                if info["wdl"] is not None:
                    entry["wdl"] = info["wdl"]
                if info["pv"]:
                    entry["pv"] = info["pv"]

                if mpv == 1:
                    cp = entry["cp"]
                    mate = entry["mate"]
                    wdl = entry["wdl"]
                continue

            if line.startswith("bestmove "):
                parts = line.split()
                if len(parts) >= 2:
                    bestmove = parts[1]
                infos = [best_by_mpv[idx] for idx in sorted(best_by_mpv)]
                return {
                    "cp": cp,
                    "mate": mate,
                    "wdl": wdl,
                    "bestmove": bestmove,
                    "infos": infos,
                }

    def quit(self):
        if self.proc.poll() is not None:
            return
        try:
            self._send("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=2.0)


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
    if abs_delta >= 0.50:
        return "Critical"
    if abs_delta >= 0.20:
        return "Major"
    return "Notable"


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


def detect_forensic_cause(
    event,
    board_before,
    board_after,
    played_move,
    best_move_san,
    consensus_loss_cp,
    sf_best_mat_delta,
    sf_played_mat_delta,
    sf_played_eval,
    lc0_played_eval,
):
    loss_cp = consensus_loss_cp if consensus_loss_cp is not None else 0
    material_gap = None
    if sf_best_mat_delta is not None and sf_played_mat_delta is not None:
        material_gap = sf_best_mat_delta - sf_played_mat_delta

    mate_against_actor = False
    for eval_result in (sf_played_eval, lc0_played_eval):
        if eval_result and eval_result.get("mate") is not None and eval_result["mate"] < 0:
            mate_against_actor = True
            break

    captured = captured_piece_type(board_before, played_move)
    if mate_against_actor:
        return (
            "The played move allowed a forcing mating attack in the follow-up line.",
            "Before committing, prioritize king-safety checks and forcing replies against your king.",
        )

    if captured is not None and loss_cp >= 150:
        return (
            f"This looks like a poisoned capture: {event['san']} wins material immediately but loses on tactics.",
            "When capturing, calculate opponent forcing sequences (checks, captures, threats) for 2-3 plies first.",
        )

    if material_gap is not None and material_gap >= 2 and loss_cp >= 120:
        return (
            "The move misses a tactical continuation and concedes material in the engine follow-up.",
            "Scan forcing candidate moves first, then compare resulting material before choosing a move.",
        )

    if board_after.is_check() and loss_cp >= 120:
        return (
            "The move enters a forcing check sequence that worsens the position.",
            "Only play checking or checked positions after confirming the resulting tactical sequence is favorable.",
        )

    if loss_cp >= 250:
        return (
            f"Major evaluation drop from deviating from the engine-preferred continuation ({best_move_san}).",
            "In sharp positions, compare your move against top engine candidates before committing.",
        )

    if loss_cp >= 120:
        return (
            "Noticeable tactical/positional inaccuracy relative to the strongest continuation.",
            "Pause on candidate selection and verify piece coordination and king safety after each candidate.",
        )

    if loss_cp >= 40:
        return (
            "Minor inaccuracy; the played move is playable but less precise than engine preference.",
            "Aim for higher-precision candidate filtering when multiple reasonable moves exist.",
        )

    return (
        "Engines see this as roughly equivalent to top choices with only a small difference.",
        "Keep prioritizing safe, active moves and spend calculation time on critical tactical moments.",
    )


def confidence_from_losses(sf_loss_cp, lc0_loss_cp):
    if sf_loss_cp is None or lc0_loss_cp is None:
        return "Low"

    sf_sign = 1 if sf_loss_cp >= 0 else -1
    lc0_sign = 1 if lc0_loss_cp >= 0 else -1
    if sf_sign != lc0_sign:
        return "Low"

    if abs(sf_loss_cp - lc0_loss_cp) <= 80 and min(abs(sf_loss_cp), abs(lc0_loss_cp)) >= 120:
        return "High"

    return "Medium"


def maybe_llm_rewrite(forensic_report, event, llm_config):
    if not llm_config.get("enabled"):
        return forensic_report

    prompt = (
        "You are rewriting chess analysis facts into concise, grounded coaching text.\n"
        "Use only the provided facts. Do not invent moves, scores, or tactics.\n"
        "Return exactly two lines in this format:\n"
        "Cause: <one sentence>\n"
        "Lesson: <one sentence>\n\n"
        f"Facts:\n"
        f"Move: {event['prefix']} {event['san']} ({event['turn_label']})\n"
        f"Best move: {forensic_report['best_move_san']}\n"
        f"Stockfish loss: {cp_delta_to_text(forensic_report['sf_loss_cp'])}\n"
        f"Lc0 loss: {cp_delta_to_text(forensic_report['lc0_loss_cp'])}\n"
        f"Confidence: {forensic_report['confidence']}\n"
        f"Evidence SF PV: {forensic_report['sf_best_pv'] or 'n/a'}\n"
        f"Evidence Lc0 PV: {forensic_report['lc0_best_pv'] or 'n/a'}\n"
        f"Deterministic cause: {forensic_report['cause']}\n"
        f"Deterministic lesson: {forensic_report['lesson']}\n"
    )

    cmd = [
        llm_config["llama_cli_path"],
        "-m",
        llm_config["llama_model"],
        "-n",
        str(llm_config["llama_max_tokens"]),
        "--temp",
        str(llm_config["llama_temperature"]),
        "--no-display-prompt",
        "-p",
        prompt,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(llm_config["llama_timeout_ms"]) / 1000.0),
            check=False,
        )
    except Exception as exc:
        log(f"llama rewrite failed to execute: {exc}")
        return forensic_report

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        log(f"llama rewrite non-zero exit ({proc.returncode}): {stderr[:160]}")
        return forensic_report

    cause = None
    lesson = None
    for raw_line in (proc.stdout or "").splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("cause:"):
            cause = line.split(":", 1)[1].strip()
        elif lower.startswith("lesson:"):
            lesson = line.split(":", 1)[1].strip()

    if not cause or not lesson:
        return forensic_report

    if len(cause) > 280 or len(lesson) > 220:
        return forensic_report

    updated = dict(forensic_report)
    updated["cause"] = cause
    updated["lesson"] = lesson
    updated["llm_rewritten"] = True
    return updated


def evaluate_for_actor(engine, fen, actor_color, movetime_ms, hard_timeout_ms, multipv=1):
    details = engine.analyse_fen_detailed(
        fen,
        movetime_ms=movetime_ms,
        hard_timeout_ms=hard_timeout_ms,
        multipv=multipv,
    )
    board = chess.Board(fen)
    cp_oriented, mate_oriented = orient_score_to_color(
        details.get("cp"),
        details.get("mate"),
        turn_color=board.turn,
        target_color=actor_color,
    )
    return {
        "details": details,
        "cp": cp_oriented,
        "mate": mate_oriented,
        "score_cp": score_to_cp(cp_oriented, mate_oriented),
        "eval_str": cp_to_eval_str(cp_oriented, mate_oriented),
    }


def build_forensic_report(
    event,
    sf_engine,
    lc0_engine,
    forensic_time_ms,
    forensic_multipv,
    forensic_max_pv_plies,
    llm_config,
):
    fen_before = event["fen_before"]
    fen_after = event["fen_after"]
    played_move_uci = event["move_uci"]

    board_before = chess.Board(fen_before)
    board_after = chess.Board(fen_after)
    actor_color = board_before.turn

    try:
        played_move = chess.Move.from_uci(played_move_uci)
    except ValueError:
        raise RuntimeError(f"Invalid played move UCI in event: {played_move_uci}")

    hard_timeout_ms = max(2500, int(forensic_time_ms) + 2500)

    sf_pre = evaluate_for_actor(
        sf_engine,
        fen_before,
        actor_color=actor_color,
        movetime_ms=forensic_time_ms,
        hard_timeout_ms=hard_timeout_ms,
        multipv=forensic_multipv,
    )
    lc0_pre = evaluate_for_actor(
        lc0_engine,
        fen_before,
        actor_color=actor_color,
        movetime_ms=forensic_time_ms,
        hard_timeout_ms=hard_timeout_ms,
        multipv=forensic_multipv,
    )

    sf_best_uci = derive_bestmove(sf_pre["details"])
    lc0_best_uci = derive_bestmove(lc0_pre["details"])

    if sf_best_uci and lc0_best_uci and sf_best_uci == lc0_best_uci:
        best_move_uci = sf_best_uci
        best_source = "Stockfish+Lc0"
    elif sf_best_uci:
        best_move_uci = sf_best_uci
        best_source = "Stockfish"
    elif lc0_best_uci:
        best_move_uci = lc0_best_uci
        best_source = "Lc0"
    else:
        best_move_uci = None
        best_source = "none"

    best_move_san = san_for_uci_move(fen_before, best_move_uci)

    sf_played = evaluate_for_actor(
        sf_engine,
        fen_after,
        actor_color=actor_color,
        movetime_ms=forensic_time_ms,
        hard_timeout_ms=hard_timeout_ms,
        multipv=1,
    )
    lc0_played = evaluate_for_actor(
        lc0_engine,
        fen_after,
        actor_color=actor_color,
        movetime_ms=forensic_time_ms,
        hard_timeout_ms=hard_timeout_ms,
        multipv=1,
    )

    sf_best_after = {"score_cp": None, "cp": None, "mate": None, "eval_str": "?", "details": {"infos": []}}
    lc0_best_after = {"score_cp": None, "cp": None, "mate": None, "eval_str": "?", "details": {"infos": []}}

    if best_move_uci:
        try:
            best_move = chess.Move.from_uci(best_move_uci)
            if best_move in board_before.legal_moves:
                board_best_after = board_before.copy(stack=False)
                board_best_after.push(best_move)
                fen_best_after = board_best_after.fen()
                sf_best_after = evaluate_for_actor(
                    sf_engine,
                    fen_best_after,
                    actor_color=actor_color,
                    movetime_ms=forensic_time_ms,
                    hard_timeout_ms=hard_timeout_ms,
                    multipv=1,
                )
                lc0_best_after = evaluate_for_actor(
                    lc0_engine,
                    fen_best_after,
                    actor_color=actor_color,
                    movetime_ms=forensic_time_ms,
                    hard_timeout_ms=hard_timeout_ms,
                    multipv=1,
                )
        except ValueError:
            pass

    sf_loss_cp = None
    if sf_best_after["score_cp"] is not None and sf_played["score_cp"] is not None:
        sf_loss_cp = sf_best_after["score_cp"] - sf_played["score_cp"]

    lc0_loss_cp = None
    if lc0_best_after["score_cp"] is not None and lc0_played["score_cp"] is not None:
        lc0_loss_cp = lc0_best_after["score_cp"] - lc0_played["score_cp"]

    if sf_loss_cp is not None and lc0_loss_cp is not None:
        consensus_loss_cp = int(round((sf_loss_cp + lc0_loss_cp) / 2.0))
    elif sf_loss_cp is not None:
        consensus_loss_cp = sf_loss_cp
    elif lc0_loss_cp is not None:
        consensus_loss_cp = lc0_loss_cp
    else:
        consensus_loss_cp = None

    sf_best_info = first_info(sf_pre["details"])
    sf_played_info = first_info(sf_played["details"])
    sf_best_line = sf_best_info.get("pv") or ([best_move_uci] if best_move_uci else [])
    sf_played_line = [played_move_uci] + (sf_played_info.get("pv") or [])

    sf_best_mat_delta = material_delta_for_line(
        fen_before,
        sf_best_line,
        actor_color=actor_color,
        max_plies=forensic_max_pv_plies,
    )
    sf_played_mat_delta = material_delta_for_line(
        fen_before,
        sf_played_line,
        actor_color=actor_color,
        max_plies=forensic_max_pv_plies,
    )

    cause, lesson = detect_forensic_cause(
        event,
        board_before=board_before,
        board_after=board_after,
        played_move=played_move,
        best_move_san=best_move_san,
        consensus_loss_cp=consensus_loss_cp,
        sf_best_mat_delta=sf_best_mat_delta,
        sf_played_mat_delta=sf_played_mat_delta,
        sf_played_eval=sf_played,
        lc0_played_eval=lc0_played,
    )

    report = {
        "best_move_uci": best_move_uci,
        "best_move_san": best_move_san,
        "best_source": best_source,
        "sf_loss_cp": sf_loss_cp,
        "lc0_loss_cp": lc0_loss_cp,
        "consensus_loss_cp": consensus_loss_cp,
        "confidence": confidence_from_losses(sf_loss_cp, lc0_loss_cp),
        "sf_best_pv": pv_to_san(fen_before, sf_best_line, forensic_max_pv_plies),
        "lc0_best_pv": pv_to_san(
            fen_before,
            (first_info(lc0_pre["details"]).get("pv") or []),
            forensic_max_pv_plies,
        ),
        "cause": cause,
        "lesson": lesson,
        "llm_rewritten": False,
    }

    return maybe_llm_rewrite(report, event, llm_config)


def render_significant_swings(
    out,
    swing_events,
    swing_threshold_score,
    swing_scope,
    swing_max_events,
    cause_mode,
):
    print("", file=out, flush=True)
    print("## Significant Swings", file=out, flush=True)
    print("", file=out, flush=True)
    print(
        f"- Config: threshold={swing_threshold_score * 100:.1f} pts, "
        f"scope={swing_scope}, max-events={swing_max_events}, cause-mode={cause_mode}",
        file=out,
        flush=True,
    )

    if swing_max_events <= 0:
        print("- Swing highlights disabled (`--swing-max-events 0`).", file=out, flush=True)
        return

    if not swing_events:
        print("- No swings met the configured threshold.", file=out, flush=True)
        return

    selected_events = select_swing_events(swing_events, swing_max_events)
    good_events = [event for event in selected_events if event["delta"] > 0]
    bad_events = [event for event in selected_events if event["delta"] < 0]
    neutral_events = [event for event in selected_events if event["delta"] == 0]
    event_groups = [
        ("Good (+me / -op.)", good_events),
        ("Bad (-me / +op.)", bad_events),
        ("Neutral", neutral_events),
    ]

    def render_event(event):
        delta_points = event["delta"] * 100.0
        sign = "+" if delta_points >= 0 else ""
        me_delta = delta_points
        op_delta = -delta_points
        print(
            (
                f"- [{event['severity']}] {event['prefix']} {event['san']} ({event['turn_label']}): "
                f"expected score {event['before_score']:.2f} -> {event['after_score']:.2f} "
                f"({sign}{delta_points:.1f} pts), eval {event['before_eval']} -> {event['after_eval']}"
            ),
            file=out,
            flush=True,
        )
        print(
            (
                f"  Impact: me={swing_polarity_label(me_delta)} ({me_delta:+.1f} pts), "
                f"op.={swing_polarity_label(op_delta)} ({op_delta:+.1f} pts)"
            ),
            file=out,
            flush=True,
        )

        forensic = event.get("forensic")
        if forensic:
            print(
                (
                    f"  Best: {forensic['best_move_san']} ({forensic['best_source']}) | "
                    f"Played: {event['san']} | Opportunity cost: {cp_delta_to_text(forensic['consensus_loss_cp'])}"
                ),
                file=out,
                flush=True,
            )
            print(
                (
                    f"  Engines: Stockfish={cp_delta_to_text(forensic['sf_loss_cp'])}, "
                    f"Lc0={cp_delta_to_text(forensic['lc0_loss_cp'])}, "
                    f"confidence={forensic['confidence']}"
                ),
                file=out,
                flush=True,
            )
            if forensic.get("sf_best_pv") or forensic.get("lc0_best_pv"):
                print(
                    (
                        f"  Evidence: SF PV {forensic.get('sf_best_pv') or 'n/a'} | "
                        f"Lc0 PV {forensic.get('lc0_best_pv') or 'n/a'}"
                    ),
                    file=out,
                    flush=True,
                )
            print(f"  Cause: {forensic['cause']}", file=out, flush=True)
            print(f"  Lesson: {forensic['lesson']}", file=out, flush=True)
        else:
            if event.get("forensic_error"):
                print(
                    f"  Cause: forensic analysis failed ({event['forensic_error']}). Falling back to heuristic.",
                    file=out,
                    flush=True,
                )
            print(f"  Cause: {event['reason']}", file=out, flush=True)

    rendered_any_group = False
    for heading, grouped_events in event_groups:
        if not grouped_events:
            continue
        print("", file=out, flush=True)
        print(f"### {heading}", file=out, flush=True)
        for index, event in enumerate(grouped_events):
            render_event(event)
            if index < len(grouped_events) - 1:
                print("", file=out, flush=True)
        rendered_any_group = True


def validate_forensic_stack(cause_mode, lc0_path, lc0_weights):
    if cause_mode not in ("forensic", "forensic-llm"):
        return
    if not lc0_path:
        raise SystemExit(
            "Forensic mode requires Lc0. Install it first or pass --lc0-path explicitly."
        )
    if not lc0_weights:
        raise SystemExit(
            "Forensic mode requires Lc0 weights (.pb.gz). Install to /usr/local/share/lc0/best.pb.gz "
            "or pass --lc0-weights explicitly."
        )


def main(
    pgn_path,
    depth=18,
    threads=DEFAULT_THREADS,
    hash_mb=DEFAULT_HASH_MB,
    max_seconds=DEFAULT_MAX_SECONDS,
    min_ms=DEFAULT_MIN_MS,
    max_ms=DEFAULT_MAX_MS,
    pov_player=DEFAULT_POV_PLAYER,
    swing_threshold_score=DEFAULT_SWING_THRESHOLD_SCORE,
    swing_max_events=DEFAULT_SWING_MAX_EVENTS,
    swing_scope=DEFAULT_SWING_SCOPE,
    cause_mode=DEFAULT_CAUSE_MODE,
    lc0_path=None,
    lc0_weights=None,
    forensic_time_ms=DEFAULT_FORENSIC_TIME_MS,
    forensic_multipv=DEFAULT_FORENSIC_MULTIPV,
    forensic_max_pv_plies=DEFAULT_FORENSIC_MAX_PV_PLIES,
    llama_cli_path=None,
    llama_model=None,
    llama_timeout_ms=DEFAULT_LLAMA_TIMEOUT_MS,
    llama_max_tokens=DEFAULT_LLAMA_MAX_TOKENS,
    llama_temperature=DEFAULT_LLAMA_TEMP,
    output_md=None,
):
    with open(pgn_path, "r", encoding="utf-8", errors="replace") as f:
        game = chess.pgn.read_game(f)
    if not game:
        raise SystemExit("No game found in PGN.")

    start = time.perf_counter()
    deadline = start + max(1, float(max_seconds))
    table_engine = UCIEngine(
        ENGINE,
        name="Stockfish",
        threads=threads,
        hash_mb=hash_mb,
        show_wdl=True,
    )

    try:
        threads = max(1, int(threads))
        hash_mb = max(16, int(hash_mb))
        min_ms = max(20, int(min_ms))
        max_ms = max(min_ms, int(max_ms))
        swing_threshold_score = max(0.0, float(swing_threshold_score))
        swing_max_events = max(0, int(swing_max_events))
        forensic_time_ms = max(80, int(forensic_time_ms))
        forensic_multipv = max(1, int(forensic_multipv))
        forensic_max_pv_plies = max(2, int(forensic_max_pv_plies))

        lc0_bin = None
        lc0_weights_path = None
        if cause_mode in ("forensic", "forensic-llm"):
            lc0_bin = resolve_executable(lc0_path, DEFAULT_LC0_CANDIDATES)
            lc0_weights_path = resolve_lc0_weights(lc0_weights)
            validate_forensic_stack(cause_mode, lc0_bin, lc0_weights_path)

        total_plies = sum(1 for _ in game.mainline_moves())
        white = game.headers.get("White", "?")
        black = game.headers.get("Black", "?")
        pov_color, pov_name, opponent_name, pov_found = resolve_pov(game, pov_player)
        pov_side = "White" if pov_color == chess.WHITE else "Black"
        if output_md is None:
            output_md = default_output_md_path(
                white,
                black,
                pov_name,
                opponent_name,
                pov_found,
            )

        if output_md != "-":
            output_dir = os.path.dirname(output_md)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            out = open(output_md, "w", encoding="utf-8")
        else:
            out = sys.stdout

        if pov_found:
            title = f"# {pov_name} vs {opponent_name} ({pov_name} POV)"
        else:
            title = f"# {white} vs {black}"
        log(
            f"Starting analysis: {white} vs {black}, plies={total_plies}, depth_hint={depth}, "
            f"threads={threads}, hash_mb={hash_mb}, max_seconds={max_seconds}, cause_mode={cause_mode}"
        )
        if pov_found:
            log(f"POV mode: player='{pov_name}' ({pov_side})")
        else:
            log(
                f"POV mode: player='{pov_player}' not found in headers; "
                "falling back to White POV."
            )
        log("Engine mode: direct UCI subprocess.")

        # Stream markdown output immediately so redirected output grows during analysis.
        print(title, file=out, flush=True)
        print("", file=out, flush=True)
        print(f"- White: `{white}`", file=out, flush=True)
        print(f"- Black: `{black}`", file=out, flush=True)
        if pov_found:
            print(f"- POV: `{pov_name}` ({pov_side})", file=out, flush=True)
            print(
                f"- Turn labels: `me` = `{pov_name}`, `op.` = `{opponent_name}`",
                file=out,
                flush=True,
            )
        else:
            print("- POV: `White` (fallback)", file=out, flush=True)
            print(f"- Turn labels: `me` = `{white}`, `op.` = `{black}`", file=out, flush=True)
        print("", file=out, flush=True)
        header = format_row("Ply", "Turn", "Move", "Win%", "Loss%", "Draw%", "Eval")
        print("```text", file=out, flush=True)
        print(header, file=out, flush=True)
        print("-" * len(header), file=out, flush=True)

        board = game.board()
        ply = 0
        previous_scored_ply = None
        swing_events = []
        for move in game.mainline_moves():
            board_before = board.copy(stack=False)
            san = board.san(move)
            board.push(move)
            ply += 1

            remaining_plies = max(1, total_plies - ply + 1)
            remaining_ms = max(0, int((deadline - time.perf_counter()) * 1000))
            # Keep a small guard band so wall time stays under target more reliably.
            usable_remaining_ms = int(remaining_ms * 0.92)
            target_ms = usable_remaining_ms // remaining_plies if remaining_plies else min_ms
            movetime_ms = max(min_ms, min(max_ms, max(1, target_ms)))
            hard_timeout_ms = movetime_ms + 2500

            cp = None
            mate = None
            wdl = None
            try:
                cp, mate, wdl = table_engine.analyse_fen(board.fen(), movetime_ms, hard_timeout_ms)
            except Exception as exc:
                log(f"[{ply}/{total_plies}] engine timeout/error at move {san}: {exc}; restarting engine.")
                table_engine.quit()
                table_engine = UCIEngine(
                    ENGINE,
                    name="Stockfish",
                    threads=threads,
                    hash_mb=hash_mb,
                    show_wdl=True,
                )

            cp, mate, wdl = to_pov(board, cp, mate, wdl, pov_color)

            if mate is not None:
                eval_str = f"M{mate:+d}"
            elif cp is not None:
                eval_str = f"{cp / 100:.2f}"
            else:
                eval_str = "?"

            if wdl is not None:
                total = wdl[0] + wdl[1] + wdl[2]
                w, d, l = pct(wdl[0], total), pct(wdl[1], total), pct(wdl[2], total)
            elif cp is not None:
                w, d, l = approx_wdl_from_cp(cp)
            else:
                w, d, l = 0.0, 100.0, 0.0

            move_no = (ply + 1) // 2
            prefix = f"{move_no}." if ply % 2 == 1 else f"{move_no}..."
            mover_color = chess.WHITE if ply % 2 == 1 else chess.BLACK
            turn_label = "me" if mover_color == pov_color else "op."
            mover_is_pov = mover_color == pov_color

            score = None
            if mate is not None or cp is not None or wdl is not None:
                score = expected_score(w, d)

            if score is not None:
                current_scored_ply = {
                    "ply": ply,
                    "prefix": prefix,
                    "san": san,
                    "turn_label": turn_label,
                    "mover_is_pov": mover_is_pov,
                    "score": score,
                    "eval_str": eval_str,
                }
                if previous_scored_ply is not None:
                    delta = score - previous_scored_ply["score"]
                    abs_delta = abs(delta)
                    if (
                        abs_delta >= swing_threshold_score
                        and should_track_swing(swing_scope, mover_is_pov)
                    ):
                        swing_events.append(
                            {
                                "ply": ply,
                                "prefix": prefix,
                                "san": san,
                                "move_uci": move.uci(),
                                "fen_before": board_before.fen(),
                                "fen_after": board.fen(),
                                "turn_label": turn_label,
                                "before_score": previous_scored_ply["score"],
                                "after_score": score,
                                "before_eval": previous_scored_ply["eval_str"],
                                "after_eval": eval_str,
                                "delta": delta,
                                "severity": swing_severity(abs_delta),
                                "reason": infer_swing_reason(
                                    board_before,
                                    board,
                                    move,
                                    mate,
                                    delta,
                                    mover_is_pov,
                                ),
                            }
                        )
                previous_scored_ply = current_scored_ply

            print(format_row(prefix, turn_label, san, w, l, d, eval_str), file=out, flush=True)
            elapsed = time.perf_counter() - start
            log(
                f"[{ply}/{total_plies}] {prefix} {san}: eval={eval_str}, W/D/L={w}/{d}/{l}, "
                f"movetime_ms={movetime_ms}, elapsed={elapsed:.1f}s"
            )

        if cause_mode in ("forensic", "forensic-llm") and swing_events and swing_max_events > 0:
            llm_bin = resolve_executable(llama_cli_path, DEFAULT_LLAMA_CLI_CANDIDATES)
            llm_model_path = os.path.abspath(os.path.expanduser(llama_model)) if llama_model else None
            llm_enabled = (
                cause_mode == "forensic-llm"
                and llm_bin is not None
                and llm_model_path is not None
                and os.path.isfile(llm_model_path)
            )
            if cause_mode == "forensic-llm" and not llm_enabled:
                log(
                    "forensic-llm requested but llama-cli/model not available; "
                    "using deterministic forensic descriptions."
                )

            llm_config = {
                "enabled": llm_enabled,
                "llama_cli_path": llm_bin,
                "llama_model": llm_model_path,
                "llama_timeout_ms": max(1000, int(llama_timeout_ms)),
                "llama_max_tokens": max(64, int(llama_max_tokens)),
                "llama_temperature": float(llama_temperature),
            }

            target_events = select_swing_events(swing_events, swing_max_events)
            phase_start = time.perf_counter()
            log(
                f"Starting forensic phase: events={len(target_events)}/{len(swing_events)}, "
                f"forensic_time_ms={forensic_time_ms}, multipv={forensic_multipv}, llm_enabled={llm_enabled}"
            )
            sf_forensic = UCIEngine(
                ENGINE,
                name="Stockfish-forensic",
                threads=threads,
                hash_mb=hash_mb,
                show_wdl=True,
            )
            lc0_forensic = UCIEngine(
                lc0_bin,
                name="Lc0",
                show_wdl=True,
                extra_options={"WeightsFile": lc0_weights_path},
            )
            try:
                for idx, event in enumerate(target_events, start=1):
                    event_start = time.perf_counter()
                    log(
                        f"[forensic {idx}/{len(target_events)}] analyzing {event['prefix']} {event['san']} "
                        f"({event['turn_label']})"
                    )
                    try:
                        event["forensic"] = build_forensic_report(
                            event,
                            sf_engine=sf_forensic,
                            lc0_engine=lc0_forensic,
                            forensic_time_ms=forensic_time_ms,
                            forensic_multipv=forensic_multipv,
                            forensic_max_pv_plies=forensic_max_pv_plies,
                            llm_config=llm_config,
                        )
                        event_elapsed = time.perf_counter() - event_start
                        log(
                            f"[forensic {idx}/{len(target_events)}] done {event['prefix']} {event['san']} "
                            f"in {event_elapsed:.1f}s"
                        )
                    except Exception as exc:
                        event["forensic_error"] = str(exc)
                        log(f"forensic analysis failed at {event['prefix']} {event['san']}: {exc}")
            finally:
                lc0_forensic.quit()
                sf_forensic.quit()
                phase_elapsed = time.perf_counter() - phase_start
                log(f"Completed forensic phase in {phase_elapsed:.1f}s.")

        print("```", file=out, flush=True)
        render_significant_swings(
            out,
            swing_events,
            swing_threshold_score=swing_threshold_score,
            swing_scope=swing_scope,
            swing_max_events=swing_max_events,
            cause_mode=cause_mode,
        )
        log(
            f"Detected {len(swing_events)} significant swings at threshold "
            f"{swing_threshold_score:.2f} (scope={swing_scope}, cause_mode={cause_mode})."
        )
        if out is not sys.stdout:
            out.close()
            log(f"Wrote analysis markdown to {output_md}")

        elapsed = time.perf_counter() - start
        log(f"Completed analysis in {elapsed:.1f}s.")
    finally:
        try:
            if "out" in locals() and out is not sys.stdout and not out.closed:
                out.close()
        except Exception:
            pass
        table_engine.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze PGN and stream WDL markdown output.")
    parser.add_argument("pgn_path", help="Path to PGN file")
    parser.add_argument(
        "depth",
        nargs="?",
        type=int,
        default=18,
        help="Legacy quality hint, kept for CLI compatibility (default: 18)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Stockfish Threads option (default: cpu_count-1={DEFAULT_THREADS})",
    )
    parser.add_argument(
        "--hash-mb",
        type=int,
        default=DEFAULT_HASH_MB,
        help=f"Stockfish Hash option in MB (default: {DEFAULT_HASH_MB})",
    )
    parser.add_argument(
        "--max-seconds",
        type=int,
        default=DEFAULT_MAX_SECONDS,
        help=f"Target wall-time budget in seconds (default: {DEFAULT_MAX_SECONDS})",
    )
    parser.add_argument(
        "--min-ms",
        type=int,
        default=DEFAULT_MIN_MS,
        help=f"Minimum movetime per ply in ms (default: {DEFAULT_MIN_MS})",
    )
    parser.add_argument(
        "--max-ms",
        type=int,
        default=DEFAULT_MAX_MS,
        help=f"Maximum movetime per ply in ms (default: {DEFAULT_MAX_MS})",
    )
    parser.add_argument(
        "--pov-player",
        type=str,
        default=DEFAULT_POV_PLAYER,
        help=(
            f"Player name for POV-oriented Eval/WDL (default: {DEFAULT_POV_PLAYER}); "
            "if not found in PGN headers, falls back to White POV"
        ),
    )
    parser.add_argument(
        "--swing-threshold-score",
        type=float,
        default=DEFAULT_SWING_THRESHOLD_SCORE,
        help=(
            "Significant swing threshold in expected-score units (0.20 = 20 pts); "
            f"default: {DEFAULT_SWING_THRESHOLD_SCORE}"
        ),
    )
    parser.add_argument(
        "--swing-max-events",
        type=int,
        default=DEFAULT_SWING_MAX_EVENTS,
        help=f"Max number of significant swings to list (default: {DEFAULT_SWING_MAX_EVENTS})",
    )
    parser.add_argument(
        "--swing-scope",
        type=str,
        choices=("both", "pov", "opponent"),
        default=DEFAULT_SWING_SCOPE,
        help=(
            "Which mover is eligible for swing highlights: "
            f"'both', 'pov', or 'opponent' (default: {DEFAULT_SWING_SCOPE})"
        ),
    )
    parser.add_argument(
        "--cause-mode",
        type=str,
        choices=("heuristic", "forensic", "forensic-llm"),
        default=DEFAULT_CAUSE_MODE,
        help=(
            "Cause generation mode: heuristic (fast), forensic (Stockfish+Lc0), "
            f"or forensic-llm (forensic + optional local llama rewrite); default: {DEFAULT_CAUSE_MODE}"
        ),
    )
    parser.add_argument(
        "--lc0-path",
        type=str,
        default=None,
        help="Path to lc0 binary (auto-detected if omitted)",
    )
    parser.add_argument(
        "--lc0-weights",
        type=str,
        default=None,
        help="Path to lc0 network .pb.gz (auto-detected if omitted)",
    )
    parser.add_argument(
        "--forensic-time-ms",
        type=int,
        default=DEFAULT_FORENSIC_TIME_MS,
        help=f"Per-probe movetime for forensic pass in ms (default: {DEFAULT_FORENSIC_TIME_MS})",
    )
    parser.add_argument(
        "--forensic-multipv",
        type=int,
        default=DEFAULT_FORENSIC_MULTIPV,
        help=f"MultiPV width for forensic best-line probes (default: {DEFAULT_FORENSIC_MULTIPV})",
    )
    parser.add_argument(
        "--forensic-max-pv-plies",
        type=int,
        default=DEFAULT_FORENSIC_MAX_PV_PLIES,
        help=f"Max plies from PV shown/used in forensic evidence (default: {DEFAULT_FORENSIC_MAX_PV_PLIES})",
    )
    parser.add_argument(
        "--llama-cli-path",
        type=str,
        default=None,
        help="Path to llama-cli binary (auto-detected in forensic-llm mode if omitted)",
    )
    parser.add_argument(
        "--llama-model",
        type=str,
        default=None,
        help="Path to local GGUF model for optional forensic-llm rewrite",
    )
    parser.add_argument(
        "--llama-timeout-ms",
        type=int,
        default=DEFAULT_LLAMA_TIMEOUT_MS,
        help=f"Timeout for each llama-cli rewrite in ms (default: {DEFAULT_LLAMA_TIMEOUT_MS})",
    )
    parser.add_argument(
        "--llama-max-tokens",
        type=int,
        default=DEFAULT_LLAMA_MAX_TOKENS,
        help=f"Max tokens for each llama-cli rewrite (default: {DEFAULT_LLAMA_MAX_TOKENS})",
    )
    parser.add_argument(
        "--llama-temperature",
        type=float,
        default=DEFAULT_LLAMA_TEMP,
        help=f"Sampling temperature for llama-cli rewrite (default: {DEFAULT_LLAMA_TEMP})",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default=None,
        help=(
            "Markdown output path (default: auto-generated under analysis/). "
            "Use '-' to write to stdout."
        ),
    )
    args = parser.parse_args()
    main(
        args.pgn_path,
        depth=args.depth,
        threads=args.threads,
        hash_mb=args.hash_mb,
        max_seconds=args.max_seconds,
        min_ms=args.min_ms,
        max_ms=args.max_ms,
        pov_player=args.pov_player,
        swing_threshold_score=args.swing_threshold_score,
        swing_max_events=args.swing_max_events,
        swing_scope=args.swing_scope,
        cause_mode=args.cause_mode,
        lc0_path=args.lc0_path,
        lc0_weights=args.lc0_weights,
        forensic_time_ms=args.forensic_time_ms,
        forensic_multipv=args.forensic_multipv,
        forensic_max_pv_plies=args.forensic_max_pv_plies,
        llama_cli_path=args.llama_cli_path,
        llama_model=args.llama_model,
        llama_timeout_ms=args.llama_timeout_ms,
        llama_max_tokens=args.llama_max_tokens,
        llama_temperature=args.llama_temperature,
        output_md=args.output_md,
    )
