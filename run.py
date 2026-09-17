#!/usr/bin/env python3
"""
Model_Arbiter - Google Gemini Automatic Benchmark, Cost Precision & Model Recommendation Engine.
Main CLI Entrypoint.
"""

import sys
import os
import argparse
import logging

# Ensure UTF-8 output encoding on Windows consoles (e.g. CP950 / CP437)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from core.discovery import list_candidate_models
from core.evaluator import run_suite_evaluation, print_leaderboard, recommend_and_export_active_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Model_Arbiter.cli")


def handle_list_models(api_key: str = None) -> None:
    """Lists available Gemini candidate models in tabular format."""
    models = list_candidate_models(api_key=api_key)
    
    headers = ["Model ID", "Display Name", "Status", "Multimodal", "Thinking Tokens", "Description"]
    table_data = []
    for m in models:
        dep_str = "[DEPRECATED]" if m.get("deprecated") else "[ACTIVE]"
        multi_str = "YES" if m.get("multimodal") else "NO"
        think_str = "YES" if m.get("supports_thinking") else "NO"
        table_data.append([
            m["name"],
            m.get("display_name", m["name"]),
            dep_str,
            multi_str,
            think_str,
            m.get("description", "")[:60]
        ])

    print("\n" + "=" * 80)
    print("MODEL ARBITER -- GOOGLE GEMINI CANDIDATE MODEL CATALOG")
    print("=" * 80)
    
    if HAS_TABULATE:
        print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    else:
        header_line = " | ".join(f"{h:<16}" for h in headers)
        print(header_line)
        print("-" * len(header_line))
        for row in table_data:
            print(" | ".join(f"{str(item):<16}" for item in row))

    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Model_Arbiter: Google Gemini Model Benchmark, Cost Precision & Auto Recommendation Engine",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List all active multimodal Gemini models available for benchmarking."
    )

    parser.add_argument(
        "--suite",
        type=str,
        choices=["pp_auto"],
        help="Execute a benchmark suite (e.g., 'pp_auto' for Passport OCR verification)."
    )

    parser.add_argument(
        "--models",
        nargs="+",
        help="Specify particular model IDs to benchmark (e.g. --models gemini-2.0-flash gemini-2.0-flash-lite)."
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="Google Gemini API Key (defaults to GEMINI_API_KEY environment variable)."
    )

    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run benchmark suite using mock test harness (useful for offline verification)."
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    if args.list_models:
        handle_list_models(api_key=args.api_key)

    if args.suite:
        print(f"\n[+] Launching Model Arbiter Benchmark Suite: [{args.suite.upper()}]...")
        results = run_suite_evaluation(
            suite_name=args.suite,
            api_key=args.api_key,
            candidate_models=args.models,
            mock=args.mock
        )

        print_leaderboard(suite_name=args.suite, results=results)
        recommend_and_export_active_model(suite_name=args.suite, results=results)


if __name__ == "__main__":
    main()
