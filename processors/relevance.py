"""
processors/relevance.py
규칙 기반 검색 결과 관련성 분류 모듈.

검색 결과를 서울국제정원박람회 관련도 기준으로 8단계 카테고리로 분류한다.
- confirmed: 순수 행사 관련 (정치/이슈/타행사 맥락 없이 본행사만 다루는 글)
- comparison: 타 행사(고양꽃박람회 등)와 본행사를 함께 다루는 글
- related_issue: 포켓몬/인파/혼잡 등 행사 연계 이슈
- political_context: 오세훈/정원오/구청장/선거 등 정치 맥락에서 행사를 언급하는 글
- weak_match: 약한 신호 (AI 2차 판별 대상) — 국제정원박람회만 있고 장소 단서 없음
- other_event_only: 타 행사 단독 (본행사 관련성 없음)
- irrelevant: 어떤 관련 키워드도 매칭되지 않음
- ai_irrelevant: AI가 무관으로 판정 (ai_classifier에서 설정)

분류 로직:
1. is_target_event를 먼저 계산:
   - strong_keep_terms 매칭 OR (정원박람회 + 장소 단서) OR matched_target_terms 존재
   - 단, matched_target_terms가 "국제정원박람회/정원박람회"만이고 장소 단서 없으면 weak_match
2. is_target_event가 true이면 맥락 카테고리 우선:
   a. matched_other_event_terms가 있으면 → comparison
   b. matched_political_terms가 있으면 → political_context
   c. matched_issue_terms가 있으면 → related_issue
   d. 위 맥락이 없으면 → confirmed
3. is_target_event가 false이면:
   - matched_other_event_terms만 있으면 → other_event_only
   - 아무 단서 없으면 → irrelevant
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

    맥락 카테고리 우선 원칙:
    - is_target_event가 true인 상태에서:
      1) other_event_terms → comparison
      2) political_terms → political_context
      3) issue_terms → related_issue
      4) 맥락 없음 → confirmed
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

    # 정원박람회 관련 일반 용어 (strong이 아닌)
    garden_expo_terms = ["국제정원박람회", "정원박람회"]
    matched_garden_expo = match_terms(combined_text, garden_expo_terms)

    # ── is_target_event 판단 ──
    has_strong = bool(matched_strong)
    has_event_and_location = bool(matched_garden_expo) and bool(matched_location)

    # matched_target_terms가 정원박람회 계열만이고 장소 단서가 없으면 weak 후보
    garden_expo_only_terms = {"국제정원박람회", "정원박람회"}
    target_beyond_expo = [t for t in matched_target if t not in garden_expo_only_terms]
    has_target_beyond_expo = bool(target_beyond_expo)

    is_target_event = has_strong or has_event_and_location or has_target_beyond_expo

    # ── 카테고리 결정 ──
    if is_target_event:
        # 맥락 카테고리 우선 (comparison > political_context > related_issue > confirmed)
        if matched_other:
            result["category"] = "comparison"
            result["filter_status"] = "kept"
            result["filter_reason"] = "target_event_and_other_event_both_matched"
            result["public_visible_default"] = True
        elif matched_political:
            result["category"] = "political_context"
            result["filter_status"] = "kept"
            result["filter_reason"] = "target_event_with_political_context"
            result["public_visible_default"] = True
        elif matched_issue:
            result["category"] = "related_issue"
            result["filter_status"] = "kept"
            result["filter_reason"] = "target_event_with_related_issue"
            result["public_visible_default"] = True
        else:
            result["category"] = "confirmed"
            result["filter_status"] = "kept"
            result["filter_reason"] = "strong_keep_term_matched" if has_strong else "event_and_location_matched" if has_event_and_location else "target_terms_matched"
            result["public_visible_default"] = True
        return result

    # ── is_target_event가 false인 경우 ──

    # 정원박람회만 있고 장소 단서 없음 → weak_match
    if matched_garden_expo and not matched_location:
        # other_event가 함께 있으면 comparison (약한 target + other)
        if matched_other:
            result["category"] = "comparison"
            result["filter_status"] = "kept"
            result["filter_reason"] = "target_event_and_other_event_both_matched"
            result["public_visible_default"] = True
            return result

        result["category"] = "weak_match"
        result["filter_status"] = "review"
        result["filter_reason"] = "weak_target_signal"
        result["ai_needed"] = True
        result["public_visible_default"] = True
        return result

    # other_event만 있고 target 없음 → other_event_only
    if matched_other and not matched_target:
        result["category"] = "other_event_only"
        result["filter_status"] = "excluded"
        result["filter_reason"] = "only_other_event_matched"
        result["public_visible_default"] = False
        return result

    # 어떤 조건에도 안 걸림 → irrelevant
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
