"""
suites/pp_auto/sync_specs.py - Central Registry (GAS Web App) Specification & Dataset Synchronization Engine.
"""

import os
import sys
import json
import base64
import logging
import requests
from typing import Dict, Any, List, Optional

# Ensure UTF-8 console output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logger = logging.getLogger("Model_Arbiter.pp_auto.sync")

DEFAULT_REGISTRY_URL = "https://script.google.com/macros/s/AKfycbyAS6ERYNd8Zc-TudDBpkD5IrPVuRbJu7buPsfYwIE_PscYRAEjDwL5AbqtWOa7xiwA/exec"


def sync_registry_specs(registry_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches the latest environment fingerprints, prompt, generation config, and real test dataset
    from the Central Registry (GAS Web App).

    1. Updates suites/pp_auto/prompt.txt with remote system_prompt.
    2. Updates suites/pp_auto/manifest.json with temperature, top_p, and thinking_budget.
    3. Restores image files (e.g. ddd93a4b.jpg) to suites/pp_auto/images/ from base64 data.
    4. Produces corresponding ground truth dataset in suites/pp_auto/test_cases.json.
    """
    url = (
        registry_url
        or os.environ.get("ARBITER_REGISTRY_WEBAPP_URL")
        or os.environ.get("REGISTRY_URL")
        or DEFAULT_REGISTRY_URL
    )

    logger.info(f"[Registry Sync] Calling GAS Web App endpoint: {url}")

    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[Registry Sync] Failed to fetch data from GAS Web App: {e}")
        raise RuntimeError(f"Registry endpoint call failed: {e}")

    if not isinstance(data, dict) or data.get("status") != "success":
        raise ValueError(f"Invalid Registry response status: {data}")

    suites = data.get("suites", {})
    pp_config = suites.get("pp_auto")

    if not pp_config:
        # Check if suites dictionary itself contains pp_auto or if top-level data has pp_auto
        if "suite_name" in data and data.get("suite_name") == "pp_auto":
            pp_config = data
        else:
            raise ValueError("Suite 'pp_auto' not found in Central Registry response.")

    if not pp_config.get("is_active", True):
        logger.warning("Suite 'pp_auto' is marked as is_active: false in Registry.")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(current_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # 1. Update system prompt in prompt.txt
    system_prompt = pp_config.get("system_prompt")
    prompt_file_path = os.path.join(current_dir, "prompt.txt")
    if system_prompt:
        with open(prompt_file_path, "w", encoding="utf-8") as f:
            f.write(system_prompt.strip() + "\n")
        logger.info(f"[Registry Sync] Updated prompt.txt ({len(system_prompt)} chars).")

    # 2. Update manifest.json
    manifest_path = os.path.join(current_dir, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    inf_cfg = manifest.setdefault("inference_config", {})
    if "temperature" in pp_config and pp_config["temperature"] is not None:
        inf_cfg["temperature"] = float(pp_config["temperature"])
    if "top_p" in pp_config and pp_config["top_p"] is not None:
        inf_cfg["top_p"] = float(pp_config["top_p"])
    if "response_mime_type" in pp_config and pp_config["response_mime_type"]:
        inf_cfg["response_mime_type"] = pp_config["response_mime_type"]

    thinking_budget = pp_config.get("thinking_budget", 1024)
    thinking_cfg = inf_cfg.setdefault("thinking_config", {})
    thinking_cfg["thinking_budget"] = int(thinking_budget)

    manifest["suite_name"] = "pp_auto"
    manifest["version"] = manifest.get("version", "1.0.0")
    manifest["description"] = "中央 Registry 同步之國際護照辨識與 MRZ 思考校驗套件"
    manifest["prompt_file"] = "prompt.txt"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"[Registry Sync] Updated manifest.json with thinking_budget={thinking_budget}.")

    # 3. Parse test cases & images
    raw_test_cases = pp_config.get("test_cases")
    if not raw_test_cases and pp_config.get("test_cases_json"):
        tc_val = pp_config["test_cases_json"]
        if isinstance(tc_val, str):
            try:
                raw_test_cases = json.loads(tc_val)
            except Exception:
                raw_test_cases = []
        elif isinstance(tc_val, list):
            raw_test_cases = tc_val

    # If test_cases array is absent/empty, construct single sample from image_base64 + ground_truth_json / ground_truth
    if not raw_test_cases and pp_config.get("image_base64"):
        gt_raw = pp_config.get("ground_truth_json") or pp_config.get("ground_truth") or {}
        if isinstance(gt_raw, str):
            try:
                gt_raw = json.loads(gt_raw)
            except Exception:
                gt_raw = {}
        
        case_id = gt_raw.get("case_id") or gt_raw.get("id") or "ddd93a4b"
        raw_test_cases = [{
            "case_id": case_id,
            "image_filename": f"{case_id}.jpg",
            "image_base64": pp_config.get("image_base64"),
            "ground_truth": gt_raw
        }]

    parsed_test_cases = []
    synced_filenames = []

    if raw_test_cases:
        for idx, tc in enumerate(raw_test_cases):
            case_id = tc.get("case_id") or tc.get("id") or f"SAMPLE_{idx+1:03d}"
            img_filename = tc.get("image_filename") or f"{case_id}.jpg"
            img_b64 = tc.get("image_base64") or pp_config.get("image_base64")

            if img_b64:
                try:
                    img_bytes = base64.b64decode(img_b64)
                    img_out_path = os.path.join(images_dir, img_filename)
                    with open(img_out_path, "wb") as f:
                        f.write(img_bytes)
                    synced_filenames.append(img_filename)
                    logger.info(f"[Registry Sync] Restored image: {img_filename} ({len(img_bytes)} bytes)")
                except Exception as e:
                    logger.warning(f"[Registry Sync] Image decode failed for {case_id}: {e}")

            gt = tc.get("ground_truth") or tc.get("expected_ground_truth") or {}
            if isinstance(gt, str):
                try:
                    gt = json.loads(gt)
                except Exception:
                    gt = {}

            # Build normalized ground truth schema for Model_Arbiter harness evaluation
            expected_gt = {}

            full_name = gt.get("full_name_en")
            if not full_name:
                last = gt.get("surname") or gt.get("last_name_en") or gt.get("ln") or ""
                first = gt.get("given_names") or gt.get("first_name_en") or gt.get("fn") or ""
                full_name = f"{last} {first}".strip()

            expected_gt["full_name_en"] = full_name
            expected_gt["passport_number"] = gt.get("passport_number") or gt.get("passport_no") or gt.get("pno") or ""
            expected_gt["nationality"] = gt.get("nationality") or gt.get("nat") or ""

            raw_mrz = gt.get("raw") or {}
            m1 = gt.get("mrz_line1") or gt.get("mrz_line_1") or gt.get("m1") or raw_mrz.get("mrz_line_1") or ""
            m2 = gt.get("mrz_line2") or gt.get("mrz_line_2") or gt.get("m2") or raw_mrz.get("mrz_line_2") or ""

            if m1:
                expected_gt["mrz_line1"] = m1
            if m2:
                expected_gt["mrz_line2"] = m2

            parsed_test_cases.append({
                "id": case_id,
                "description": f"中央 Registry 真實驗收樣張 ({case_id})",
                "image_filename": img_filename,
                "image_mock_data": gt,
                "expected_ground_truth": expected_gt
            })

    if parsed_test_cases:
        test_cases_path = os.path.join(current_dir, "test_cases.json")
        with open(test_cases_path, "w", encoding="utf-8") as f:
            json.dump(parsed_test_cases, f, indent=2, ensure_ascii=False)
        logger.info(f"[Registry Sync] Updated test_cases.json with {len(parsed_test_cases)} case(s).")

    summary = {
        "status": "success",
        "synced_cases": len(parsed_test_cases),
        "case_ids": [c["id"] for c in parsed_test_cases],
        "synced_images": synced_filenames,
        "temperature": inf_cfg.get("temperature"),
        "top_p": inf_cfg.get("top_p"),
        "thinking_budget": thinking_budget,
        "updated_at": pp_config.get("updated_at")
    }

    print(f"[REGISTRY SYNC COMPLETE] Synced {len(parsed_test_cases)} test case(s) from Central Registry.")
    for cid in summary["case_ids"]:
        print(f"   > Case ID: {cid}")
    print(f"   > Restored Images : {', '.join(synced_filenames)}")
    print(f"   > Thinking Budget : {thinking_budget}")

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_registry_specs()
