from __future__ import annotations

import os
import re
import sys
import time

import chess
import chess.pgn

from .common import (
    cp_delta_to_text,
    default_output_md_path,
    expected_score,
    format_row,
    format_wld,
    infer_swing_reason,
    is_critical_swing,
    log,
    normalize_whitespace,
    pct,
    resolve_executable,
    resolve_lc0_weights,
    resolve_pov,
    select_swing_events,
    should_track_swing,
    swing_polarity_label,
    swing_severity,
    to_pov,
)
from .constants import (
    DEFAULT_CAUSE_MODE,
    DEFAULT_FORENSIC_MAX_PV_PLIES,
    DEFAULT_FORENSIC_MULTIPV,
    DEFAULT_FORENSIC_TIME_MS,
    DEFAULT_HASH_MB,
    DEFAULT_LC0_CANDIDATES,
    DEFAULT_LLAMA_CLI_CANDIDATES,
    DEFAULT_LLAMA_MAX_TOKENS,
    DEFAULT_LLAMA_TEMP,
    DEFAULT_LLAMA_TIMEOUT_MS,
    DEFAULT_LLM_BACKEND,
    DEFAULT_LLM_LOG_RAW,
    DEFAULT_LLM_RAW_MAX_CHARS,
    DEFAULT_LLM_REQUEST_THINKING,
    DEFAULT_MAX_MS,
    DEFAULT_MAX_SECONDS,
    DEFAULT_MIN_MS,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MAX_TOKENS,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TEMP,
    DEFAULT_OLLAMA_TIMEOUT_MS,
    DEFAULT_POV_PLAYER,
    DEFAULT_SWING_MAX_EVENTS,
    DEFAULT_SWING_SCOPE,
    DEFAULT_SWING_THRESHOLD_SCORE,
    DEFAULT_THREADS,
    ENGINE,
)
from .engine import UCIEngine, approx_wdl_from_cp
from .forensic import (
    build_forensic_report,
    log_forensic_lesson_progress,
    normalize_ollama_host,
    ollama_model_available,
)

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
        f"scope={swing_scope}, max-events={swing_max_events}, cause-mode={cause_mode}, "
        "severity=Critical only",
        file=out,
        flush=True,
    )

    if swing_max_events <= 0:
        print("- Swing highlights disabled (`--swing-max-events 0`).", file=out, flush=True)
        return

    if not swing_events:
        print("- No critical swings met the configured threshold.", file=out, flush=True)
        return

    selected_events = select_swing_events(swing_events, swing_max_events)

    def render_event(event):
        delta_points = event["delta"] * 100.0
        sign = "+" if delta_points >= 0 else ""
        me_delta = delta_points
        op_delta = -delta_points
        before_wld = format_wld(*event["before_wld"])
        after_wld = format_wld(*event["after_wld"])
        print(
            (
                f"- [{event['severity']}] {event['prefix']} {event['san']} ({event['turn_label']}): "
                f"W/L/D {before_wld} -> {after_wld}, "
                f"eval {event['before_eval']} -> {event['after_eval']}, "
                f"expected score {event['before_score']:.2f} -> {event['after_score']:.2f} "
                f"({sign}{delta_points:.1f} pts)"
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
            print(f"  Cause: {forensic.get('cause_summary') or forensic.get('cause')}", file=out, flush=True)
            print(
                f"  What you likely thought: {forensic.get('human_thought_process') or 'n/a'}",
                file=out,
                flush=True,
            )
            print(
                f"  What you missed on the board: {forensic.get('missed_cues') or 'n/a'}",
                file=out,
                flush=True,
            )
            print(
                f"  How to decide better next time: {forensic.get('better_decision_process') or 'n/a'}",
                file=out,
                flush=True,
            )
            print(
                f"  Practice habit: {forensic.get('practice_habit') or 'n/a'}",
                file=out,
                flush=True,
            )
            print(f"  Lesson: {forensic['lesson']}", file=out, flush=True)
        else:
            if event.get("forensic_error"):
                print(
                    f"  Cause: forensic analysis failed ({event['forensic_error']}). Falling back to heuristic.",
                    file=out,
                    flush=True,
                )
            print(f"  Cause: {event['reason']}", file=out, flush=True)

    for index, event in enumerate(selected_events):
        print("", file=out, flush=True)
        render_event(event)
        if index < len(selected_events) - 1:
            print("", file=out, flush=True)


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
    llm_backend=DEFAULT_LLM_BACKEND,
    ollama_host=DEFAULT_OLLAMA_HOST,
    ollama_model=DEFAULT_OLLAMA_MODEL,
    ollama_timeout_ms=DEFAULT_OLLAMA_TIMEOUT_MS,
    ollama_max_tokens=DEFAULT_OLLAMA_MAX_TOKENS,
    ollama_temperature=DEFAULT_OLLAMA_TEMP,
    llm_log_raw=DEFAULT_LLM_LOG_RAW,
    llm_raw_max_chars=DEFAULT_LLM_RAW_MAX_CHARS,
    llm_request_thinking=DEFAULT_LLM_REQUEST_THINKING,
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
        llm_backend = normalize_whitespace(llm_backend).lower() or DEFAULT_LLM_BACKEND
        if llm_backend not in ("auto", "ollama", "llama-cli"):
            llm_backend = DEFAULT_LLM_BACKEND
        ollama_host = normalize_ollama_host(ollama_host)
        ollama_model = normalize_whitespace(ollama_model) or DEFAULT_OLLAMA_MODEL
        try:
            ollama_timeout_ms = int(ollama_timeout_ms)
        except (TypeError, ValueError):
            ollama_timeout_ms = DEFAULT_OLLAMA_TIMEOUT_MS
        # 0 means unlimited timeout for slow local models.
        if ollama_timeout_ms < 0:
            ollama_timeout_ms = DEFAULT_OLLAMA_TIMEOUT_MS
        elif ollama_timeout_ms > 0:
            ollama_timeout_ms = max(1000, ollama_timeout_ms)
        ollama_max_tokens = max(96, int(ollama_max_tokens))
        ollama_temperature = float(ollama_temperature)
        llm_log_raw = bool(llm_log_raw)
        try:
            llm_raw_max_chars = int(llm_raw_max_chars)
        except (TypeError, ValueError):
            llm_raw_max_chars = DEFAULT_LLM_RAW_MAX_CHARS
        # 0 means unlimited raw log length.
        if llm_raw_max_chars <= 0:
            llm_raw_max_chars = None
        else:
            llm_raw_max_chars = max(2000, llm_raw_max_chars)
        llm_request_thinking = bool(llm_request_thinking)

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

        # Write metadata first; swing summary is rendered above the move table after analysis.
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

        board = game.board()
        ply = 0
        previous_scored_ply = None
        swing_events = []
        table_rows = []
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
                    "wld": (w, l, d),
                }
                if previous_scored_ply is not None:
                    delta = score - previous_scored_ply["score"]
                    abs_delta = abs(delta)
                    if (
                        abs_delta >= swing_threshold_score
                        and is_critical_swing(abs_delta)
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
                                "before_wld": previous_scored_ply["wld"],
                                "after_wld": (w, l, d),
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

            table_rows.append(format_row(prefix, turn_label, san, w, l, d, eval_str))
            elapsed = time.perf_counter() - start
            log(
                f"[{ply}/{total_plies}] {prefix} {san}: eval={eval_str}, W/D/L={w}/{d}/{l}, "
                f"movetime_ms={movetime_ms}, elapsed={elapsed:.1f}s"
            )

        if cause_mode in ("forensic", "forensic-llm") and swing_events and swing_max_events > 0:
            llm_bin = resolve_executable(llama_cli_path, DEFAULT_LLAMA_CLI_CANDIDATES)
            llm_model_path = os.path.abspath(os.path.expanduser(llama_model)) if llama_model else None
            llama_cli_enabled = (
                cause_mode == "forensic-llm"
                and llm_bin is not None
                and llm_model_path is not None
                and os.path.isfile(llm_model_path)
            )
            ollama_enabled = False
            if cause_mode == "forensic-llm" and llm_backend in ("auto", "ollama"):
                probe_timeout_ms = 3000 if ollama_timeout_ms <= 0 else min(3000, ollama_timeout_ms)
                ollama_enabled = ollama_model_available(
                    ollama_host,
                    ollama_model,
                    timeout_ms=probe_timeout_ms,
                )

            selected_backend = None
            if cause_mode == "forensic-llm":
                if llm_backend == "ollama":
                    selected_backend = "ollama" if ollama_enabled else None
                elif llm_backend == "llama-cli":
                    selected_backend = "llama-cli" if llama_cli_enabled else None
                else:  # auto
                    if ollama_enabled:
                        selected_backend = "ollama"
                    elif llama_cli_enabled:
                        selected_backend = "llama-cli"
            llm_enabled = selected_backend is not None
            if cause_mode == "forensic-llm" and not llm_enabled:
                log(
                    "forensic-llm requested but no rewrite runtime is available; "
                    "using deterministic forensic descriptions."
                )

            llm_config = {
                "enabled": llm_enabled,
                "backend": selected_backend,
                "llm_backend_requested": llm_backend,
                "ollama_host": ollama_host,
                "ollama_model": ollama_model,
                "ollama_timeout_ms": ollama_timeout_ms,
                "ollama_max_tokens": ollama_max_tokens,
                "ollama_temperature": ollama_temperature,
                "log_raw": llm_log_raw,
                "raw_max_chars": llm_raw_max_chars,
                "request_thinking": llm_request_thinking,
                "llama_cli_path": llm_bin,
                "llama_model": llm_model_path,
                "llama_timeout_ms": max(1000, int(llama_timeout_ms)),
                "llama_max_tokens": max(64, int(llama_max_tokens)),
                "llama_temperature": float(llama_temperature),
            }

            llm_streamed_thinking = set()

            def llm_trace_hook(event, backend, raw_output):
                if not llm_log_raw:
                    return
                move_label = f"{event['prefix']} {event['san']} ({event['turn_label']})"
                stream_key = (event.get("ply"), backend, move_label)

                if isinstance(raw_output, dict) and raw_output.get("kind") == "chunk":
                    if raw_output.get("channel") != "thinking":
                        return
                    chunk_text = str(raw_output.get("text") or "").replace("\r", "")
                    if stream_key not in llm_streamed_thinking:
                        llm_streamed_thinking.add(stream_key)
                        log(f"[llm thinking] {backend} {move_label} BEGIN")
                    if chunk_text:
                        for line in chunk_text.split("\n"):
                            if line:
                                log(f"[llm thinking] {line}")
                    return

                streamed_thinking = stream_key in llm_streamed_thinking
                if streamed_thinking:
                    log(f"[llm thinking] {backend} {move_label} END")
                    llm_streamed_thinking.discard(stream_key)

                text = (raw_output or "").replace("\r", "")
                truncated = False
                if llm_raw_max_chars is not None and len(text) > llm_raw_max_chars:
                    text = text[:llm_raw_max_chars]
                    truncated = True

                if (not streamed_thinking) and "<thinking>" in text.lower() and "</thinking>" in text.lower():
                    thinking_match = re.search(
                        r"<thinking>\s*(.*?)\s*</thinking>",
                        text,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if thinking_match:
                        thinking_text = thinking_match.group(1).strip()
                        log(f"[llm thinking] {backend} {move_label} BEGIN")
                        if thinking_text:
                            for line in thinking_text.splitlines():
                                log(f"[llm thinking] {line}")
                        else:
                            log("[llm thinking] (empty)")
                        log(f"[llm thinking] {backend} {move_label} END")

                log(f"[llm raw] {backend} {move_label} BEGIN")
                log("```text")
                if text.strip():
                    for line in text.rstrip("\n").split("\n"):
                        log(line)
                else:
                    log("(empty)")
                if truncated:
                    log(f"... [truncated to {llm_raw_max_chars} chars]")
                log("```")
                log(f"[llm raw] {backend} {move_label} END")

            target_events = select_swing_events(swing_events, swing_max_events)
            phase_start = time.perf_counter()
            log(
                f"Starting forensic phase: events={len(target_events)}/{len(swing_events)}, "
                f"forensic_time_ms={forensic_time_ms}, multipv={forensic_multipv}, "
                f"llm_enabled={llm_enabled}, llm_backend={selected_backend or 'deterministic'}"
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
                            llm_trace_hook=llm_trace_hook,
                        )
                        event_elapsed = time.perf_counter() - event_start
                        log(
                            f"[forensic {idx}/{len(target_events)}] done {event['prefix']} {event['san']} "
                            f"in {event_elapsed:.1f}s"
                        )
                        log_forensic_lesson_progress(event, idx, len(target_events))
                    except Exception as exc:
                        event["forensic_error"] = str(exc)
                        log(f"forensic analysis failed at {event['prefix']} {event['san']}: {exc}")
                        log_forensic_lesson_progress(event, idx, len(target_events))
            finally:
                lc0_forensic.quit()
                sf_forensic.quit()
                phase_elapsed = time.perf_counter() - phase_start
                log(f"Completed forensic phase in {phase_elapsed:.1f}s.")

        render_significant_swings(
            out,
            swing_events,
            swing_threshold_score=swing_threshold_score,
            swing_scope=swing_scope,
            swing_max_events=swing_max_events,
            cause_mode=cause_mode,
        )
        print("", file=out, flush=True)
        header = format_row("Ply", "Turn", "Move", "Win%", "Loss%", "Draw%", "Eval")
        print("```text", file=out, flush=True)
        print(header, file=out, flush=True)
        print("-" * len(header), file=out, flush=True)
        for row in table_rows:
            print(row, file=out, flush=True)
        print("```", file=out, flush=True)
        log(
            f"Detected {len(swing_events)} critical swings at threshold "
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
