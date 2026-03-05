from __future__ import annotations

import os
import re

import chess

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
DEFAULT_SWING_SCOPE = "pov"
CRITICAL_SWING_THRESHOLD_SCORE = 0.50
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
DEFAULT_LLM_BACKEND = "auto"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:14b"
DEFAULT_OLLAMA_TIMEOUT_MS = 6000
DEFAULT_OLLAMA_MAX_TOKENS = 220
DEFAULT_OLLAMA_TEMP = 0.2
DEFAULT_LLM_LOG_RAW = False
DEFAULT_LLM_RAW_MAX_CHARS = 24000
DEFAULT_LLM_REQUEST_THINKING = False
COACHING_FIELDS = (
    "cause_summary",
    "human_thought_process",
    "missed_cues",
    "better_decision_process",
    "practice_habit",
    "lesson",
)
MAX_CAUSE_CHARS = 420
MAX_COACHING_CHARS = 700
LIVE_TABLE_SNAPSHOT_INTERVAL_PLIES = 8
LESSON_BANNED_RE = re.compile(
    r"\b(engine|stockfish|lc0|pv|eval|centipawn|best move|top line)\b",
    re.IGNORECASE,
)
MATERIAL_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}
