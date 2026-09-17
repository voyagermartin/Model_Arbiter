"""core/evaluator.py - Model benchmark evaluation engine & automated recommendation system."""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from core.pricer import calculate_cost_ntd, get_model_pricing
from core.discovery import list_candidate_models
from suites.pp_auto.harness import load_test_cases, execute_test_case

logger = logging.getLogger("Model_Arbiter.evaluator")


def run_suite_evaluation(
    suite_name: str = "pp_auto",
    api_key: Optional[str] = None,
    candidate_models: Optional[List[str]] = None,
    mock: bool = False,
    image_bytes: Optional[bytes] = None
) -> List[Dict[str, Any]]:
    """
    Executes benchmark test suite across all active candidate models.
    """
    if suite_name != "pp_auto":
        raise ValueError(f"Unsupported benchmark suite: {suite_name}")

    test_cases = load_test_cases()
    if not candidate_models:
        discovered = list_candidate_models(api_key=api_key)
        candidate_models = [m["name"] for m in discovered if not m.get("deprecated")]

    suite_results = []

    for model_name in candidate_models:
        total_cases = len(test_cases)
        passed_cases = 0
        total_prompt_tokens = 0
        total_candidate_tokens = 0
        total_thought_tokens = 0
        total_latency = 0.0
        case_details = []

        for case in test_cases:
            res = execute_test_case(
                model_name=model_name,
                test_case=case,
                api_key=api_key,
                mock=mock,
                image_bytes=image_bytes
            )
            if res["passed"]:
                passed_cases += 1
            total_prompt_tokens += res["prompt_tokens"]
            total_candidate_tokens += res["candidate_tokens"]
            total_thought_tokens += res["thought_tokens"]
            total_latency += res["latency_sec"]
            case_details.append(res)

        pass_rate = round((passed_cases / total_cases) * 100.0, 2) if total_cases > 0 else 0.0
        avg_latency = round(total_latency / total_cases, 3) if total_cases > 0 else 0.0

        cost_ntd = calculate_cost_ntd(
            model_name=model_name,
            prompt_tokens=total_prompt_tokens,
            candidate_tokens=total_candidate_tokens,
            thought_tokens=total_thought_tokens
        )

        suite_results.append({
            "model_name": model_name,
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "pass_rate": pass_rate,
            "avg_latency_sec": avg_latency,
            "prompt_tokens": total_prompt_tokens,
            "candidate_tokens": total_candidate_tokens,
            "thought_tokens": total_thought_tokens,
            "total_tokens": total_prompt_tokens + total_candidate_tokens + total_thought_tokens,
            "cost_ntd": cost_ntd,
            "case_details": case_details
        })

    return suite_results


def print_leaderboard(suite_name: str, results: List[Dict[str, Any]]) -> None:
    """Prints ASCII ladder board / leaderboard comparison table."""
    headers = [
        "Rank", "Model Name", "Pass Rate (%)", "Avg Latency (s)",
        "Prompt Tokens", "Thought Tokens", "Output Tokens", "Cost (TWD)"
    ]

    sorted_results = sorted(results, key=lambda x: (-x["pass_rate"], x["cost_ntd"], x["avg_latency_sec"]))

    table_data = []
    for rank, r in enumerate(sorted_results, 1):
        status_flag = "* " if rank == 1 and r["pass_rate"] == 100.0 else "  "
        table_data.append([
            f"{status_flag}{rank}",
            r["model_name"],
            f"{r['pass_rate']:.1f}%",
            f"{r['avg_latency_sec']:.3f}",
            r["prompt_tokens"],
            r["thought_tokens"],
            r["candidate_tokens"],
            f"NT${r['cost_ntd']:.6f}"
        ])

    print("\n" + "=" * 90)
    print(f"MODEL ARBITER BENCHMARK LEADERBOARD -- SUITE: [{suite_name.upper()}]")
    print("=" * 90)

    if HAS_TABULATE:
        print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    else:
        header_line = " | ".join(f"{h:<14}" for h in headers)
        print(header_line)
        print("-" * len(header_line))
        for row in table_data:
            print(" | ".join(f"{str(item):<14}" for item in row))

    print("=" * 90 + "\n")


def recommend_and_export_active_model(
    suite_name: str,
    results: List[Dict[str, Any]],
    output_dir: str = "active_configs"
) -> Optional[Dict[str, Any]]:
    """
    Selects optimal model (100% pass rate & minimum TWD cost) and exports to active_configs/<suite_name>_model.json.
    """
    eligible = [r for r in results if r["pass_rate"] == 100.0]

    if not eligible:
        logger.warning(f"No model achieved 100% pass rate in suite '{suite_name}'. Skipping active config update.")
        return None

    best_model = min(eligible, key=lambda x: (x["cost_ntd"], x["avg_latency_sec"]))
    model_name = best_model["model_name"]
    pricing = get_model_pricing(model_name)

    avg_prompt = best_model["prompt_tokens"] / best_model["total_cases"]
    avg_candidate = best_model["candidate_tokens"] / best_model["total_cases"]
    avg_thought = best_model["thought_tokens"] / best_model["total_cases"]

    cost_per_1k_ntd = calculate_cost_ntd(
        model_name=model_name,
        prompt_tokens=int(avg_prompt * 1000),
        candidate_tokens=int(avg_candidate * 1000),
        thought_tokens=int(avg_thought * 1000)
    )

    recommendation = {
        "suite": suite_name,
        "recommended_model": model_name,
        "pass_rate": best_model["pass_rate"],
        "avg_latency_sec": best_model["avg_latency_sec"],
        "estimated_cost_ntd_per_1000_req": round(cost_per_1k_ntd, 4),
        "pricing_rule_usd_per_1m": pricing,
        "evaluated_at": datetime.now().isoformat()
    }

    os.makedirs(output_dir, exist_ok=True)
    target_file = os.path.join(output_dir, f"{suite_name}_model.json")
    
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(recommendation, f, indent=2, ensure_ascii=False)

    print(f"[AUTO RECOMMENDER] Optimal active model exported to: {target_file}")
    print(f"   > Selected Model : {model_name}")
    print(f"   > Pass Rate      : {best_model['pass_rate']}%")
    print(f"   > Est. Cost/1k   : NT${cost_per_1k_ntd:.4f}\n")

    return recommendation
