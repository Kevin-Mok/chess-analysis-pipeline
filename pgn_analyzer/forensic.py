from __future__ import annotations

import json
import os
import re
import subprocess
from urllib import error as urllib_error
from urllib import request as urllib_request

import chess

from .common import (
    captured_piece_type,
    cp_delta_to_text,
    cp_to_eval_str,
    derive_bestmove,
    enforce_human_field,
    first_info,
    material_delta_for_line,
    normalize_whitespace,
    orient_score_to_color,
    pv_to_san,
    san_for_uci_move,
    score_to_cp,
)
from .constants import (
    COACHING_FIELDS,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_TIMEOUT_MS,
    MAX_CAUSE_CHARS,
)

def count_loose_pieces(board, color):
    loose = []
    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        if board.is_attacked_by(not color, square) and not board.is_attacked_by(color, square):
            loose.append(square)
    return loose


def cct_profile(board):
    checks = 0
    captures = 0
    for move in board.legal_moves:
        if board.gives_check(move):
            checks += 1
        if board.is_capture(move):
            captures += 1
    return {"checks": checks, "captures": captures}


def classify_forensic_motif(mate_against_actor, captured, material_gap, board_after, loss_cp):
    if mate_against_actor:
        return "mate_threat"
    if captured is not None and loss_cp >= 150:
        return "poisoned_capture"
    if material_gap is not None and material_gap >= 2 and loss_cp >= 120:
        return "material_drop"
    if board_after.is_check() and loss_cp >= 120:
        return "forcing_sequence"
    if loss_cp >= 250:
        return "major_deviation"
    if loss_cp >= 120:
        return "inaccuracy"
    if loss_cp >= 40:
        return "minor_inaccuracy"
    return "near_equal"


def motif_defaults(motif):
    defaults = {
        "mate_threat": {
            "failure": "it allowed a forcing attack against your king",
            "thought": (
                "A human often focuses on their own idea and underweights immediate danger to the king. "
                "The move felt natural, but it likely skipped a full danger scan of forcing replies."
            ),
            "missed": (
                "You needed a direct king-safety check: list opponent checks first, then captures that open lines "
                "toward your king."
            ),
            "process": "1) List opponent checks. 2) Reject moves that allow forcing checks. 3) Only then compare candidate plans.",
            "habit": "Before every sharp move, do a 10-second king danger scan: checks, captures, threats.",
            "lesson": "In sharp positions, king safety is the first filter, not the last.",
        },
        "poisoned_capture": {
            "failure": "it won material short-term but handed over tactical momentum",
            "thought": (
                "Humans are pulled toward obvious material gains and can stop calculating once a capture looks winning. "
                "The trap is ending the calculation before testing the opponent's forcing reply."
            ),
            "missed": (
                "The key missed cue is recapture/tempo risk after the grab: loose pieces, exposed king, and forcing counterplay."
            ),
            "process": (
                "1) After any tempting capture, calculate the opponent's forcing reply first. "
                "2) Re-check king safety and piece safety two plies deep. 3) If unclear, choose the safer improving move."
            ),
            "habit": "Treat every 'free' pawn or piece as suspicious until the tactical sequence is proven safe.",
            "lesson": "If a gain looks free, verify the punishment line before taking it.",
        },
        "material_drop": {
            "failure": "it missed a tactical resource and allowed avoidable material damage",
            "thought": (
                "Humans often lock onto one plan and fail to refresh candidate moves after the position changes. "
                "That causes tactical resources to be overlooked."
            ),
            "missed": "The missed cue was tactical forcing order: checks and captures changed the material outcome quickly.",
            "process": (
                "1) Rebuild candidate moves from scratch. 2) Prioritize forcing moves before quiet plans. "
                "3) Compare resulting material after each forcing branch."
            ),
            "habit": "When the position is tactical, restart candidate generation every move.",
            "lesson": "In tactical positions, forcing move order decides material outcomes.",
        },
        "forcing_sequence": {
            "failure": "it stepped into a forcing sequence and reduced your practical choices",
            "thought": (
                "A move can look active but still hand initiative away if the opponent gets forcing tempo moves. "
                "Humans underestimate this when they don't compare initiative after each candidate."
            ),
            "missed": "You needed to count forcing replies available to the opponent after your move.",
            "process": (
                "1) For each candidate, count opponent forcing moves. 2) Prefer candidates that reduce forcing replies. "
                "3) Keep king and loose pieces stable."
            ),
            "habit": "Judge candidate quality by how many forcing replies you concede.",
            "lesson": "Good moves reduce opponent forcing options, not just improve your own piece.",
        },
        "major_deviation": {
            "failure": "it created a large practical drop compared with safer continuations",
            "thought": (
                "Humans under time pressure often pick the first workable move instead of comparing two serious candidates. "
                "That shortcut is costly in sharp middlegames."
            ),
            "missed": "The missed cue was decision quality, not only tactics: candidate comparison and safety checks were incomplete.",
            "process": (
                "1) Pick two serious candidates. 2) Run a brief CCT scan for both sides on each. "
                "3) Choose the line with fewer immediate tactical liabilities."
            ),
            "habit": "Never play the first acceptable move in sharp positions; compare at least two candidates.",
            "lesson": "Candidate comparison prevents large practical blunders.",
        },
        "inaccuracy": {
            "failure": "it weakened coordination and handed over initiative",
            "thought": "The move looked playable, but a deeper safety/coordination check would have flagged the downside.",
            "missed": "You likely missed piece coordination and loose-piece tension after the move.",
            "process": "1) Check king safety. 2) Check loose pieces. 3) Prefer moves that improve both activity and stability.",
            "habit": "Use a fixed three-step blunder check before committing.",
            "lesson": "Solid coordination beats speculative activity.",
        },
        "minor_inaccuracy": {
            "failure": "it was playable but less accurate than safer alternatives",
            "thought": "Humans often choose a reasonable plan without testing whether a cleaner move avoids future problems.",
            "missed": "Small improvements in safety and coordination were available.",
            "process": "1) Test one alternative move. 2) Compare safety after one opponent reply. 3) Pick the cleaner structure.",
            "habit": "In quiet positions, spend one extra check on piece safety and structure.",
            "lesson": "Precision in quiet moments prevents future tactical strain.",
        },
        "near_equal": {
            "failure": "it kept the position close and mostly practical",
            "thought": "The decision was acceptable; refinement is mostly about cleaner move ordering.",
            "missed": "No major tactical cue was missed, only small efficiency gains.",
            "process": "1) Maintain king safety. 2) Improve worst piece. 3) Avoid creating new weaknesses.",
            "habit": "Keep a simple positional checklist in equal positions.",
            "lesson": "When nothing tactical is urgent, improve piece quality and structure.",
        },
    }
    return defaults[motif]


def build_deterministic_forensic_coaching(
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
    sf_loss_cp,
    lc0_loss_cp,
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
    motif = classify_forensic_motif(mate_against_actor, captured, material_gap, board_after, loss_cp)
    defaults = motif_defaults(motif)

    best_label = best_move_san if best_move_san and best_move_san != "?" else "a safer continuation"
    delta_points = (event["after_score"] - event["before_score"]) * 100.0
    sf_text = cp_delta_to_text(sf_loss_cp)
    lc0_text = cp_delta_to_text(lc0_loss_cp)

    cue_profile = cct_profile(board_after)
    actor_color = board_before.turn
    loose_before = count_loose_pieces(board_before, actor_color)
    loose_after = count_loose_pieces(board_after, actor_color)
    captured_name = chess.piece_name(captured) if captured is not None else None

    extra_cues = []
    if captured_name:
        extra_cues.append(f"You captured a {captured_name}, so recapture tempo needed deeper verification.")
    if cue_profile["checks"] > 0:
        extra_cues.append(
            f"After your move, the opponent had {cue_profile['checks']} checking idea(s), which is a forcing-warning signal."
        )
    if cue_profile["captures"] > 0:
        extra_cues.append(
            f"After your move, the opponent also had {cue_profile['captures']} capture(s), increasing tactical volatility."
        )
    if len(loose_after) > len(loose_before):
        extra_cues.append(
            f"Your move increased loose-piece pressure ({len(loose_before)} -> {len(loose_after)} loose pieces)."
        )
    if not extra_cues:
        extra_cues.append("The practical risk came from move-order and safety checks, not from one obvious tactical shot.")

    cause_summary = (
        f"{event['prefix']} {event['san']} was inferior to {best_label}; {defaults['failure']}. "
        f"Evidence: expected score {event['before_score']:.2f} -> {event['after_score']:.2f} ({delta_points:+.1f} pts), "
        f"Stockfish {sf_text}, Lc0 {lc0_text}."
    )
    human_thought_process = defaults["thought"]
    missed_cues = f"{defaults['missed']} " + " ".join(extra_cues[:2])
    better_decision_process = defaults["process"]
    practice_habit = defaults["habit"]
    lesson = defaults["lesson"]

    return {
        "motif": motif,
        "cause_summary": cause_summary,
        "human_thought_process": human_thought_process,
        "missed_cues": missed_cues,
        "better_decision_process": better_decision_process,
        "practice_habit": practice_habit,
        "lesson": lesson,
        # Backward-compatible aliases used by existing rendering/consumers.
        "cause": cause_summary,
    }


def finalize_human_coaching_fields(report):
    defaults = motif_defaults(report.get("motif", "inaccuracy"))
    report["human_thought_process"] = enforce_human_field(
        report.get("human_thought_process"),
        defaults["thought"],
    )
    report["missed_cues"] = enforce_human_field(
        report.get("missed_cues"),
        defaults["missed"],
    )
    report["better_decision_process"] = enforce_human_field(
        report.get("better_decision_process"),
        defaults["process"],
    )
    report["practice_habit"] = enforce_human_field(
        report.get("practice_habit"),
        defaults["habit"],
    )
    report["lesson"] = enforce_human_field(
        report.get("lesson"),
        defaults["lesson"],
    )
    cause_summary = normalize_whitespace(report.get("cause_summary"))
    if not cause_summary:
        cause_summary = "The move created a practical drop in a tactical position; use slower candidate comparison."
    if len(cause_summary) > MAX_CAUSE_CHARS:
        cause_summary = cause_summary[:MAX_CAUSE_CHARS].rstrip(" ,;:")
        if cause_summary and cause_summary[-1] not in ".!?":
            cause_summary += "."
    report["cause_summary"] = cause_summary
    report["cause"] = cause_summary
    report["lesson"] = normalize_whitespace(report["lesson"])
    return report


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
    sf_loss_cp,
    lc0_loss_cp,
):
    coaching = build_deterministic_forensic_coaching(
        event,
        board_before=board_before,
        board_after=board_after,
        played_move=played_move,
        best_move_san=best_move_san,
        consensus_loss_cp=consensus_loss_cp,
        sf_best_mat_delta=sf_best_mat_delta,
        sf_played_mat_delta=sf_played_mat_delta,
        sf_played_eval=sf_played_eval,
        lc0_played_eval=lc0_played_eval,
        sf_loss_cp=sf_loss_cp,
        lc0_loss_cp=lc0_loss_cp,
    )
    return finalize_human_coaching_fields(coaching)


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


def normalize_ollama_host(host):
    host = normalize_whitespace(host or DEFAULT_OLLAMA_HOST).rstrip("/")
    if not host:
        host = DEFAULT_OLLAMA_HOST
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "http://" + host
    return host.rstrip("/")


def ollama_request_json(host, path, payload=None, timeout_ms=2000):
    host = normalize_ollama_host(host)
    url = f"{host}{path}"
    body = None
    headers = {}
    method = "GET"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    req = urllib_request.Request(url, data=body, headers=headers, method=method)
    timeout_s = None
    if timeout_ms is not None:
        try:
            timeout_ms = int(timeout_ms)
        except (TypeError, ValueError):
            timeout_ms = 2000
        if timeout_ms > 0:
            timeout_s = max(1, timeout_ms) / 1000.0

    try:
        if timeout_s is None:
            response_ctx = urllib_request.urlopen(req)
        else:
            response_ctx = urllib_request.urlopen(req, timeout=timeout_s)
        with response_ctx as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except (urllib_error.URLError, urllib_error.HTTPError, json.JSONDecodeError, TimeoutError) as exc:
        log(f"Ollama request failed ({url}): {exc}")
        return None


def ollama_model_available(host, model, timeout_ms):
    payload = ollama_request_json(host, "/api/tags", timeout_ms=timeout_ms)
    if not isinstance(payload, dict):
        return False
    models = payload.get("models") or []
    names = set()
    for entry in models:
        if isinstance(entry, dict) and entry.get("name"):
            names.add(str(entry["name"]))
    if model in names:
        return True
    # Accept untagged match if user passed "name:tag" and only "name" exists or vice-versa.
    model_base = model.split(":")[0]
    return any(name.split(":")[0] == model_base for name in names)


def build_forensic_rewrite_prompt(forensic_report, event, request_thinking=False):
    thinking_instruction = ""
    if request_thinking:
        thinking_instruction = (
            "- Before JSON, include a <thinking>...</thinking> block with concise human reasoning.\n"
            "- Keep the <thinking> block under 60 words.\n"
            "- After that block, output exactly one JSON object.\n"
        )
    return (
        "Rewrite the chess coaching text using ONLY provided facts.\n"
        "Output format:\n"
        "1) Optional <thinking>...</thinking> block.\n"
        "2) Exactly one JSON object with keys:\n"
        "cause_summary, human_thought_process, missed_cues, better_decision_process, practice_habit, lesson.\n"
        "Rules:\n"
        "- cause_summary must include concrete evidence from numbers.\n"
        "- The other five fields must be human over-the-board language.\n"
        "- Do NOT mention engines, stockfish, lc0, pv, eval, centipawn, best move, or top line in those five fields.\n"
        "- Keep text practical, specific, and understandable.\n\n"
        f"{thinking_instruction}"
        f"Facts:\n"
        f"Move: {event['prefix']} {event['san']} ({event['turn_label']})\n"
        f"Expected score: {event['before_score']:.2f} -> {event['after_score']:.2f} ({(event['after_score']-event['before_score'])*100:+.1f} pts)\n"
        f"Best move: {forensic_report['best_move_san']}\n"
        f"Stockfish loss: {cp_delta_to_text(forensic_report['sf_loss_cp'])}\n"
        f"Lc0 loss: {cp_delta_to_text(forensic_report['lc0_loss_cp'])}\n"
        f"Confidence: {forensic_report['confidence']}\n"
        f"SF PV: {forensic_report['sf_best_pv'] or 'n/a'}\n"
        f"Lc0 PV: {forensic_report['lc0_best_pv'] or 'n/a'}\n"
        f"Deterministic cause_summary: {forensic_report.get('cause_summary')}\n"
        f"Deterministic human_thought_process: {forensic_report.get('human_thought_process')}\n"
        f"Deterministic missed_cues: {forensic_report.get('missed_cues')}\n"
        f"Deterministic better_decision_process: {forensic_report.get('better_decision_process')}\n"
        f"Deterministic practice_habit: {forensic_report.get('practice_habit')}\n"
        f"Deterministic lesson: {forensic_report.get('lesson')}\n"
    )


def run_llama_cli_rewrite(prompt, llm_config):
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
        return None
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        log(f"llama rewrite non-zero exit ({proc.returncode}): {stderr[:160]}")
        return None
    return proc.stdout or ""


def run_ollama_rewrite(prompt, llm_config, chunk_hook=None):
    payload = {
        "model": llm_config["ollama_model"],
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": llm_config["ollama_max_tokens"],
            "temperature": llm_config["ollama_temperature"],
        },
    }

    host = normalize_ollama_host(llm_config["ollama_host"])
    url = f"{host}/api/generate"
    req = urllib_request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    timeout_ms = llm_config.get("ollama_timeout_ms")
    timeout_s = None
    if timeout_ms is not None:
        try:
            timeout_ms = int(timeout_ms)
        except (TypeError, ValueError):
            timeout_ms = DEFAULT_OLLAMA_TIMEOUT_MS
        if timeout_ms > 0:
            timeout_s = max(1, timeout_ms) / 1000.0

    thinking_parts = []
    response_parts = []
    try:
        if timeout_s is None:
            response_ctx = urllib_request.urlopen(req)
        else:
            response_ctx = urllib_request.urlopen(req, timeout=timeout_s)
        with response_ctx as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                thinking_chunk = str(item.get("thinking") or "")
                response_chunk = str(item.get("response") or "")

                if thinking_chunk:
                    thinking_parts.append(thinking_chunk)
                    if chunk_hook:
                        try:
                            chunk_hook("thinking", thinking_chunk)
                        except Exception:
                            pass
                if response_chunk:
                    response_parts.append(response_chunk)
                    if chunk_hook:
                        try:
                            chunk_hook("response", response_chunk)
                        except Exception:
                            pass

                if item.get("done"):
                    break
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError) as exc:
        log(f"Ollama request failed ({url}): {exc}")
        return None

    thinking = "".join(thinking_parts)
    response = "".join(response_parts)
    if not response and not thinking:
        return ""
    if thinking:
        return f"<thinking>\n{thinking}\n</thinking>\n{response}"
    return response


def extract_json_object(text):
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def parse_llm_coaching(raw_text):
    payload = extract_json_object(raw_text)
    if not isinstance(payload, dict):
        return None
    parsed = {}
    for key in COACHING_FIELDS:
        value = payload.get(key)
        if value is None:
            continue
        parsed[key] = normalize_whitespace(str(value))
    if "cause_summary" not in parsed and payload.get("cause"):
        parsed["cause_summary"] = normalize_whitespace(str(payload.get("cause")))
    return parsed if parsed.get("cause_summary") else None


def log_forensic_lesson_progress(event, idx, total):
    forensic = event.get("forensic")
    if not forensic:
        if event.get("forensic_error"):
            log(
                f"[forensic {idx}/{total}] lesson unavailable: "
                f"{event['prefix']} {event['san']} ({event['turn_label']}): {event['forensic_error']}"
            )
        return

    move_label = f"{event['prefix']} {event['san']} ({event['turn_label']})"
    cause_summary = forensic.get("cause_summary") or forensic.get("cause") or "n/a"
    lesson = forensic.get("lesson") or "n/a"
    thought = forensic.get("human_thought_process") or "n/a"
    habit = forensic.get("practice_habit") or "n/a"
    log(f"[forensic {idx}/{total}] cause: {move_label}: {cause_summary}")
    log(f"[forensic {idx}/{total}] lesson: {lesson}")
    log(f"[forensic {idx}/{total}] thought: {thought}")
    log(f"[forensic {idx}/{total}] habit: {habit}")


def maybe_llm_rewrite(forensic_report, event, llm_config, trace_hook=None):
    if not llm_config.get("enabled"):
        return forensic_report

    prompt = build_forensic_rewrite_prompt(
        forensic_report,
        event,
        request_thinking=bool(llm_config.get("request_thinking")),
    )
    backend = llm_config.get("backend")
    raw_output = None
    if backend == "ollama":
        raw_output = run_ollama_rewrite(
            prompt,
            llm_config,
            chunk_hook=(
                (lambda channel, text: trace_hook(event, backend or "unknown", {
                    "kind": "chunk",
                    "channel": channel,
                    "text": text,
                }))
                if trace_hook
                else None
            ),
        )
    elif backend == "llama-cli":
        raw_output = run_llama_cli_rewrite(prompt, llm_config)
    if not raw_output:
        return forensic_report
    if trace_hook:
        try:
            trace_hook(event, backend or "unknown", raw_output)
        except Exception:
            pass

    parsed = parse_llm_coaching(raw_output)
    if not parsed:
        return forensic_report

    updated = dict(forensic_report)
    for key, value in parsed.items():
        updated[key] = value
    updated = finalize_human_coaching_fields(updated)
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
    llm_trace_hook=None,
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

    coaching = detect_forensic_cause(
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
        sf_loss_cp=sf_loss_cp,
        lc0_loss_cp=lc0_loss_cp,
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
        "motif": coaching["motif"],
        "cause_summary": coaching["cause_summary"],
        "human_thought_process": coaching["human_thought_process"],
        "missed_cues": coaching["missed_cues"],
        "better_decision_process": coaching["better_decision_process"],
        "practice_habit": coaching["practice_habit"],
        "cause": coaching["cause_summary"],
        "lesson": coaching["lesson"],
        "llm_rewritten": False,
    }

    return maybe_llm_rewrite(
        finalize_human_coaching_fields(report),
        event,
        llm_config,
        trace_hook=llm_trace_hook,
    )

