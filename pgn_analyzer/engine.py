from __future__ import annotations

import math
import queue
import subprocess
import threading
import time

from .common import log

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
        lowered_name = (name or "").lower()
        self._is_lc0 = "lc0" in lowered_name or "leela" in lowered_name
        self._current_multipv = None
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

    def _ready_timeout_s(self, requested_multipv=1, hard_timeout_ms=None, during_init=False):
        timeout_s = 6.0
        if hard_timeout_ms is not None:
            timeout_s = max(timeout_s, (hard_timeout_ms / 1000.0) + 1.0)
        if during_init:
            timeout_s = max(timeout_s, 12.0)
        if self._is_lc0:
            # Lc0 can take longer to acknowledge option changes, especially at higher MultiPV.
            lc0_floor = 12.0 if requested_multipv <= 1 else 16.0 + max(0, requested_multipv - 2) * 2.0
            if during_init:
                lc0_floor = max(lc0_floor, 18.0)
            timeout_s = max(timeout_s, lc0_floor)
        return timeout_s

    def _sync_ready(self, timeout_s, retries=0):
        timeout_s = max(1.0, float(timeout_s))
        attempts = max(0, int(retries)) + 1
        for attempt in range(1, attempts + 1):
            self._send("isready")
            try:
                self._wait_for("readyok", timeout_s)
                return
            except TimeoutError:
                if attempt >= attempts:
                    raise
                timeout_s += max(4.0, timeout_s * 0.5)
                log(
                    f"{self.name}: isready retry {attempt}/{attempts - 1} "
                    f"after ready timeout; new timeout={timeout_s:.1f}s"
                )

    def _effective_hard_timeout_ms(self, movetime_ms, hard_timeout_ms, requested_multipv=1):
        timeout_ms = max(1000, int(hard_timeout_ms))
        if self._is_lc0:
            requested_multipv = max(1, int(requested_multipv))
            # Give neural MultiPV searches extra time to emit bestmove.
            lc0_floor_ms = int(movetime_ms) * (requested_multipv + 4) + 2500
            timeout_ms = max(timeout_ms, lc0_floor_ms)
        return timeout_ms

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
        ready_retries = 1 if self._is_lc0 else 0
        self._sync_ready(self._ready_timeout_s(during_init=True), retries=ready_retries)

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
        if self._current_multipv != requested_multipv:
            self._set_option("MultiPV", requested_multipv)
            ready_retries = 1 if self._is_lc0 else 0
            self._sync_ready(
                self._ready_timeout_s(
                    requested_multipv=requested_multipv,
                    hard_timeout_ms=hard_timeout_ms,
                ),
                retries=ready_retries,
            )
            self._current_multipv = requested_multipv

        self._send(f"go movetime {max(1, int(movetime_ms))}")

        best_by_mpv = {}
        bestmove = None
        cp = None
        mate = None
        wdl = None

        effective_hard_timeout_ms = self._effective_hard_timeout_ms(
            movetime_ms=movetime_ms,
            hard_timeout_ms=hard_timeout_ms,
            requested_multipv=requested_multipv,
        )
        deadline = time.monotonic() + (effective_hard_timeout_ms / 1000.0)
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
