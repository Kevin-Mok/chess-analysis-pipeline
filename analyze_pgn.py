#!/usr/bin/env python3
from pgn_analyzer.cli import run_cli
from pgn_analyzer.engine import UCIEngine
from pgn_analyzer.pipeline import main

__all__ = ["run_cli", "main", "UCIEngine"]


if __name__ == "__main__":
    run_cli()
