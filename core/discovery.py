"""
core/discovery.py - Google Gemini Model Dynamic Discovery, Pre-flight Probe & EOL Lifecycle Radar.
"""

import os
import re
import sys
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("Model_Arbiter.discovery")

REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_registry.json")
CACHE_TTL_SECONDS = 86400  # 24 hour cache TTL

KNOWN_BASELINE_MODELS = {
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
}

# Static fallback candidate catalog
DEFAULT_MODELS = [
    {
        "name": "gemini-3.8-flash",
        "display_name": "Gemini 3.8 Flash",
        "status": "NEW_DISCOVERED",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": True,
        "suggested_replacement": None,
        "description": "Official flagship fast multimodal reasoning model with extended thinking."
    },
    {
        "name": "gemini-3.5-flash",
        "display_name": "Gemini 3.5 Flash",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": True,
        "suggested_replacement": None,
        "description": "High performance multimodal reasoning model."
    },
    {
        "name": "gemini-3.5-flash-lite",
        "display_name": "Gemini 3.5 Flash Lite",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": True,
        "suggested_replacement": None,
        "description": "Next-gen ultra lightweight baseline multimodal reasoning model."
    },
    {
        "name": "gemini-3.1-flash-lite",
        "display_name": "Gemini 3.1 Flash Lite",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": False,
        "suggested_replacement": None,
        "description": "Speed optimized lightweight multimodal model."
    },
    {
        "name": "gemini-2.5-flash-lite",
        "display_name": "Gemini 2.5 Flash Lite",
        "status": "DEPRECATED",
        "multimodal": True,
        "deprecated": True,
        "supports_thinking": False,
        "suggested_replacement": "gemini-3.5-flash-lite",
        "description": "Retired legacy model code (404 NOT_FOUND by vendor)."
    },
    {
        "name": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "status": "DEPRECATED",
        "multimodal": True,
        "deprecated": True,
        "supports_thinking": True,
        "suggested_replacement": "gemini-3.5-flash",
        "description": "Retired legacy model code (404 NOT_FOUND by vendor)."
    },
    {
        "name": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "status": "DEPRECATED",
        "multimodal": True,
        "deprecated": True,
        "supports_thinking": False,
        "suggested_replacement": "gemini-3.5-flash-lite",
        "description": "Retired legacy model code (404 NOT_FOUND by vendor)."
    },
    {
        "name": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "status": "DEPRECATED",
        "multimodal": True,
        "deprecated": True,
        "supports_thinking": True,
        "suggested_replacement": "gemini-3.8-flash",
        "description": "Legacy model code (Deprecated - Please upgrade to Gemini 3.8 Flash)."
    },
    {
        "name": "gemini-1.0-pro",
        "display_name": "Gemini 1.0 Pro",
        "status": "DEPRECATED",
        "multimodal": False,
        "deprecated": True,
        "supports_thinking": False,
        "suggested_replacement": "gemini-3.5-flash-lite",
        "description": "Legacy text-only model."
    }
]


def load_model_registry() -> Dict[str, Any]:
    """Loads cached model status registry from core/model_registry.json."""
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read model_registry.json: {e}")
    return {"last_probed_at": 0, "models": {}}


def save_model_registry(registry_data: Dict[str, Any]) -> None:
    """Saves updated model status registry to core/model_registry.json."""
    try:
        os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save model_registry.json: {e}")


def probe_model_status(model_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs pre-flight health probe for a single model ID to determine availability & status.
    """
    norm_name = model_name.lower().replace("models/", "").strip()
    
    # Check known deprecated models
    if any(k in norm_name for k in ["2.5-flash-lite", "2.5-flash", "2.0-flash", "1.5-flash", "1.5-pro", "2.5-pro", "1.0-pro", "deprecated", "legacy"]):
        replacement = "gemini-3.8-flash" if ("3.8" in norm_name or "2.5" in norm_name or "2.0" in norm_name) else "gemini-3.5-flash-lite"
        return {
            "name": norm_name,
            "status": "DEPRECATED",
            "deprecated": True,
            "suggested_replacement": replacement,
            "probe_msg": "Model is marked as deprecated by vendor."
        }

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        # Static status fallback
        is_new = norm_name not in KNOWN_BASELINE_MODELS
        status = "NEW_DISCOVERED" if is_new else "ACTIVE"
        return {
            "name": norm_name,
            "status": status,
            "deprecated": False,
            "suggested_replacement": None,
            "probe_msg": "Offline fallback verification."
        }

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        # Pre-flight lightweight content generation probe
        config = types.GenerateContentConfig(max_output_tokens=1, temperature=0.0)
        client.models.generate_content(
            model=norm_name,
            contents="ping",
            config=config
        )

        is_new = norm_name not in KNOWN_BASELINE_MODELS
        status = "NEW_DISCOVERED" if is_new else "ACTIVE"

        return {
            "name": norm_name,
            "status": status,
            "deprecated": False,
            "suggested_replacement": None,
            "probe_msg": "Pre-flight probe passed successfully."
        }

    except Exception as e:
        err_str = str(e)
        if "404" in err_str or "no longer available" in err_str or "NOT_FOUND" in err_str:
            replacement = "gemini-3.8-flash"
            m = re.search(r"use models/([a-zA-Z0-9\.\-]+)", err_str)
            if m:
                replacement = m.group(1)
            return {
                "name": norm_name,
                "status": "DEPRECATED",
                "deprecated": True,
                "suggested_replacement": replacement,
                "probe_msg": f"Model not found or offline (404): {err_str}"
            }
        else:
            # Operational error (e.g. rate limit/quota), keep active status
            is_new = norm_name not in KNOWN_BASELINE_MODELS
            status = "NEW_DISCOVERED" if is_new else "ACTIVE"
            return {
                "name": norm_name,
                "status": status,
                "deprecated": False,
                "suggested_replacement": None,
                "probe_msg": f"Operational probe note: {err_str}"
            }


def extract_model_version_key(model: Dict[str, Any]) -> Tuple[int, float, str]:
    """
    Key function for sorting candidate models from newest version to oldest.
    1. Active/New Discovered first (0), Deprecated last (1).
    2. Model version number descending (-version_num, e.g. 3.8 > 3.5 > 2.0 > 1.5).
    3. Model name string.
    """
    name = model.get("name", "").lower()
    is_deprecated = model.get("deprecated") or model.get("status") == "DEPRECATED"
    dep_rank = 1 if is_deprecated else 0

    m = re.search(r"(\d+(?:\.\d+)?)", name)
    version_num = float(m.group(1)) if m else 0.0

    return (dep_rank, -version_num, name)


def list_candidate_models(api_key: Optional[str] = None, force_refresh: bool = False, probe: bool = True) -> List[Dict[str, Any]]:
    """
    Discovers Google Gemini models via API and returns candidate models with status badges & caching.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")

    registry = load_model_registry()
    now_ts = time.time()
    cached_models = registry.get("models", {})
    last_probed_at = registry.get("last_probed_at", 0)

    # Return cached registry if fresh (<24 hours) and force_refresh is False
    if not force_refresh and (now_ts - last_probed_at < CACHE_TTL_SECONDS) and cached_models:
        logger.info("[Model Radar] Returning cached model registry (<24h TTL).")
        res = list(cached_models.values())
        res.sort(key=extract_model_version_key)
        return res

    if not key:
        logger.info("GEMINI_API_KEY not present. Returning default model catalog.")
        res = list(DEFAULT_MODELS)
        res.sort(key=extract_model_version_key)
        return res

    try:
        from google import genai
        client = genai.Client(api_key=key)

        candidate_list = []
        raw_models = client.models.list()

        discovered_dict = {}

        for m in raw_models:
            name = m.name.replace("models/", "") if hasattr(m, "name") and m.name else str(m)
            
            supported_actions = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" not in supported_actions and "generate_content" not in supported_actions:
                continue

            display_name = getattr(m, "display_name", name)
            description = getattr(m, "description", "")

            if any(term in name.lower() for term in ["embedding", "imagen", "aqa", "tts", "stt", "veo", "lyria", "robotics", "computer-use", "banana"]):
                continue

            deprecated = False
            if any(term in name.lower() for term in ["deprecated", "legacy", "1.0", "2.5-flash", "2.5-pro"]):
                deprecated = True

            multimodal = True
            if "text-only" in description.lower() or "bison" in name or "gecko" in name:
                multimodal = False

            supports_thinking = any(v in name for v in ["2.0", "2.5", "3.0", "3.1", "3.5", "3.6", "3.7", "3.8"]) or "thinking" in name.lower()

            is_new = name not in KNOWN_BASELINE_MODELS
            initial_status = "DEPRECATED" if deprecated else ("NEW_DISCOVERED" if is_new else "ACTIVE")
            suggested_rep = "gemini-3.8-flash" if deprecated else None

            model_info = {
                "name": name,
                "display_name": display_name,
                "status": initial_status,
                "multimodal": multimodal,
                "deprecated": deprecated,
                "supports_thinking": supports_thinking,
                "suggested_replacement": suggested_rep,
                "description": description,
                "probed_at": datetime.now().isoformat()
            }
            discovered_dict[name] = model_info

        # Pre-flight probe candidate models
        if probe:
            for m_name, m_info in discovered_dict.items():
                if not m_info["deprecated"]:
                    probe_res = probe_model_status(m_name, api_key=key)
                    m_info["status"] = probe_res["status"]
                    m_info["deprecated"] = probe_res["deprecated"]
                    m_info["suggested_replacement"] = probe_res["suggested_replacement"]

        # Ensure default baseline & deprecated models are present in registry
        for d in DEFAULT_MODELS:
            if d["name"] not in discovered_dict:
                discovered_dict[d["name"]] = d

        final_candidates = list(discovered_dict.values())
        final_candidates.sort(key=extract_model_version_key)

        # Update cache
        registry["last_probed_at"] = now_ts
        registry["models"] = discovered_dict
        save_model_registry(registry)

        logger.info(f"[Model Radar] Discovered and probed {len(final_candidates)} candidate models.")
        return final_candidates

    except Exception as e:
        logger.warning(f"Failed to fetch remote models via google-genai SDK ({e}). Returning default catalog.")
        res = list(DEFAULT_MODELS)
        res.sort(key=extract_model_version_key)
        return res


def get_model_status_badge(model: Dict[str, Any]) -> str:
    """Formats human-readable status badge for UI display."""
    status = model.get("status", "ACTIVE")
    name = model.get("name", "")
    rep = model.get("suggested_replacement")

    if status == "DEPRECATED" or model.get("deprecated"):
        rep_str = f" - 請改用 {rep}" if rep else ""
        return f"🔴 {name} (已除役{rep_str})"
    elif status == "NEW_DISCOVERED":
        return f"🚀 {name} (新發佈)"
    else:
        return f"🟢 {name} (現役)"


def get_active_models_radar(api_key: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Returns dictionary mapping model_name -> model info dict for fast status lookup and pre-flight filtering.
    """
    candidates = list_candidate_models(api_key=api_key, force_refresh=force_refresh, probe=False)
    radar_map = {}
    for m in candidates:
        name = m.get("name", "").lower().replace("models/", "").strip()
        radar_map[name] = m
    return radar_map
