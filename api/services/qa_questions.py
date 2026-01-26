"""QA Questions service - loads sample questions from Google Sheet."""
import os
import logging
import random
from typing import List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Fallback questions if Google Sheet is unavailable
# These questions are selected for good Vector vs Graph comparison
# Graph retrieval typically performs 25-30x better on these queries
FALLBACK_QUESTIONS = [
    "Thuế suất ưu đãi 10% áp dụng cho đối tượng nào?",
    "Hàng hóa nào chịu thuế tiêu thụ đặc biệt?",
    "Chi phí nào được khấu trừ khi tính thuế TNDN?",
    "Doanh thu chịu thuế TNDN bao gồm những gì?",
    "Điều kiện được miễn thuế thu nhập doanh nghiệp?",
    "Căn cứ tính thuế giá trị gia tăng là gì?",
    "Thuế suất thuế thu nhập doanh nghiệp là bao nhiêu?",
    "Cách tính thuế thu nhập cá nhân từ tiền lương?",
]

# Cache for questions
_cached_questions: Optional[List[dict]] = None


def _load_from_google_sheet() -> List[dict]:
    """Load questions from Google Sheet using gspread."""
    try:
        import gspread
        from google.oauth2 import service_account

        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "1xBgBiA1KwTNdqPfrqH5p_Sf-MhTCXMfy4ousb0WE4Ik")

        if not creds_path or not os.path.exists(creds_path):
            logger.warning("Google credentials not found, using fallback questions")
            return []

        gc = gspread.service_account(filename=creds_path)
        sh = gc.open_by_key(sheet_id)

        # Try different tab names that might contain QA data
        for tab_name in ["QA_sample", "QA_Gen", "QA_Crawled", "Potential QA Question", "gen_100", "hybrid"]:
            try:
                wks = sh.worksheet(tab_name)
                records = wks.get_all_records()
                if records:
                    logger.info(f"Loaded {len(records)} questions from tab '{tab_name}'")
                    return records
            except gspread.exceptions.WorksheetNotFound:
                continue

        logger.warning("No QA worksheet found in Google Sheet")
        return []

    except ImportError:
        logger.warning("gspread not installed, using fallback questions")
        return []
    except Exception as e:
        logger.error(f"Failed to load from Google Sheet: {e}")
        return []


def get_sample_questions(count: int = 8, shuffle: bool = True) -> List[dict]:
    """
    Get sample questions for the UI.

    Returns list of dicts with 'question' and optional 'category' fields.
    """
    global _cached_questions

    # Try to load from Google Sheet (cached)
    if _cached_questions is None:
        _cached_questions = _load_from_google_sheet()

    if _cached_questions:
        questions = _cached_questions
        # Extract question field (might be 'question', 'Question', or similar)
        result = []
        for q in questions:
            question_text = q.get("question") or q.get("Question") or q.get("text") or ""
            if question_text:
                result.append({
                    "question": question_text,
                    "category": q.get("question_category") or q.get("category") or "General",
                    "id": q.get("question_id") or q.get("id") or "",
                    "type": q.get("question_type") or q.get("type") or ""
                })

        if shuffle:
            random.shuffle(result)

        return result[:count]

    # Fallback to hardcoded questions
    result = [{"question": q, "category": "General", "id": "", "type": ""} for q in FALLBACK_QUESTIONS]
    if shuffle:
        random.shuffle(result)
    return result[:count]


def refresh_questions_cache():
    """Force refresh of questions cache."""
    global _cached_questions
    _cached_questions = None
    return get_sample_questions()
