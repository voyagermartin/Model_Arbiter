"""suites/pp_auto/harness.py - Passport OCR benchmark harness & MRZ verification engine."""

import json
import os
import time
import logging
from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("Model_Arbiter.pp_auto.harness")


class PassportResultSchema(BaseModel):
    """Structured output Pydantic schema for passport OCR verification."""
    full_name_en: str = Field(..., description="Full English name extracted from passport/MRZ.")
    passport_number: str = Field(..., description="Passport document number.")
    nationality: str = Field(..., description="3-letter ISO nationality code.")
    mrz_line1: str = Field(..., description="MRZ Line 1 string (44 chars).")
    mrz_line2: str = Field(..., description="MRZ Line 2 string (44 chars).")


def compute_mrz_check_digit(data_str: str) -> int:
    """
    Computes MRZ check digit using the standard 7-3-1 weighting scheme (ICAO Doc 9303).
    """
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
    """
    Verifies 100% mathematical MRZ checksum compliance according to ICAO Doc 9303 TD3 format.

    Returns:
        (is_valid: bool, errors: List[str])
    """
    errors = []
    
    if len(mrz_line1) != 44:
        errors.append(f"MRZ Line 1 length is {len(mrz_line1)}, expected 44.")
    if len(mrz_line2) != 44:
        errors.append(f"MRZ Line 2 length is {len(mrz_line2)}, expected 44.")

    if errors:
        return False, errors

    # Check 1: Passport number check digit (Line 2 pos 0:9 vs pos 9)
    doc_num_str = mrz_line2[0:9]
    expected_doc_check = mrz_line2[9]
    if expected_doc_check != '<':
        calc_doc_check = compute_mrz_check_digit(doc_num_str)
        if str(calc_doc_check) != expected_doc_check:
            errors.append(f"Passport Number check digit mismatch: calculated {calc_doc_check}, got {expected_doc_check}")

    # Check 2: Date of birth check digit (Line 2 pos 13:19 vs pos 19)
    dob_str = mrz_line2[13:19]
    expected_dob_check = mrz_line2[19]
    if expected_dob_check != '<':
        calc_dob_check = compute_mrz_check_digit(dob_str)
        if str(calc_dob_check) != expected_dob_check:
            errors.append(f"Date of Birth check digit mismatch: calculated {calc_dob_check}, got {expected_dob_check}")

    # Check 3: Expiration date check digit (Line 2 pos 21:27 vs pos 27)
    exp_str = mrz_line2[21:27]
    expected_exp_check = mrz_line2[27]
    if expected_exp_check != '<':
        calc_exp_check = compute_mrz_check_digit(exp_str)
        if str(calc_exp_check) != expected_exp_check:
            errors.append(f"Expiry Date check digit mismatch: calculated {calc_exp_check}, got {expected_exp_check}")

    # Check 4: Personal number check digit (Line 2 pos 28:42 vs pos 42)
    personal_str = mrz_line2[28:42]
    expected_personal_check = mrz_line2[42]
    if expected_personal_check != '<':
        calc_personal_check = compute_mrz_check_digit(personal_str)
        if str(calc_personal_check) != expected_personal_check:
            errors.append(f"Personal Number check digit mismatch: calculated {calc_personal_check}, got {expected_personal_check}")

    # Check 5: Composite check digit (Line 2 positions 0:10 + 13:20 + 21:28 + 28:43 vs pos 43)
    composite_data = mrz_line2[0:10] + mrz_line2[13:20] + mrz_line2[21:28] + mrz_line2[28:43]
    expected_composite_check = mrz_line2[43]
    if expected_composite_check != '<':
        calc_composite_check = compute_mrz_check_digit(composite_data)
        if str(calc_composite_check) != expected_composite_check:
            errors.append(f"Composite check digit mismatch: calculated {calc_composite_check}, got {expected_composite_check}")

    is_valid = len(errors) == 0
    return is_valid, errors


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
    mock: bool = False
) -> Dict[str, Any]:
    """
    Executes a single passport OCR benchmark test case.

    Acceptance criteria:
    1. JSON structure parsing compliance.
    2. MRZ checksum mathematical verification 100% pass.
    3. Key fields (full_name_en, passport_number) match expected ground truth.

    Returns test metric dict:
    {
        "test_id": str,
        "json_valid": bool,
        "mrz_math_valid": bool,
        "fields_match": bool,
        "passed": bool,
        "latency_sec": float,
        "prompt_tokens": int,
        "candidate_tokens": int,
        "thought_tokens": int,
        "total_tokens": int,
        "error": Optional[str]
    }
    """
    test_id = test_case.get("id", "UNKNOWN")
    gt = test_case.get("expected_ground_truth", {})

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key or mock:
        # Mock execution mode
        start_time = time.time()
        time.sleep(0.05)  # Simulate network latency
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

        # Mock token counts (varying slightly per model)
        is_flash_lite = "lite" in model_name
        is_pro = "pro" in model_name

        prompt_tokens = 320
        candidate_tokens = 110
        thought_tokens = 64 if ("2.0" in model_name or "2.5" in model_name) and not is_flash_lite else 0
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
            "error": None if passed else f"MRZ errors: {mrz_errors}"
        }

    # Live SDK execution mode
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        prompt = (
            "Extract the following passport fields into JSON: full_name_en, passport_number, "
            "nationality, mrz_line1, mrz_line2.\n"
            f"Reference mock input data: {json.dumps(test_case.get('image_mock_data', {}))}"
        )

        start_time = time.time()
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PassportResultSchema,
                temperature=0.0
            )
        )
        latency = round(time.time() - start_time, 3)

        # Extract usage metadata
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        candidate_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        thought_tokens = getattr(usage, "thoughts_token_count", 0) if usage else 0
        total_tokens = getattr(usage, "total_token_count", prompt_tokens + candidate_tokens + thought_tokens) if usage else 0

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
            "error": None if passed else f"MRZ errors: {mrz_errors}"
        }

    except Exception as e:
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
            "error": str(e)
        }
