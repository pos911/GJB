"""
processors/ai_classifier.py
Gemini 2차 판별 모듈 (배치 처리 + 고도화된 컨텍스트).

규칙 기반 분류에서 모호하거나 고위험인 항목들을 선별하여
Gemini AI를 통해 최종 판별을 수행한다.
"""
import os
import json
import logging
import time

logger = logging.getLogger(__name__)

# 배치 처리를 위한 엄격한 프롬프트 템플릿
GEMINI_BATCH_PROMPT_TEMPLATE = """당신은 '2026 서울국제정원박람회' 관련 콘텐츠를 선별하는 전문가입니다.
제공된 검색 결과 리스트가 '2026 서울국제정원박람회(서울숲/뚝섬/성동구 일대)'와 직접적으로 관련 있는지 판단하여 분류하십시오.

[판단 기준]
1. Relevant 조건 (하나 이상 필수):
   - 공식 행사명(서울국제정원박람회 등)이 명시됨
   - 서울 내 개최 장소(서울숲, 뚝섬, 성동구 등)와 '정원박람회'가 함께 언급됨
   - 서울시/오세훈 시장의 정원 도시 정책 맥락임
2. Irrelevant 조건:
   - 타 지역(순천, 고양, 태안, 울산 등)의 정원/꽃 박람회 단독 글
   - 도시재생, 파크골프장, 쓰레기 매립지 공원화 등 박람회와 무관한 공원 조성 글
   - 서울국제정원박람회와 명시적 연결이 없는 일반 여행/숙박/맛집 정보
   - 서울 앵커(장소/명칭)가 없고 일반적인 '정원박람회' 키워드만 있는 글

[주의사항]
- '관련 있을 수도 있음'이라는 추론은 배제하고 명시적 근거로만 판단하십시오.
- 타 지역 행사는 서울 행사와 직접 비교/언급하는 경우에만 'relevant'(category: comparison)로 분류하십시오.
- 애매하면 'uncertain' 또는 'irrelevant'로 분류하십시오.

[반환 형식]
반드시 아래와 같은 JSON array 형식으로만 응답하십시오.
[
  {{
    "id": 0,
    "result": "relevant|irrelevant|uncertain",
    "category": "confirmed|related_issue|comparison|political_context|weak_match|irrelevant",
    "reason": "서울 앵커 유무를 포함한 1문장 판단 근거"
  }},
  ...
]

[분류 대상 리스트]
{items_json}"""


def get_gemini_api_key(config):
    """Gemini API 키를 가져온다."""
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


def calculate_risk_score(item):
    """항목의 위험도/모호성 점수를 계산한다 (AI 우선순위용)."""
    score = 0
    if item.get("category") == "weak_match": score += 5
    if item.get("seoul_anchor_score", 0) == 0: score += 5
    if item.get("other_event_score", 0) > 0: score += 3
    if item.get("noise_score", 0) > 0: score += 2
    if item.get("source") == "naver_blog": score += 2
    if item.get("category") in ["comparison", "related_issue"] and item.get("seoul_anchor_score", 0) < 2:
        score += 4
    return score


def _call_gemini_batch(items_to_send, api_key):
    """Gemini API를 호출하여 배치 결과를 반환한다."""
    try:
        from google import genai
    except ImportError:
        return None, "google-genai package not installed"
    
    # AI에 전달할 컨텍스트 확장
    formatted_items = []
    for i, item in enumerate(items_to_send):
        formatted_items.append({
            "id": i,
            "source": item.get("source", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "author": item.get("author_or_channel", ""),
            "category_before": item.get("category", ""),
            "seoul_anchor_score": item.get("seoul_anchor_score", 0),
            "other_event_score": item.get("other_event_score", 0),
            "noise_score": item.get("noise_score", 0)
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
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        results = json.loads(response_text)
        return results, None
    except Exception as e:
        return None, str(e)


def apply_ai_classification(items, config):
    """고위험 항목에 대해 Gemini AI 분류를 적용한다."""
    rf = config.get("relevance_filter", {})
    if not rf.get("ambiguous_ai_enabled", False):
        return items
    
    api_key = get_gemini_api_key(config)
    if not api_key:
        return items

    # AI 검토가 필요한 항목 식별
    # 1. weak_match
    # 2. seoul_anchor_score가 낮은데 context(issue/comparison)가 있는 경우
    # 3. 블로그 중 모호한 항목
    ai_candidates = []
    for item in items:
        needed = False
        if item.get("category") == "weak_match":
            needed = True
        elif item.get("category") in ["comparison", "related_issue"] and item.get("seoul_anchor_score", 0) < 2:
            needed = True
        elif item.get("source") == "naver_blog" and item.get("seoul_anchor_score", 0) == 0 and len(item.get("matched_ambiguous_event_terms", [])) > 0:
            needed = True
        
        if needed:
            item["ai_needed"] = True
            item["risk_score"] = calculate_risk_score(item)
            ai_candidates.append(item)
    
    if not ai_candidates:
        return items

    # 리스크 점수 순으로 정렬 후 상위 N건만 처리
    max_items = rf.get("max_ai_items_per_run", 50)
    ai_candidates.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    
    items_to_process = ai_candidates[:max_items]
    skipped_items = ai_candidates[max_items:]
    
    for item in skipped_items:
        item["ai_used"] = False
        item["ai_reason"] = "skipped_due_to_limit"

    if not items_to_process:
        return items

    logger.info(f"Gemini AI Batch classification: {len(items_to_process)} items to classify (Max: {max_items})")
    
    batch_size = rf.get("ai_batch_size", 10)
    for i in range(0, len(items_to_process), batch_size):
        batch = items_to_process[i:i+batch_size]
        results, error = _call_gemini_batch(batch, api_key)
        
        if error:
            for item in batch:
                item["ai_used"] = False
                item["ai_reason"] = f"api_error: {error}"
            continue

        for res in results:
            try:
                idx = int(res.get("id", -1))
                if 0 <= idx < len(batch):
                    item = batch[idx]
                    ai_result = res.get("result", "uncertain")
                    ai_category = res.get("category", "weak_match")
                    
                    item["ai_used"] = True
                    item["ai_result"] = ai_result
                    item["ai_category"] = ai_category
                    item["ai_reason"] = res.get("reason", "")
                    
                    # 2차 판별 결과에 따른 카테고리 갱신
                    if ai_result == "irrelevant":
                        item["category"] = "ai_irrelevant"
                        item["filter_status"] = "excluded"
                        item["public_visible_default"] = False
                    elif ai_result == "relevant":
                        item["category"] = ai_category
                        item["filter_status"] = "kept"
                        item["public_visible_default"] = True
                    else:
                        item["category"] = "weak_match"
                        item["filter_status"] = "review"
                        item["public_visible_default"] = False
            except:
                continue
        
        time.sleep(0.5)

    return items
