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
   - 주차/입장료/추천/예약/가이드/코스 등 방문 정보가 서울 행사와 연결됨
2. Irrelevant 조건:
   - 타 지역(순천, 고양, 태안, 울산 등)의 정원/꽃 박람회 단독 글
   - 도시재생, 파크골프장, 쓰레기 매립지 공원화 등 박람회와 무관한 공원 조성 글
   - 서울국제정원박람회와 명시적 연결이 없는 일반 여행/숙박/맛집 정보
   - 서울 앵커(장소/명칭)가 없고 일반적인 '정원박람회' 키워드만 있는 글
3. Comparison 조건:
   - 서울국제정원박람회와 타 행사(고양꽃박람회 등)가 제목/본문에서 함께 언급되거나 실제 비교되는 경우에만 해당함.

[주의사항]
- '관련 있을 수도 있음'이라는 추론은 배제하고 명시적 근거로만 판단하십시오.
- 서울 앵커가 없고 타 지역/도시재생/파크골프장/숙박/여행성 문맥이면 반드시 irrelevant입니다.
- 주차/입장료/추천/예약/가이드/코스는 서울 앵커가 있을 때는 정상 방문 정보로 간주하십시오.
- 애매하면 'relevant'가 아니라 'uncertain' 또는 'irrelevant'로 답하십시오.

[반환 형식]
반드시 아래와 같은 JSON array 형식으로만 응답하십시오. 다른 텍스트는 포함하지 마십시오.
[
  {{
    "id": 0,
    "result": "relevant|irrelevant|uncertain",
    "category": "confirmed|related_issue|comparison|political_context|weak_match|irrelevant",
    "reason": "판단 근거 (1문장)"
  }},
  ...
]

[분류 대상 리스트]
{items_json}"""


def get_gemini_api_key(config):
    """Gemini API 키를 가져온다."""
    # main.py에서 config에 이미 모든 secret이 merge되어 있음
    key = config.get("gemini_api_key")
    if key and key != "YOUR_GEMINI_API_KEY":
        return key
    
    # Fallback to direct environment variables
    key = os.getenv("GEMINI_API_KEY")
    if key and key != "YOUR_GEMINI_API_KEY":
        return key
        
    return None


def calculate_risk_score(item):
    """항목의 위험도/모호성 점수를 계산한다 (AI 우선순위용)."""
    score = 0
    cat = item.get("category")
    seoul_score = item.get("seoul_anchor_score", 0)
    other_score = item.get("other_event_score", 0)
    noise_score = item.get("noise_score", 0)
    
    if cat == "weak_match": score += 10
    if seoul_score == 0: score += 5
    if other_score > 0: score += 5
    if noise_score > 0: score += 3
    if item.get("source") == "naver_blog": score += 2
    
    # 비교/이슈인데 서울 앵커가 약한 경우
    if cat in ["comparison", "related_issue"] and seoul_score < 2:
        score += 7
        
    return score


def _call_gemini_batch(items_to_send, api_key):
    """Gemini API를 호출하여 배치 결과를 반환한다."""
    try:
        from google import genai
    except ImportError:
        return None, "google-genai package not installed"
    
    formatted_items = []
    for i, item in enumerate(items_to_send):
        formatted_items.append({
            "id": i,
            "source": item.get("source", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "author_or_channel": item.get("author_or_channel", ""),
            "canonical_url": item.get("canonical_url", ""),
            "category_before_ai": item.get("category", ""),
            "filter_reason": item.get("filter_reason", ""),
            "seoul_anchor_score": item.get("seoul_anchor_score", 0),
            "other_event_score": item.get("other_event_score", 0),
            "noise_score": item.get("noise_score", 0),
            "issue_score": item.get("issue_score", 0),
            "matched_official_event_terms": item.get("matched_official_event_terms", []),
            "matched_location_anchor_terms": item.get("matched_location_anchor_terms", []),
            "matched_program_anchor_terms": item.get("matched_program_anchor_terms", []),
            "matched_ambiguous_event_terms": item.get("matched_ambiguous_event_terms", []),
            "matched_other_event_terms": item.get("matched_other_event_terms", []),
            "matched_other_event_terms_in_main_text": item.get("matched_other_event_terms_in_main_text", []),
            "matched_noise_terms": item.get("matched_noise_terms", []),
            "matched_issue_terms": item.get("matched_issue_terms", [])
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
        logger.warning("Gemini API key missing. Skipping AI classification.")
        return items

    allowed_results = ["relevant", "irrelevant", "uncertain"]
    allowed_categories = ["confirmed", "related_issue", "comparison", "political_context", "weak_match", "irrelevant"]

    # AI 검토 대상 선별
    ai_candidates = []
    for item in items:
        needed = False
        cat = item.get("category")
        seoul_score = item.get("seoul_anchor_score", 0)
        other_score = item.get("other_event_score", 0)
        
        # 1. weak_match는 무조건 검토
        if cat == "weak_match":
            needed = True
        # 2. comparison인데 타지역 점수가 높음 (진짜 비교인지 확인)
        elif cat == "comparison" and other_score > 0:
            needed = True
        # 3. related_issue인데 서울 앵커가 없음
        elif cat == "related_issue" and seoul_score == 0:
            needed = True
        # 4. 블로그인데 서울 앵커 없고 모호한 용어 존재
        elif item.get("source") == "naver_blog" and seoul_score == 0 and len(item.get("matched_ambiguous_event_terms", [])) > 0:
            needed = True
        # 5. 비교 근거가 약한 경우 (relevance.py에서 ai_needed=True로 설정됨)
        elif item.get("ai_needed"):
            needed = True
            
        # 제외 조건: 서울 앵커가 확실하고 노이즈가 없으며 이미 확실한 카테고리인 경우 스킵
        if seoul_score > 0 and other_score == 0 and item.get("noise_score", 0) == 0:
            if cat in ["confirmed", "related_issue"]:
                needed = False

        if needed:
            item["ai_needed"] = True
            item["risk_score"] = calculate_risk_score(item)
            ai_candidates.append(item)
    
    if not ai_candidates:
        return items

    # 리스크 점수 순 정렬 후 상위 N건만 처리
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
            logger.error(f"Gemini API error: {error}")
            for item in batch:
                item["ai_used"] = False
                item["ai_reason"] = f"api_error: {error}"
            continue

        # 결과 매핑 및 검증
        for res in results:
            try:
                idx = int(res.get("id", -1))
                if 0 <= idx < len(batch):
                    item = batch[idx]
                    ai_result = res.get("result", "uncertain")
                    ai_category = res.get("category", "weak_match")
                    
                    # 반환값 검증
                    if ai_result not in allowed_results:
                        ai_result = "uncertain"
                    if ai_category not in allowed_categories:
                        ai_category = "weak_match"
                        item["ai_reason_internal"] = "invalid_ai_category"
                    
                    item["ai_used"] = True
                    item["ai_result"] = ai_result
                    item["ai_category"] = ai_category
                    item["ai_reason"] = res.get("reason", "")
                    
                    # AI 판별 결과에 따른 카테고리/상태 갱신
                    if ai_result == "irrelevant":
                        item["category"] = "ai_irrelevant"
                        item["filter_status"] = "excluded"
                        item["public_visible_default"] = False
                    elif ai_result == "relevant":
                        item["category"] = ai_category
                        # Category가 public 허용값이 아니면 노출 안함
                        if ai_category in ["confirmed", "related_issue", "comparison", "political_context"]:
                            item["filter_status"] = "kept"
                            item["public_visible_default"] = True
                        else:
                            item["filter_status"] = "review"
                            item["public_visible_default"] = False
                    else:
                        item["category"] = "weak_match"
                        item["filter_status"] = "review"
                        item["public_visible_default"] = False
            except Exception as e:
                logger.warning(f"Error parsing AI result entry: {e}")
                continue
        
        time.sleep(0.5)

    return items
