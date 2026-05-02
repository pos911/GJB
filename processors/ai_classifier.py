"""
processors/ai_classifier.py
Gemini 2차 판별 모듈 (배치 처리 최적화 버전).

weak_match/ai_needed인 항목들을 묶어서 Gemini를 호출하여
서울국제정원박람회 관련 여부를 판별한다.
"""
import os
import json
import logging
import time

logger = logging.getLogger(__name__)

# 배치 처리를 위한 프롬프트 템플릿
GEMINI_BATCH_PROMPT_TEMPLATE = """다음 검색 결과 리스트가 2026 서울국제정원박람회(서울숲/성동구 일대)와 관련 있는지 판단하여 분류하라.
각 항목에 대해 "relevant", "irrelevant", "uncertain" 여부와 적절한 카테고리를 지정하라.

반환은 반드시 아래와 같은 JSON array 형식으로만 하라. 다른 설명은 생략하라.
[
  {{
    "id": 0,
    "result": "relevant|irrelevant|uncertain",
    "category": "confirmed|related_issue|comparison|political_context|weak_match|irrelevant",
    "reason": "1문장 근거"
  }},
  ...
]

분류 카테고리 기준:
- confirmed: 서울국제정원박람회 자체를 직접 다루는 결과
- related_issue: 포켓몬, 인파, 교통, 혼잡, 행사 중단 등 행사 연계 이슈
- comparison: 타 행사(고양꽃박람회 등)와 비교하거나 함께 언급
- political_context: 오세훈, 정원오, 정치·인물 맥락 포함
- irrelevant: 서울국제정원박람회와 관련 없음
- weak_match: 제목/요약만으로 판단 불가

분류 대상 리스트:
{items_json}"""


def get_gemini_api_key(config):
    """Gemini API 키를 환경변수 또는 config에서 가져온다."""
    key = os.getenv("GEMINI_API_KEY")
    if key and key != "YOUR_GEMINI_API_KEY":
        return key
    
    key = config.get("gemini_api_key")
    if key and key != "YOUR_GEMINI_API_KEY":
        return key
    
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


def _call_gemini_batch(items_to_send, api_key):
    """
    여러 항목을 한 번에 Gemini에 보내 판별 결과를 받아온다.
    """
    try:
        from google import genai
    except ImportError:
        return None, "google-genai package not installed"
    
    # 입력 데이터 정규화 (ID 포함)
    formatted_items = []
    for i, item in enumerate(items_to_send):
        formatted_items.append({
            "id": i,
            "title": item.get("title", ""),
            "description": item.get("description", "")
        })
    
    items_json = json.dumps(formatted_items, ensure_ascii=False, indent=2)
    prompt = GEMINI_BATCH_PROMPT_TEMPLATE.format(items_json=items_json)
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        response_text = response.text.strip()
        
        # JSON 추출
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        results = json.loads(response_text)
        if not isinstance(results, list):
            return None, "gemini_response_not_a_list"
            
        return results, None
        
    except json.JSONDecodeError as e:
        return None, f"gemini_json_parse_error: {str(e)}"
    except Exception as e:
        return None, f"gemini_error: {str(e)}"


def apply_ai_classification(items, config):
    """
    전체 item 목록 중 ai_needed인 항목들을 배치(Batch)로 Gemini 분류를 적용한다.
    """
    rf = config.get("relevance_filter", {})
    if not rf.get("ambiguous_ai_enabled", False):
        return items
    
    api_key = get_gemini_api_key(config)
    if not api_key:
        logger.warning("Gemini API key missing. Skipping AI classification.")
        return items

    # 판별이 필요한 항목만 추출
    ai_needed_items = [item for item in items if item.get("ai_needed", False) and item.get("category") == "weak_match"]
    if not ai_needed_items:
        return items

    logger.info(f"Gemini AI Batch classification: {len(ai_needed_items)} items to classify")
    
    batch_size = 10
    total_items = len(ai_needed_items)
    
    for start_idx in range(0, total_items, batch_size):
        end_idx = min(start_idx + batch_size, total_items)
        batch = ai_needed_items[start_idx:end_idx]
        
        logger.info(f"  - Processing batch {start_idx//batch_size + 1} ({len(batch)} items)...")
        
        results, error = _call_gemini_batch(batch, api_key)
        
        if error:
            logger.warning(f"    Batch error: {error}")
            for item in batch:
                item["ai_used"] = False
                item["ai_reason"] = error
            continue

        # 결과 맵핑 (ID 기반)
        for res in results:
            try:
                idx = int(res.get("id", -1))
                if 0 <= idx < len(batch):
                    item = batch[idx]
                    
                    ai_result = res.get("result", "uncertain")
                    ai_category = res.get("category", "weak_match")
                    ai_reason = res.get("reason", "")
                    
                    item["ai_used"] = True
                    item["ai_result"] = ai_result
                    item["ai_reason"] = ai_reason
                    item["ai_category"] = ai_category
                    
                    # 카테고리 및 노출 정책 적용
                    if ai_result == "irrelevant" or ai_category == "irrelevant":
                        item["category"] = "ai_irrelevant"
                        item["filter_status"] = "excluded"
                        item["public_visible_default"] = False
                    elif ai_result == "relevant" and ai_category in ["confirmed", "related_issue", "comparison", "political_context"]:
                        item["category"] = ai_category
                        item["filter_status"] = "kept"
                        item["public_visible_default"] = True
                    else:
                        # uncertain 혹은 판단 보류
                        item["category"] = "weak_match"
                        item["filter_status"] = "review"
                        item["public_visible_default"] = rf.get("weak_match_public_default", False)
            except (ValueError, TypeError):
                continue
        
        # API Rate limit 방지를 위해 아주 짧게 대기 (필요시)
        if end_idx < total_items:
            time.sleep(0.5)

    ai_used_count = sum(1 for item in ai_needed_items if item.get("ai_used", True))
    logger.info(f"Gemini AI Batch classification complete: {ai_used_count}/{len(ai_needed_items)} items processed")
    
    return items
