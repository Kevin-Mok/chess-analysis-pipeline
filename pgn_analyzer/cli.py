from __future__ import annotations

import argparse

from .constants import (
    CRITICAL_SWING_THRESHOLD_SCORE,
    DEFAULT_CAUSE_MODE,
    DEFAULT_FORENSIC_MAX_PV_PLIES,
    DEFAULT_FORENSIC_MULTIPV,
    DEFAULT_FORENSIC_TIME_MS,
    DEFAULT_HASH_MB,
    DEFAULT_LLAMA_MAX_TOKENS,
    DEFAULT_LLAMA_TEMP,
    DEFAULT_LLAMA_TIMEOUT_MS,
    DEFAULT_LLM_BACKEND,
    DEFAULT_LLM_RAW_MAX_CHARS,
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
)
from .pipeline import main as analysis_main


def run_cli(argv=None):
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
                "Critical swing threshold in expected-score units (0.20 = 20 pts); "
                f"effective minimum is {CRITICAL_SWING_THRESHOLD_SCORE:.2f}; "
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
                f"or forensic-llm (forensic + optional local rewrite); default: {DEFAULT_CAUSE_MODE}"
            ),
        )
        parser.add_argument(
            "--llm-backend",
            type=str,
            choices=("auto", "ollama", "llama-cli"),
            default=DEFAULT_LLM_BACKEND,
            help=(
                "Rewrite backend for forensic-llm mode: auto (prefer Ollama), "
                f"ollama, or llama-cli (default: {DEFAULT_LLM_BACKEND})"
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
            "--ollama-host",
            type=str,
            default=DEFAULT_OLLAMA_HOST,
            help=f"Ollama host URL for forensic-llm rewrite (default: {DEFAULT_OLLAMA_HOST})",
        )
        parser.add_argument(
            "--ollama-model",
            type=str,
            default=DEFAULT_OLLAMA_MODEL,
            help=f"Ollama model tag for forensic-llm rewrite (default: {DEFAULT_OLLAMA_MODEL})",
        )
        parser.add_argument(
            "--ollama-timeout-ms",
            type=int,
            default=DEFAULT_OLLAMA_TIMEOUT_MS,
            help=(
                "Timeout for each Ollama rewrite call in ms "
                f"(default: {DEFAULT_OLLAMA_TIMEOUT_MS}; use 0 for unlimited)"
            ),
        )
        parser.add_argument(
            "--ollama-max-tokens",
            type=int,
            default=DEFAULT_OLLAMA_MAX_TOKENS,
            help=f"Max tokens for each Ollama rewrite (default: {DEFAULT_OLLAMA_MAX_TOKENS})",
        )
        parser.add_argument(
            "--ollama-temperature",
            type=float,
            default=DEFAULT_OLLAMA_TEMP,
            help=f"Sampling temperature for Ollama rewrite (default: {DEFAULT_OLLAMA_TEMP})",
        )
        parser.add_argument(
            "--llm-log-raw",
            action="store_true",
            help=(
                "Log raw forensic-llm model output (including optional reasoning text) to stderr "
                "for progress capture."
            ),
        )
        parser.add_argument(
            "--llm-raw-max-chars",
            type=int,
            default=DEFAULT_LLM_RAW_MAX_CHARS,
            help=(
                "Max chars to log from each raw forensic-llm response when --llm-log-raw is enabled "
                f"(default: {DEFAULT_LLM_RAW_MAX_CHARS}; use 0 for unlimited)"
            ),
        )
        parser.add_argument(
            "--llm-request-thinking",
            action="store_true",
            help=(
                "Ask forensic-llm rewrites to include a <thinking> block before JSON; "
                "use with --llm-log-raw to stream it to progress logs."
            ),
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
        args = parser.parse_args(argv)
        analysis_main(
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
            llm_backend=args.llm_backend,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model,
            ollama_timeout_ms=args.ollama_timeout_ms,
            ollama_max_tokens=args.ollama_max_tokens,
            ollama_temperature=args.ollama_temperature,
            llm_log_raw=args.llm_log_raw,
            llm_raw_max_chars=args.llm_raw_max_chars,
            llm_request_thinking=args.llm_request_thinking,
            llama_cli_path=args.llama_cli_path,
            llama_model=args.llama_model,
            llama_timeout_ms=args.llama_timeout_ms,
            llama_max_tokens=args.llama_max_tokens,
            llama_temperature=args.llama_temperature,
            output_md=args.output_md,
        )
