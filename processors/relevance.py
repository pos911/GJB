"""
Rule-based relevance classifier for collected search results.

The classifier keeps every result in the audit trail, but only public-facing
categories are exported to details JSON. Context categories take priority over
plain confirmed so "confirmed" stays close to pure event coverage.
"""
import html
import re


def normalize_text(text):
    """Normalize text for case-insensitive substring matching."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ").replace("\u3000", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def match_terms(text, terms):
    """Return configured terms contained in text."""
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
    """Return politician term matches grouped by configured key."""
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
    parts = [
        item.get("title", ""),
        item.get("description", ""),
        item.get("author_or_channel", ""),
        item.get("canonical_url", ""),
    ]
    return " ".join(parts)


def classify_relevance(item, config):
    """
    Classify one item.

    Priority:
    1. Other-event only -> excluded
    2. Weak garden-expo-only signal -> review/AI candidate
    3. Target event with context -> comparison, political_context, related_issue
    4. Target event without context -> confirmed
    5. No signal -> irrelevant
    """
    rf = config.get("relevance_filter", {})
    combined_text = _build_combined_text(item)

    matched_strong = match_terms(combined_text, rf.get("strong_keep_terms", []))
    matched_target = match_terms(combined_text, rf.get("target_terms", []))
    matched_other = match_terms(combined_text, rf.get("other_event_terms", []))
    matched_political = match_terms(combined_text, rf.get("political_terms", []))
    matched_issue = match_terms(combined_text, rf.get("issue_terms", []))
    matched_politician = match_politician_terms(combined_text, rf.get("politician_terms", {}))
    has_politician = any(bool(terms) for terms in matched_politician.values())

    location_terms = [
        "서울숲",
        "성동구",
        "성수동",
        "뚝섬",
        "광진구",
        "건대입구",
        "정원전시 서울",
    ]
    garden_expo_terms = ["국제정원박람회", "정원박람회"]
    matched_location = match_terms(combined_text, location_terms)
    matched_garden_expo = match_terms(combined_text, garden_expo_terms)

    result = {
        "matched_target_terms": matched_target,
        "matched_other_event_terms": matched_other,
        "matched_political_terms": matched_political,
        "matched_issue_terms": matched_issue,
        "matched_politician_terms": matched_politician,
        "relevance_score": len(matched_target),
        "category": "irrelevant",
        "filter_status": "excluded",
        "filter_reason": "no_relevant_signal",
        "ai_needed": False,
        "ai_used": False,
        "ai_category": "",
        "ai_reason": "",
        "public_visible_default": False,
    }

    has_strong = bool(matched_strong)
    has_event_and_location = bool(matched_garden_expo) and bool(matched_location)
    has_context = bool(matched_other or matched_political or matched_issue or has_politician)

    garden_expo_only_terms = {"국제정원박람회", "정원박람회"}
    target_beyond_expo = [term for term in matched_target if term not in garden_expo_only_terms]
    weak_target_only = (
        bool(matched_garden_expo)
        and not matched_location
        and not has_strong
        and not target_beyond_expo
    )

    is_target_event = (
        has_strong
        or has_event_and_location
        or bool(target_beyond_expo)
        or (bool(matched_target) and (has_context or not weak_target_only))
    )

    if matched_other and not is_target_event:
        result["category"] = "other_event_only"
        result["filter_status"] = "excluded"
        result["filter_reason"] = "only_other_event_matched"
        result["public_visible_default"] = False
        return result

    if weak_target_only and not has_context:
        result["category"] = "weak_match"
        result["filter_status"] = "review"
        result["filter_reason"] = "weak_target_signal"
        result["ai_needed"] = True
        result["public_visible_default"] = True
        return result

    if is_target_event:
        result["filter_status"] = "kept"
        result["ai_needed"] = False
        result["public_visible_default"] = True

        if matched_other:
            result["category"] = "comparison"
            result["filter_reason"] = "target_event_and_other_event_both_matched"
        elif matched_political or has_politician:
            result["category"] = "political_context"
            result["filter_reason"] = "target_event_with_political_context"
        elif matched_issue:
            result["category"] = "related_issue"
            result["filter_reason"] = "target_event_with_related_issue"
        else:
            result["category"] = "confirmed"
            result["filter_reason"] = "target_event_confirmed"
        return result

    return result


def apply_relevance_classification(items, config):
    """Apply relevance classification to every item."""
    rf = config.get("relevance_filter", {})
    if not rf.get("enabled", False):
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
        item.update(classify_relevance(item, config))

    return items
