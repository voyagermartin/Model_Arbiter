"""core/discovery.py - Google Gemini model active candidate discovery module."""

import os
import logging

logger = logging.getLogger("Model_Arbiter.discovery")

# Default offline fallback model catalog in case API key is not present or offline execution is requested
DEFAULT_MODELS = [
    {
        "name": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": True,
        "description": "Next-gen hybrid reasoning model offering ultra-fast speed and low cost."
    },
    {
        "name": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": True,
        "description": "Fast multimodal workhorse model with thinking token capabilities."
    },
    {
        "name": "gemini-2.0-flash-lite",
        "display_name": "Gemini 2.0 Flash Lite",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": False,
        "description": "Ultra lightweight cost-optimized multimodal model."
    },
    {
        "name": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": False,
        "description": "Lightweight multimodal model optimized for speed."
    },
    {
        "name": "gemini-1.5-pro",
        "display_name": "Gemini 1.5 Pro",
        "status": "ACTIVE",
        "multimodal": True,
        "deprecated": False,
        "supports_thinking": False,
        "description": "Complex reasoning multimodal model with large context window."
    },
    {
        "name": "gemini-1.0-pro",
        "display_name": "Gemini 1.0 Pro",
        "status": "DEPRECATED",
        "multimodal": False,
        "deprecated": True,
        "supports_thinking": False,
        "description": "Legacy text-only model."
    }
]


def list_candidate_models(api_key: str = None) -> list[dict]:
    """
    Fetches official Google Gemini models and returns active candidate multimodal models.

    Args:
        api_key: Optional Gemini API Key. If not provided, reads from GEMINI_API_KEY env var.

    Returns:
        List of dictionaries containing model attributes (name, display_name, status, multimodal, deprecated, supports_thinking).
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")

    if not key:
        logger.info("GEMINI_API_KEY not found. Returning built-in fallback model candidate list.")
        return DEFAULT_MODELS

    try:
        from google import genai
        client = genai.Client(api_key=key)

        candidate_list = []
        raw_models = client.models.list()

        for m in raw_models:
            # Model name normalization (e.g., 'models/gemini-2.0-flash' -> 'gemini-2.0-flash')
            name = m.name.replace("models/", "") if hasattr(m, "name") and m.name else str(m)
            
            # Check capabilities
            supported_actions = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" not in supported_actions and "generate_content" not in supported_actions:
                continue

            display_name = getattr(m, "display_name", name)
            description = getattr(m, "description", "")
            
            # Deprecation check
            deprecated = False
            if "deprecated" in name.lower() or "legacy" in name.lower() or "1.0" in name:
                deprecated = True

            # Multimodal check
            multimodal = True
            if "text-only" in description.lower() or "bison" in name or "gecko" in name:
                multimodal = False

            # Active filter
            status = "ACTIVE" if not deprecated else "DEPRECATED"

            # Filter out non-target embeddings/imagen/aqa models
            if any(term in name.lower() for term in ["embedding", "imagen", "aqa", "tts", "stt"]):
                continue

            supports_thinking = "2.0" in name or "2.5" in name or "thinking" in name.lower()

            candidate_list.append({
                "name": name,
                "display_name": display_name,
                "status": status,
                "multimodal": multimodal,
                "deprecated": deprecated,
                "supports_thinking": supports_thinking,
                "description": description
            })

        if candidate_list:
            return candidate_list
        return DEFAULT_MODELS

    except Exception as e:
        logger.warning(f"Failed to fetch remote models via google-genai SDK ({e}). Falling back to static list.")
        return DEFAULT_MODELS
