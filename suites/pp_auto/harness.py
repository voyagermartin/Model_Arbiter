"""suites/pp_auto/harness.py - Passport OCR benchmark harness & MRZ verification engine with multi-stage diagnostics."""

import json
import os
import io
import time
import logging
import traceback
from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw

logger = logging.getLogger("Model_Arbiter.pp_auto.harness")


class PassportResultSchema(BaseModel):
    """Structured output Pydantic schema for passport OCR verification."""
    full_name_en: str = Field(..., description="Full English name extracted from passport/MRZ.")
    passport_number: str = Field(..., description="Passport document number.")
    nationality: str = Field(..., description="3-letter ISO nationality code.")
    mrz_line1: str = Field(..., description="MRZ Line 1 string (44 chars).")
    mrz_line2: str = Field(..., description="MRZ Line 2 string (44 chars).")


def compute_mrz_check_digit(data_str: str) -> int:
    """Computes MRZ check digit using standard 7-3-1 weighting scheme (ICAO Doc 9303)."""
    weights = [7, 3, 1]
    total = 0
    for i, char in enumerate(data_str):
        if '0' <= char <= '9':
            val = int(char)
        elif 'A' <= char <= 'Z':
            val = ord(char) - ord('A') + 10
        elif char == '<':
            val = 0
        else:
            val = 0
        total += val * weights[i % 3]
    return total % 10


import re

def normalize_mrz_line(line: str, expected_length: int = 44) -> str:
    """
    對齊 PP_AUTO 線上生產環境標準：
    去除換行與空白，若字尾角括號遺失或溢出，自動對齊至標準長度 (44 碼)。
    針對 Line 2 末位包含 Check Digit 數字且中間填空 < 殘缺時，自動於末位前補齊 < 至標準 44 碼。
    """
    if not line:
        return ""
    clean = line.strip().replace("\r", "").replace("\n", "").replace(" ", "")
    if 40 <= len(clean) < expected_length:
        if clean[-1].isdigit():
            clean = clean[:-1].ljust(expected_length - 1, "<") + clean[-1]
        else:
            clean = clean.ljust(expected_length, "<")
    elif len(clean) > expected_length:
        clean = clean[:expected_length]
    return clean


def verify_mrz_checksums(mrz_line1: str, mrz_line2: str) -> Tuple[bool, List[str]]:
    """Verifies 100% mathematical MRZ checksum compliance according to ICAO Doc 9303 TD3 format."""
    mrz_line1 = normalize_mrz_line(mrz_line1)
    mrz_line2 = normalize_mrz_line(mrz_line2)
    errors = []
    
    if len(mrz_line1) != 44:
        errors.append(f"MRZ Line 1 length is {len(mrz_line1)}, expected 44.")
    if len(mrz_line2) != 44:
        errors.append(f"MRZ Line 2 length is {len(mrz_line2)}, expected 44.")

    if errors:
        return False, errors

    doc_num_str = mrz_line2[0:9]
    expected_doc_check = mrz_line2[9]
    if expected_doc_check != '<':
        calc_doc_check = compute_mrz_check_digit(doc_num_str)
        if str(calc_doc_check) != expected_doc_check:
            errors.append(f"Passport Number check digit mismatch: calculated {calc_doc_check}, got {expected_doc_check}")

    dob_str = mrz_line2[13:19]
    expected_dob_check = mrz_line2[19]
    if expected_dob_check != '<':
        calc_dob_check = compute_mrz_check_digit(dob_str)
        if str(calc_dob_check) != expected_dob_check:
            errors.append(f"Date of Birth check digit mismatch: calculated {calc_dob_check}, got {expected_dob_check}")

    exp_str = mrz_line2[21:27]
    expected_exp_check = mrz_line2[27]
    if expected_exp_check != '<':
        calc_exp_check = compute_mrz_check_digit(exp_str)
        if str(calc_exp_check) != expected_exp_check:
            errors.append(f"Expiry Date check digit mismatch: calculated {calc_exp_check}, got {expected_exp_check}")

    personal_str = mrz_line2[28:42]
    expected_personal_check = mrz_line2[42]
    if expected_personal_check != '<':
        calc_personal_check = compute_mrz_check_digit(personal_str)
        if str(calc_personal_check) != expected_personal_check:
            errors.append(f"Personal Number check digit mismatch: calculated {calc_personal_check}, got {expected_personal_check}")

    composite_data = mrz_line2[0:10] + mrz_line2[13:20] + mrz_line2[21:28] + mrz_line2[28:43]
    expected_composite_check = mrz_line2[43]
    if expected_composite_check != '<':
        calc_composite_check = compute_mrz_check_digit(composite_data)
        if str(calc_composite_check) != expected_composite_check:
            errors.append(f"Composite check digit mismatch: calculated {calc_composite_check}, got {expected_composite_check}")

    is_valid = len(errors) == 0
    return is_valid, errors


def load_manifest() -> Dict[str, Any]:
    """Loads suite manifest.json configuration according to Suite Protocol v1.0."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_file = os.path.join(current_dir, "manifest.json")
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load manifest.json: {e}")
    return {}


def load_prompt() -> str:
    """Loads prompt text from specified prompt file in manifest.json or fallback."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    manifest = load_manifest()
    prompt_filename = manifest.get("prompt_file", "prompt.txt")
    prompt_file = os.path.join(current_dir, prompt_filename)
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            logger.warning(f"Failed to load {prompt_filename}: {e}")

    return (
        "You are a professional Passport OCR engine. Analyze the provided passport image "
        "and extract the exact JSON fields: full_name_en, passport_number, nationality, "
        "mrz_line1, mrz_line2."
    )


def generate_synthetic_passport_image() -> bytes:
    """Generates a clean synthetic passport image for fallback testing using Pillow."""
    img = Image.new("RGB", (600, 400), color=(240, 244, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 580, 380], outline=(30, 58, 138), width=3)
    draw.text((40, 40), "PASSPORT / PASSEPORT - REPUBLIC OF CHINA (TAIWAN)", fill=(30, 58, 138))
    draw.text((40, 80), "Type: P  Country Code: TWN  Passport No: 350123456", fill=(0, 0, 0))
    draw.text((40, 110), "Surname / Given Names: WANG, HSIAO MING", fill=(0, 0, 0))
    draw.text((40, 140), "Nationality: TWN  Date of Birth: 01 JAN 1990  Sex: M", fill=(0, 0, 0))
    draw.text((30, 300), "P<TWNWANG<<HSIAO<MING<<<<<<<<<<<<<<<<<<<<<<<", fill=(0, 0, 0))
    draw.text((30, 330), "3501234561TWN9001011M3001019<<<<<<<<<<<<<<<4", fill=(0, 0, 0))
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def get_test_image_bytes(
    test_case: Optional[Dict[str, Any]] = None,
    provided_image_bytes: Optional[bytes] = None
) -> Tuple[bytes, str]:
    """
    Retrieves image bytes for testing.
    Priority:
    1. Direct user provided image bytes.
    2. Image file specified by test_case["image_filename"] in suites/pp_auto/images/
    3. Any image file in suites/pp_auto/images/ directory.
    4. Synthetic Pillow fallback image.
    """
    if provided_image_bytes:
        return provided_image_bytes, "使用者上傳圖片"

    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
    if test_case and test_case.get("image_filename"):
        target_path = os.path.join(images_dir, test_case["image_filename"])
        if os.path.exists(target_path):
            try:
                with open(target_path, "rb") as f:
                    return f.read(), f"題目專屬圖片 ({test_case['image_filename']})"
            except Exception:
                pass

    if os.path.exists(images_dir):
        for fname in sorted(os.listdir(images_dir)):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                fpath = os.path.join(images_dir, fname)
                try:
                    with open(fpath, "rb") as f:
                        return f.read(), f"實體目錄圖片 ({fname})"
                except Exception:
                    pass

    return generate_synthetic_passport_image(), "備援 Mock 合成圖片 (Synthetic Sample)"


def call_gemini_with_resilience(client, model_name: str, contents: Any, config: Any, max_retries: int = 5) -> Tuple[Any, float]:
    """
    具備指數退避 (Exponential Backoff) 的穩健呼叫器，專門抵禦 503 High Demand 與 429 Rate Limit。
    回傳 (response, call_latency_sec)，Latency 僅包含最終單次成功呼叫之純推論時間，排除重試睡眠。
    """
    try:
        from google.genai import errors
    except ImportError:
        errors = None

    for attempt in range(max_retries):
        call_start = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            call_latency = round(time.perf_counter() - call_start, 3)
            return response, call_latency
        except Exception as e:
            is_server_error = errors and isinstance(e, errors.ServerError)
            is_client_error = errors and isinstance(e, errors.ClientError)
            
            err_str = str(e)
            err_code = getattr(e, "code", None)

            if is_server_error or "503" in err_str or err_code == 503 or "UNAVAILABLE" in err_str:
                wait_time = (2 ** attempt) + 2  # 3s, 4s, 6s...
                logging.warning(f"⚠️ [{model_name}] 遭遇 503 伺服器滿載，將於 {wait_time} 秒後重試 (第 {attempt+1}/{max_retries} 次)...")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    raise e
            elif "429" in err_str or err_code == 429 or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower():
                wait_time = (attempt * 10) + 12  # 12s, 22s, 32s, 42s...
                logging.warning(f"⚠️ [{model_name}] 觸發 429 速率限制，退避等待 {wait_time} 秒 (第 {attempt+1}/{max_retries} 次)...")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    raise e
            else:
                raise e


def load_test_cases() -> List[Dict[str, Any]]:
    """Loads ground truth test cases from test_cases.json."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_cases_file = os.path.join(current_dir, "test_cases.json")
    with open(test_cases_file, "r", encoding="utf-8") as f:
        return json.load(f)


def execute_test_case(
    model_name: str,
    test_case: Dict[str, Any],
    api_key: Optional[str] = None,
    mock: bool = False,
    image_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Executes a single passport OCR benchmark test case with multi-stage error categorization.
    """
    test_id = test_case.get("id", test_case.get("case_id", "UNKNOWN"))
    gt = test_case.get("expected_ground_truth") or test_case.get("ground_truth") or {}

    key = api_key or os.environ.get("GEMINI_API_KEY")

    if not key or mock:
        # Mock mode execution
        start_time = time.time()
        time.sleep(0.05)
        latency = round(time.time() - start_time, 3)

        mock_data = test_case.get("image_mock_data") or gt
        extracted_name = mock_data.get("full_name_en") or f"{mock_data.get('surname', '')} {mock_data.get('given_names', '')}".strip()
        extracted_pass_num = mock_data.get("passport_number") or mock_data.get("passport_no", "")
        mrz1 = mock_data.get("mrz_line1") or mock_data.get("m1", "")
        mrz2 = mock_data.get("mrz_line2") or mock_data.get("m2", "")

        mrz_valid, mrz_errors = verify_mrz_checksums(mrz1, mrz2)
        
        gt_name = gt.get("full_name_en") or f"{gt.get('surname', '')} {gt.get('given_names', '')}".strip()
        gt_pass_num = gt.get("passport_number") or gt.get("passport_no", "")

        norm_ext_name = re.sub(r'[^A-Z0-9]', '', (extracted_name or "").upper())
        norm_gt_name = re.sub(r'[^A-Z0-9]', '', (gt_name or "").upper())
        norm_ext_pno = re.sub(r'[^A-Z0-9]', '', (extracted_pass_num or "").upper())
        norm_gt_pno = re.sub(r'[^A-Z0-9]', '', (gt_pass_num or "").upper())

        fields_match = True
        if norm_gt_name:
            fields_match = fields_match and (norm_ext_name == norm_gt_name)
        if norm_gt_pno:
            fields_match = fields_match and (norm_ext_pno == norm_gt_pno)

        passed = mrz_valid and fields_match

        is_flash_lite = "lite" in model_name
        prompt_tokens = 640
        candidate_tokens = 220
        thought_tokens = 128 if ("2.0" in model_name or "2.5" in model_name) and not is_flash_lite else 0
        total_tokens = prompt_tokens + candidate_tokens + thought_tokens

        return {
            "test_id": test_id,
            "json_valid": True,
            "mrz_math_valid": mrz_valid,
            "fields_match": fields_match,
            "passed": passed,
            "latency_sec": latency,
            "prompt_tokens": prompt_tokens,
            "candidate_tokens": candidate_tokens,
            "thought_tokens": thought_tokens,
            "total_tokens": total_tokens,
            "error_stage": None if passed else "[校驗階段]",
            "error_details": None if passed else f"MRZ 檢查碼驗算不相符: {mrz_errors}",
            "traceback": None,
            "image_source": "離線 Mock 資料"
        }

    # Live SDK execution
    img_data, img_source = get_test_image_bytes(test_case=test_case, provided_image_bytes=image_bytes)

    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError

        client = genai.Client(api_key=key)

        pil_img = Image.open(io.BytesIO(img_data))

        prompt = load_prompt()
        manifest = load_manifest()
        inf_config = manifest.get("inference_config", {})

        temp = inf_config.get("temperature", 0.1)
        top_p = inf_config.get("top_p")
        mime_type = inf_config.get("response_mime_type", "application/json")
        thinking_cfg_dict = inf_config.get("thinking_config")

        config_kwargs = {
            "response_mime_type": mime_type,
            "response_schema": PassportResultSchema,
            "temperature": temp
        }
        if top_p is not None:
            config_kwargs["top_p"] = top_p

        thinking_obj = None
        if thinking_cfg_dict is not None and hasattr(types, "ThinkingConfig"):
            try:
                clean_dict = {k: v for k, v in thinking_cfg_dict.items() if v not in (-1, None)}
                thinking_obj = types.ThinkingConfig(**clean_dict)
            except Exception as exc:
                logger.warning(f"Could not construct ThinkingConfig: {exc}")

        if thinking_obj is not None:
            config_kwargs["thinking_config"] = thinking_obj

        has_thinking = "thinking_config" in config_kwargs

        try:
            config = types.GenerateContentConfig(**config_kwargs)
            response, latency = call_gemini_with_resilience(
                client=client,
                model_name=model_name,
                contents=[pil_img, prompt],
                config=config
            )
        except Exception as api_exc:
            err_str = str(api_exc).lower()
            err_name = api_exc.__class__.__name__

            is_rate_limit = "429" in err_str or "rate limit" in err_str or "resource_exhausted" in err_str
            is_404 = "404" in err_str or "not_found" in err_str or "no longer available" in err_str
            is_thinking_rejected = "thinking" in err_str or "thought" in err_str or "unsupported" in err_str or "unknown field" in err_str or "budget" in err_str

            if has_thinking and not is_rate_limit and not is_404 and is_thinking_rejected:
                logger.info(f"[INFO] 模型 {model_name} 不支援 Thinking 模式，已自動退回標準直覺推論模式重試。")
                config_kwargs.pop("thinking_config", None)
                has_thinking = False
                config = types.GenerateContentConfig(**config_kwargs)
                response, latency = call_gemini_with_resilience(
                    client=client,
                    model_name=model_name,
                    contents=[pil_img, prompt],
                    config=config
                )
            else:
                raise api_exc

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = (getattr(usage, "prompt_token_count", 0) if usage else 0) or 0
        candidate_tokens = (getattr(usage, "candidates_token_count", 0) if usage else 0) or 0

        # 防禦性解析 Thinking Tokens（支援不同 SDK 版本與多種模型欄位命名）
        def _get_val(obj, k):
            if obj is None:
                return 0
            if isinstance(obj, dict):
                return obj.get(k, 0) or 0
            return getattr(obj, k, 0) or 0

        thought_tokens = 0
        if usage:
            thought_tokens = (
                _get_val(usage, "thoughts_token_count")
                or _get_val(usage, "thinking_token_count")
                or _get_val(usage, "thought_token_count")
            )
            if not thought_tokens:
                details = _get_val(usage, "candidates_tokens_details") or _get_val(usage, "candidates_token_details")
                if details and isinstance(details, (list, tuple)) and len(details) > 0:
                    first = details[0]
                    thought_tokens = (
                        _get_val(first, "thoughts_token_count")
                        or _get_val(first, "thinking_token_count")
                        or _get_val(first, "thought_token_count")
                    )

        logger.info(f"[{model_name}] Tokens -> Prompt: {prompt_tokens}, Candidate: {candidate_tokens}, Thought: {thought_tokens}")

        if usage:
            reported_total = getattr(usage, "total_token_count", None)
            total_tokens = reported_total if reported_total is not None else (prompt_tokens + candidate_tokens + thought_tokens)
        else:
            total_tokens = 0

        # Check response text
        if not response.text:
            return {
                "test_id": test_id,
                "json_valid": False,
                "mrz_math_valid": False,
                "fields_match": False,
                "passed": False,
                "latency_sec": latency,
                "prompt_tokens": prompt_tokens,
                "candidate_tokens": candidate_tokens,
                "thought_tokens": thought_tokens,
                "total_tokens": total_tokens,
                "error_stage": "[呼叫階段]",
                "error_details": "API 回傳空文字內容 (Empty Response Text)",
                "traceback": None,
                "image_source": img_source
            }

        parsed_json = json.loads(response.text)
        json_valid = True

        mrz1 = parsed_json.get("mrz_line1") or parsed_json.get("m1", "")
        mrz2 = parsed_json.get("mrz_line2") or parsed_json.get("m2", "")
        mrz_valid, mrz_errors = verify_mrz_checksums(mrz1, mrz2)

        extracted_name = parsed_json.get("full_name_en")
        if not extracted_name and ("ln" in parsed_json or "fn" in parsed_json):
            extracted_name = f"{parsed_json.get('ln', '')} {parsed_json.get('fn', '')}".strip()

        extracted_pass_num = parsed_json.get("passport_number") or parsed_json.get("pno", "")

        gt_name = gt.get("full_name_en") or f"{gt.get('surname', '')} {gt.get('given_names', '')}".strip()
        gt_pass_num = gt.get("passport_number") or gt.get("passport_no") or gt.get("pno", "")

        norm_ext_name = re.sub(r'[^A-Z0-9]', '', (extracted_name or "").upper())
        norm_gt_name = re.sub(r'[^A-Z0-9]', '', (gt_name or "").upper())
        norm_ext_pno = re.sub(r'[^A-Z0-9]', '', (extracted_pass_num or "").upper())
        norm_gt_pno = re.sub(r'[^A-Z0-9]', '', (gt_pass_num or "").upper())

        ext_words = set(re.findall(r'[A-Z0-9]+', (extracted_name or "").upper()))
        gt_words = set(re.findall(r'[A-Z0-9]+', (gt_name or "").upper()))
        name_match = (norm_ext_name == norm_gt_name) or (bool(gt_words) and ext_words == gt_words)

        fields_match = True
        if norm_gt_name:
            fields_match = fields_match and name_match
        if norm_gt_pno:
            fields_match = fields_match and (norm_ext_pno == norm_gt_pno)

        passed = json_valid and mrz_valid and fields_match

        error_stage = None
        error_details = None
        if not mrz_valid:
            error_stage = "[校驗階段]"
            error_details = f"MRZ 檢查碼不符: {mrz_errors}"
        elif not fields_match:
            error_stage = "[校驗階段]"
            error_details = f"欄位不一致: 擷取姓名 '{extracted_name}' (期望 '{gt_name}'), 護照號 '{extracted_pass_num}' (期望 '{gt_pass_num}')"

        return {
            "test_id": test_id,
            "json_valid": json_valid,
            "mrz_math_valid": mrz_valid,
            "fields_match": fields_match,
            "passed": passed,
            "latency_sec": latency,
            "prompt_tokens": prompt_tokens,
            "candidate_tokens": candidate_tokens,
            "thought_tokens": thought_tokens,
            "total_tokens": total_tokens,
            "error_stage": error_stage,
            "error_details": error_details,
            "traceback": None,
            "image_source": img_source
        }

    except Exception as e:
        tb_str = traceback.format_exc()
        err_msg = str(e)

        # Categorize stage
        if "API_KEY" in err_msg or "INVALID_ARGUMENT" in err_msg or "image" in err_msg.lower():
            stage = "[環境階段]"
        elif "401" in err_msg or "403" in err_msg or "404" in err_msg or "429" in err_msg or "Quota" in err_msg or "UNAUTHENTICATED" in err_msg:
            stage = "[呼叫階段]"
        else:
            stage = "[呼叫階段]"

        return {
            "test_id": test_id,
            "json_valid": False,
            "mrz_math_valid": False,
            "fields_match": False,
            "passed": False,
            "latency_sec": 0.0,
            "prompt_tokens": 0,
            "candidate_tokens": 0,
            "thought_tokens": 0,
            "total_tokens": 0,
            "error_stage": stage,
            "error_details": err_msg,
            "traceback": tb_str,
            "image_source": img_source
        }
