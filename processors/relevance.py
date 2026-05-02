"""
processors/relevance.py
규칙 기반 검색 결과 관련성 분류 모듈.

검색 결과를 서울국제정원박람회 관련도 기준으로 8단계 우선순위로 분류한다.
- confirmed: 확정 관련
- comparison: 타 행사 비교/연관
- related_issue: 연계 이슈
- political_context: 정치/선거 맥락
- weak_match: 약한 신호 (AI 2차 판별 대상)
- other_event_only: 타 행사 단독
- irrelevant: 무관
- ai_irrelevant: AI가 무관으로 판정
"""
import re
import html


def normalize_text(text):
    """
    텍스트 정규화:
    - HTML 태그 제거
    - HTML entity 정리
    - 특수 공백 정리
    - 연속 공백 제거
    - 영문 소문자 변환
    """
    if not text:
        return ""
    # HTML entity 디코딩
    text = html.unescape(text)
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 특수 공백 정리 (NBSP, 전각 공백 등)
    text = text.replace('\xa0', ' ').replace('\u3000', ' ').replace('\t', ' ')
    # 연속 공백 제거
    text = re.sub(r'\s+', ' ', text).strip()
    # 영문 소문자 변환
    text = text.lower()
    return text


def match_terms(text, terms):
    """
    text에 포함된 terms 목록을 반환한다.
    한글은 대소문자 영향 없지만 영문 혼용 대비 normalize_text 기준으로 비교.
    """
    if not text or not terms:
        return []
    normalized = normalize_text(text)
    matched = []
    for term in terms:
        normalized_term = normalize_text(term)
        if normalized_term and normalized_term in normalized:
            matched.append(term)
    return matched


def match_politician_terms(text, politician_terms):
    """
    정치인별 매칭 결과를 dict로 반환.
    politician_terms: {"oh_sehoon": ["오세훈"], "jung_wonoh": ["정원오"], ...}
    반환 예: {"oh_sehoon": ["오세훈"], "jung_wonoh": [], ...}
    """
    if not text or not politician_terms:
        return {}
    normalized = normalize_text(text)
    result = {}
    for key, terms in politician_terms.items():
        matched = []
        for term in terms:
            normalized_term = normalize_text(term)
            if normalized_term and normalized_term in normalized:
                matched.append(term)
        result[key] = matched
    return result


def _build_combined_text(item):
    """item의 title, description, author_or_channel, canonical_url을 합쳐 반환."""
    parts = [
        item.get("title", ""),
        item.get("description", ""),
        item.get("author_or_channel", ""),
        item.get("canonical_url", "")
    ]
    return " ".join(parts)


def classify_relevance(item, config):
    """
    item을 규칙 기반으로 관련성 분류한다.
    
    판단 우선순위:
    1. strong_keep_terms 매칭 → confirmed
    2. 정원박람회 + 서울 장소 → confirmed
    3. target + other_event → comparison
    4. target + issue → related_issue
    5. target + political → political_context
    6. other_event only → other_event_only
    7. 국제정원박람회만 (장소 단서 없음) → weak_match
    8. 어느 것도 아님 → irrelevant
    """
    rf = config.get("relevance_filter", {})
    
    combined_text = _build_combined_text(item)
    
    # 각 term 그룹 매칭
    matched_strong = match_terms(combined_text, rf.get("strong_keep_terms", []))
    matched_target = match_terms(combined_text, rf.get("target_terms", []))
    matched_other = match_terms(combined_text, rf.get("other_event_terms", []))
    matched_political = match_terms(combined_text, rf.get("political_terms", []))
    matched_issue = match_terms(combined_text, rf.get("issue_terms", []))
    matched_politician = match_politician_terms(combined_text, rf.get("politician_terms", {}))
    
    # relevance_score 계산 (매칭된 target_terms 개수)
    relevance_score = len(matched_target)
    
    # 기본 반환 구조
    result = {
        "matched_target_terms": matched_target,
        "matched_other_event_terms": matched_other,
        "matched_political_terms": matched_political,
        "matched_issue_terms": matched_issue,
        "matched_politician_terms": matched_politician,
        "relevance_score": relevance_score,
        "category": "irrelevant",
        "filter_status": "excluded",
        "filter_reason": "no_relevant_signal",
        "ai_needed": False,
        "ai_used": False,
        "ai_category": "",
        "ai_reason": "",
        "public_visible_default": False
    }
    
    # 장소 단서 목록
    location_terms = ["서울숲", "성동구", "성수동", "뚝섬", "광진구", "건대입구", "정원도시 서울"]
    matched_location = match_terms(combined_text, location_terms)
    
    # 정원박람회 관련 용어
    garden_expo_terms = ["국제정원박람회", "정원박람회"]
    matched_garden_expo = match_terms(combined_text, garden_expo_terms)
    
    # ── 1. strong_keep_terms 매칭 ──
    if matched_strong:
        result["category"] = "confirmed"
        result["filter_status"] = "kept"
        result["filter_reason"] = "strong_keep_term_matched"
        result["ai_needed"] = False
        result["public_visible_default"] = True
        return result
    
    # ── 2. 정원박람회 + 서울 장소 매칭 ──
    if matched_garden_expo and matched_location:
        result["category"] = "confirmed"
        result["filter_status"] = "kept"
        result["filter_reason"] = "event_and_location_matched"
        result["ai_needed"] = False
        result["public_visible_default"] = True
        return result
    
    # ── 3. target + other_event → comparison ──
    if matched_target and matched_other:
        result["category"] = "comparison"
        result["filter_status"] = "kept"
        result["filter_reason"] = "target_event_and_other_event_both_matched"
        result["ai_needed"] = False
        result["public_visible_default"] = True
        return result
    
    # ── 4. target + issue → related_issue ──
    if matched_target and matched_issue:
        result["category"] = "related_issue"
        result["filter_status"] = "kept"
        result["filter_reason"] = "target_event_with_related_issue"
        result["ai_needed"] = False
        result["public_visible_default"] = True
        return result
    
    # ── 5. target + political → political_context ──
    if matched_target and matched_political:
        result["category"] = "political_context"
        result["filter_status"] = "kept"
        result["filter_reason"] = "target_event_with_political_context"
        result["ai_needed"] = False
        result["public_visible_default"] = True
        return result
    
    # ── 6. other_event only (target 없음) → other_event_only ──
    if matched_other and not matched_target:
        result["category"] = "other_event_only"
        result["filter_status"] = "excluded"
        result["filter_reason"] = "only_other_event_matched"
        result["ai_needed"] = False
        result["public_visible_default"] = False
        return result
    
    # ── 7. 국제정원박람회만 있고 장소 단서 없음 → weak_match ──
    if matched_garden_expo and not matched_location:
        result["category"] = "weak_match"
        result["filter_status"] = "review"
        result["filter_reason"] = "weak_target_signal"
        result["ai_needed"] = True
        result["public_visible_default"] = True
        return result
    
    # ── 8. 어떤 조건에도 안 걸림 → irrelevant ──
    # (result는 이미 irrelevant 기본값으로 설정됨)
    return result


def apply_relevance_classification(items, config):
    """
    전체 item 목록에 classify_relevance를 적용하고,
    각 item에 분류 결과 필드를 추가한다.
    """
    rf = config.get("relevance_filter", {})
    if not rf.get("enabled", False):
        # 필터 비활성화 시 모든 item을 confirmed로 처리
        for item in items:
            item["category"] = "confirmed"
            item["filter_status"] = "kept"
            item["filter_reason"] = "filter_disabled"
            item["matched_target_terms"] = []
            item["matched_other_event_terms"] = []
            item["matched_political_terms"] = []
            item["matched_issue_terms"] = []
            item["matched_politician_terms"] = {}
            item["relevance_score"] = 0
            item["ai_needed"] = False
            item["ai_used"] = False
            item["ai_category"] = ""
            item["ai_reason"] = ""
            item["public_visible_default"] = True
        return items
    
    for item in items:
        classification = classify_relevance(item, config)
        item.update(classification)
    
    return items
