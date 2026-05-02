"""
processors/relevance.py
점수 기반 서울국제정원박람회 관련성 판별 모듈.

서울 앵커(공식명칭, 장소, 프로그램) 점수를 기반으로 1차 분류를 수행하고,
AI 검토가 필요한 항목을 선별한다.
"""
import html
import re


def normalize_text(text, remove_all_spaces=False):
    """Normalize text for case-insensitive substring matching."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ").replace("\u3000", " ").replace("\t", " ")
    if remove_all_spaces:
        text = re.sub(r"\s+", "", text)
    else:
        text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def match_terms(text, terms):
    """Return configured terms contained in text (space-insensitive)."""
    if not text or not terms:
        return []
    normalized = normalize_text(text, remove_all_spaces=True)
    matched = []
    for term in terms:
        normalized_term = normalize_text(term, remove_all_spaces=True)
        if normalized_term and normalized_term in normalized:
            matched.append(term)
    return matched


def match_politician_terms(text, politician_terms):
    """Return politician term matches grouped by configured key (space-insensitive)."""
    if not text or not politician_terms:
        return {}
    normalized = normalize_text(text, remove_all_spaces=True)
    result = {}
    for key, terms in politician_terms.items():
        matched = []
        for term in terms:
            normalized_term = normalize_text(term, remove_all_spaces=True)
            if normalized_term and normalized_term in normalized:
                matched.append(term)
        result[key] = matched
    return result


def _build_combined_text(item):
    parts = [
        item.get("title", ""),
        item.get("description", ""),
        item.get("author_or_channel", ""),
        item.get("canonical_url", ""),
    ]
    return " ".join(parts)


def classify_relevance(item, config):
    """
    점수 기반 1차 분류.
    """
    rf = config.get("relevance_filter", {})
    combined_text = _build_combined_text(item)
    source = item.get("source", "")

    # 항목별 매칭 수행
    matched_official = match_terms(combined_text, rf.get("official_event_terms", []))
    matched_location = match_terms(combined_text, rf.get("location_anchor_terms", []))
    matched_program = match_terms(combined_text, rf.get("program_anchor_terms", []))
    matched_ambiguous = match_terms(combined_text, rf.get("ambiguous_event_terms", []))
    matched_other = match_terms(combined_text, rf.get("other_event_terms", []))
    matched_noise = match_terms(combined_text, rf.get("noise_terms", []))
    matched_political = match_terms(combined_text, rf.get("political_terms", []))
    matched_issue = match_terms(combined_text, rf.get("issue_terms", []))
    matched_politician = match_politician_terms(combined_text, rf.get("politician_terms", {}))
    has_politician = any(bool(terms) for terms in matched_politician.values())

    # 점수 계산
    seoul_anchor_score = len(matched_official) + len(matched_location) + len(matched_program)
    other_event_score = len(matched_other)
    noise_score = len(matched_noise)
    issue_score = len(matched_issue)
    
    # 결과 초기화
    result = {
        "matched_official_event_terms": matched_official,
        "matched_location_anchor_terms": matched_location,
        "matched_program_anchor_terms": matched_program,
        "matched_ambiguous_event_terms": matched_ambiguous,
        "matched_other_event_terms": matched_other,
        "matched_noise_terms": matched_noise,
        "matched_political_terms": matched_political,
        "matched_issue_terms": matched_issue,
        "matched_politician_terms": matched_politician,
        "seoul_anchor_score": seoul_anchor_score,
        "other_event_score": other_event_score,
        "noise_score": noise_score,
        "issue_score": issue_score,
        "category": "irrelevant",
        "filter_status": "excluded",
        "filter_reason": "no_relevant_signal",
        "ai_needed": False,
        "ai_used": False,
        "ai_category": "",
        "ai_reason": "",
        "public_visible_default": False,
        "classification_policy_version": rf.get("classification_policy_version", "2026-05-v1")
    }

    # 블로그 전용 필터링 (서울 앵커 필수)
    if source == "naver_blog" and rf.get("blog_requires_seoul_anchor", True):
        if seoul_anchor_score == 0:
            if other_event_score > 0:
                result["category"] = "other_event_only"
                result["filter_reason"] = "blog_no_seoul_anchor_with_other_event"
            else:
                result["category"] = "irrelevant"
                result["filter_reason"] = "blog_no_seoul_anchor"
            return result

    # 타 지역 확증 시 제외 (서울 앵커가 없을 때)
    if other_event_score > 0 and seoul_anchor_score == 0:
        result["category"] = "other_event_only"
        result["filter_reason"] = "other_event_score_positive_no_seoul_anchor"
        return result

    # 노이즈 기반 제외 (서울 앵커가 없을 때)
    if noise_score > 0 and seoul_anchor_score == 0:
        # 뉴스인 경우 weak_match로 두어 AI 검토 기회 부여, 블로그는 즉시 제외
        if source == "naver_news":
            result["category"] = "weak_match"
            result["filter_status"] = "review"
            result["ai_needed"] = True
            result["filter_reason"] = "news_noise_with_no_seoul_anchor"
        else:
            result["category"] = "irrelevant"
            result["filter_reason"] = "noise_score_positive_no_seoul_anchor"
        return result

    # 서울 앵커가 있는 경우
    if seoul_anchor_score > 0:
        result["filter_status"] = "kept"
        result["public_visible_default"] = True
        
        # 정치 맥락
        if matched_political or has_politician:
            result["category"] = "political_context"
            result["filter_reason"] = "seoul_anchor_with_political"
        # 이슈/인파 맥락
        elif matched_issue:
            result["category"] = "related_issue"
            result["filter_reason"] = "seoul_anchor_with_issue"
        # 타 지역과 비교 맥락
        elif other_event_score > 0:
            result["category"] = "comparison"
            result["filter_reason"] = "seoul_anchor_with_other_event"
            # 비교 근거가 약하면 AI 검토 요청
            if other_event_score == 1 and len(matched_official) == 0:
                result["ai_needed"] = True
        # 확증된 서울 행사
        else:
            result["category"] = "confirmed"
            result["filter_reason"] = "seoul_anchor_confirmed"
        return result

    # 모호한 표현(정원박람회 등)만 있는 경우
    if matched_ambiguous:
        result["category"] = "weak_match"
        result["filter_status"] = "review"
        result["ai_needed"] = True
        result["filter_reason"] = "ambiguous_terms_only_no_seoul_anchor"
        result["public_visible_default"] = rf.get("weak_match_public_default", False)
        return result

    return result


def apply_relevance_classification(items, config):
    """전체 항목에 대해 관련성 분류 적용."""
    rf = config.get("relevance_filter", {})
    if not rf.get("enabled", False):
        return items

    for item in items:
        item.update(classify_relevance(item, config))

    return items
