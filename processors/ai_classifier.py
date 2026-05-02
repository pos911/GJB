"""
processors/ai_classifier.py
Gemini 2차 판별 모듈.

weak_match/ai_needed인 항목에만 Gemini를 선택 호출하여
서울국제정원박람회 관련 여부를 판별한다.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


GEMINI_PROMPT_TEMPLATE = """다음 검색 결과가 2026 서울국제정원박람회(서울숲/성동구 일대)와 관련 있는지 판단하고 카테고리를 분류하라.
본문 전체가 아니라 검색 결과 제목과 요약문 기준으로만 판단하라.

반환은 JSON으로만 하라.
{{
  "result": "relevant|irrelevant|uncertain",
  "category": "confirmed|related_issue|comparison|political_context|weak_match|irrelevant",
  "reason": "1문장 근거"
}}

분류 기준:
- confirmed: 서울국제정원박람회 자체를 직접 다루는 결과
- related_issue: 포켓몬, 인파, 교통, 혼잡, 행사 중단 등 행사 연계 이슈
- comparison: 고양꽃박람회, 순천만국제정원박람회, 태안꽃박람회 등 타 행사와 비교하거나 함께 언급
- political_context: 오세훈, 정원오, 구청장, 후보, 선거, 공약 등 정치·인물 맥락 포함
- irrelevant: 서울국제정원박람회와 관련 없음
- weak_match: 제목/요약만으로 판단 불가

제목: {title}
요약: {description}"""


def get_gemini_api_key(config):
    """
    Gemini API 키를 우선순위에 따라 반환한다.
    1. 환경변수 GEMINI_API_KEY
    2. config 내 gemini_api_key (secret.json에서 로드됨)
    3. SECRET_JSON 환경변수 내 gemini_api_key
    """
    # 1. 환경변수
    key = os.getenv("GEMINI_API_KEY")
    if key and key != "YOUR_GEMINI_API_KEY":
        return key
    
    # 2. config (secret.json에서 merge됨)
    key = config.get("gemini_api_key")
    if key and key != "YOUR_GEMINI_API_KEY":
        return key
    
    # 3. SECRET_JSON 환경변수
    secret_str = os.getenv("SECRET_JSON")
    if secret_str:
        try:
            secrets = json.loads(secret_str)
            key = secrets.get("gemini_api_key")
            if key and key != "YOUR_GEMINI_API_KEY":
                return key
        except json.JSONDecodeError:
            pass
    
    return None


def _call_gemini(title, description, api_key):
    """
    Gemini API를 호출하여 분류 결과를 반환한다.
    google-genai 패키지 사용.
    """
    try:
        from google import genai
    except ImportError:
        return None, "google-genai package not installed"
    
    prompt = GEMINI_PROMPT_TEMPLATE.format(
        title=title or "",
        description=description or ""
    )
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        response_text = response.text.strip()
        
        # JSON 추출 (코드 블록 안에 있을 수 있음)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_text)
        return result, None
        
    except json.JSONDecodeError as e:
        return None, f"gemini_json_parse_error: {str(e)}"
    except Exception as e:
        return None, f"gemini_error: {str(e)}"


def classify_with_gemini(item, config):
    """
    weak_match/ai_needed인 항목에 대해 Gemini 2차 판별을 수행한다.
    
    호출 조건:
    - config.relevance_filter.ambiguous_ai_enabled = true
    - item.ai_needed = true
    - item.category = weak_match
    - gemini_api_key 존재
    
    결과에 따라 item의 ai_used, ai_category, ai_reason,
    그리고 category, filter_status, public_visible_default를 갱신한다.
    """
    rf = config.get("relevance_filter", {})
    
    # 호출 조건 확인
    if not rf.get("ambiguous_ai_enabled", False):
        return item
    
    if not item.get("ai_needed", False):
        return item
    
    if item.get("category") != "weak_match":
        return item
    
    api_key = get_gemini_api_key(config)
    
    if not api_key:
        logger.warning("Gemini API key not found. Skipping AI classification.")
        item["ai_used"] = False
        item["ai_reason"] = "gemini_api_key_missing"
        return item
    
    title = item.get("title", "")
    description = item.get("description", "")
    
    result, error = _call_gemini(title, description, api_key)
    
    if error:
        # Gemini 오류 시 전체 파이프라인 실패 금지
        logger.warning(f"Gemini classification error: {error}")
        item["ai_used"] = False
        item["ai_reason"] = error
        return item
    
    # 결과 처리
    ai_result = result.get("result", "uncertain")
    ai_category = result.get("category", "weak_match")
    ai_reason = result.get("reason", "")
    
    item["ai_used"] = True
    item["ai_result"] = ai_result
    item["ai_reason"] = ai_reason
    
    if ai_result == "irrelevant" or ai_category == "irrelevant":
        item["category"] = "ai_irrelevant"
        item["filter_status"] = "excluded"
        item["public_visible_default"] = False
        item["ai_category"] = "irrelevant"
        
    elif ai_result == "relevant" and ai_category in ["confirmed", "related_issue", "comparison", "political_context"]:
        item["category"] = ai_category
        item["filter_status"] = "kept"
        item["public_visible_default"] = True
        item["ai_category"] = ai_category
        
    elif ai_result == "uncertain" or ai_category == "weak_match":
        item["category"] = "weak_match"
        item["filter_status"] = "review"
        item["public_visible_default"] = rf.get("weak_match_public_default", False)
        item["ai_category"] = "weak_match"
    
    return item


def apply_ai_classification(items, config):
    """
    전체 item 목록 중 ai_needed인 항목에만 Gemini 분류를 적용한다.
    """
    rf = config.get("relevance_filter", {})
    
    if not rf.get("ambiguous_ai_enabled", False):
        logger.info("Gemini AI classification disabled (ambiguous_ai_enabled=false)")
        return items
    
    api_key = get_gemini_api_key(config)
    if not api_key:
        logger.warning("Gemini API key missing. AI classification will be skipped for all items.")
        for item in items:
            if item.get("ai_needed", False) and item.get("category") == "weak_match":
                item["ai_used"] = False
                item["ai_reason"] = "gemini_api_key_missing"
        return items
    
    ai_needed_items = [item for item in items if item.get("ai_needed", False) and item.get("category") == "weak_match"]
    logger.info(f"Gemini AI classification: {len(ai_needed_items)} items to classify")
    
    for item in ai_needed_items:
        classify_with_gemini(item, config)
    
    ai_used_count = sum(1 for item in ai_needed_items if item.get("ai_used", False))
    logger.info(f"Gemini AI classification complete: {ai_used_count}/{len(ai_needed_items)} items classified")
    
    return items
