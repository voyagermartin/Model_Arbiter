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


def verify_mrz_checksums(mrz_line1: str, mrz_line2: str) -> Tuple[bool, List[str]]:
    """Verifies 100% mathematical MRZ checksum compliance according to ICAO Doc 9303 TD3 format."""
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


def get_test_image_bytes(provided_image_bytes: Optional[bytes] = None) -> Tuple[bytes, str]:
    """
    Retrieves image bytes for testing.
    Priority:
    1. Direct user provided image bytes.
    2. Any image file in suites/pp_auto/images/ directory.
    3. Synthetic Pillow fallback image.
    """
    if provided_image_bytes:
        return provided_image_bytes, "使用者上傳圖片"

    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
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
    test_id = test_case.get("id", "UNKNOWN")
    gt = test_case.get("expected_ground_truth", {})

    key = api_key or os.environ.get("GEMINI_API_KEY")

    if not key or mock:
        # Mock mode execution
        start_time = time.time()
        time.sleep(0.05)
        latency = round(time.time() - start_time, 3)

        mock_data = test_case.get("image_mock_data", {})
        extracted_name = f"{mock_data.get('surname', '')} {mock_data.get('given_names', '')}".strip()
        extracted_pass_num = mock_data.get("passport_number", "")
        mrz1 = mock_data.get("mrz_line1", "")
        mrz2 = mock_data.get("mrz_line2", "")

        mrz_valid, mrz_errors = verify_mrz_checksums(mrz1, mrz2)
        fields_match = (
            extracted_name == gt.get("full_name_en") and
            extracted_pass_num == gt.get("passport_number")
        )
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
    img_data, img_source = get_test_image_bytes(image_bytes)

    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError

        client = genai.Client(api_key=key)

        pil_img = Image.open(io.BytesIO(img_data))

        prompt = (
            "You are a professional Passport OCR engine. Analyze the provided passport image "
            "and extract the exact JSON fields: full_name_en, passport_number, nationality, "
            "mrz_line1, mrz_line2."
        )

        start_time = time.time()
        response = client.models.generate_content(
            model=model_name,
            contents=[pil_img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PassportResultSchema,
                temperature=0.0
            )
        )
        latency = round(time.time() - start_time, 3)

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        candidate_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        thought_tokens = getattr(usage, "thoughts_token_count", 0) if usage else 0
        total_tokens = getattr(usage, "total_token_count", prompt_tokens + candidate_tokens + thought_tokens) if usage else 0

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

        mrz1 = parsed_json.get("mrz_line1", "")
        mrz2 = parsed_json.get("mrz_line2", "")
        mrz_valid, mrz_errors = verify_mrz_checksums(mrz1, mrz2)

        fields_match = (
            parsed_json.get("full_name_en") == gt.get("full_name_en") and
            parsed_json.get("passport_number") == gt.get("passport_number")
        )

        passed = json_valid and mrz_valid and fields_match

        error_stage = None
        error_details = None
        if not mrz_valid:
            error_stage = "[校驗階段]"
            error_details = f"MRZ 檢查碼不符: {mrz_errors}"
        elif not fields_match:
            error_stage = "[校驗階段]"
            error_details = f"欄位不一致: 擷取姓名 '{parsed_json.get('full_name_en')}', 護照號 '{parsed_json.get('passport_number')}'"

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
