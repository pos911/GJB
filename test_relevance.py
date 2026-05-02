"""
검증 스크립트: 사용자 요구 12개 시나리오 검증
"""
import sys
import json

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')
from processors.relevance import classify_relevance, normalize_text, match_terms

# config 로드
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# ── 테스트 케이스 ──
tests = [
    {
        "name": "1. 서울국제정원박람회 개막",
        "item": {
            "title": "서울국제정원박람회 개막",
            "description": "2026 서울국제정원박람회가 서울숲에서 개막했다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/1"
        },
        "expected_category": "confirmed",
        "expected_public": True
    },
    {
        "name": "2. 서울숲 국제정원박람회와 고양꽃박람회 비교",
        "item": {
            "title": "서울숲 국제정원박람회와 고양꽃박람회 비교",
            "description": "올해 두 박람회를 비교해본다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/2"
        },
        "expected_category": "confirmed",  # strong_keep_term "서울숲 국제정원박람회" 매칭 가능, 또는 confirmed (event+location)
        "expected_public": True
    },
    {
        "name": "3. 고양국제꽃박람회 방문 후기",
        "item": {
            "title": "고양국제꽃박람회 방문 후기",
            "description": "일산호수공원에서 열린 꽃박람회에 다녀왔습니다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/3"
        },
        "expected_category": "other_event_only",
        "expected_public": False
    },
    {
        "name": "4. 오세훈, 서울국제정원박람회 참석",
        "item": {
            "title": "오세훈, 서울국제정원박람회 참석",
            "description": "서울시장이 박람회 개막식에 참석했다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/4"
        },
        "expected_category": "confirmed",  # strong_keep_term 매칭
        "expected_public": True
    },
    {
        "name": "5. 정원오 후보, 서울숲 관련 발언",
        "item": {
            "title": "정원오 후보, 서울숲 관련 발언",
            "description": "성동구청장 후보가 서울숲 정책을 발표했다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/5"
        },
        "expected_category": "political_context",
        "expected_public": True
    },
    {
        "name": "6. 구청장, 서울국제정원박람회 참석",
        "item": {
            "title": "구청장, 서울국제정원박람회 참석",
            "description": "성동구청장이 박람회에 참석했다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/6"
        },
        "expected_category": "confirmed",  # strong_keep_term 매칭
        "expected_public": True
    },
    {
        "name": "7. 포켓몬 행사에 성수동 인파 몰려",
        "item": {
            "title": "포켓몬 행사에 성수동 인파 몰려",
            "description": "서울국제정원박람회 포켓몬 시크릿 포레스트 행사에 인파가 몰렸다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/7"
        },
        "expected_category": "confirmed",  # description에 서울국제정원박람회가 있으므로 strong_keep_term
        "expected_public": True
    },
    {
        "name": "8. 국제정원박람회 일정 정리 (장소 단서 없음)",
        "item": {
            "title": "국제정원박람회 일정 정리",
            "description": "올해 열리는 국제정원박람회 일정을 정리합니다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/8"
        },
        "expected_category": "weak_match",
        "expected_public": True
    },
    {
        "name": "9. 순천만국제정원박람회 후기",
        "item": {
            "title": "순천만국제정원박람회 후기",
            "description": "순천만에서 열린 정원박람회를 다녀왔습니다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/9"
        },
        "expected_category": "comparison",  # target_terms(정원박람회) + other(순천만)
        "expected_public": True
    },
    {
        "name": "10. 완전 무관 글",
        "item": {
            "title": "주식 시장 동향 분석",
            "description": "코스피 지수가 하락했다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/10"
        },
        "expected_category": "irrelevant",
        "expected_public": False
    },
    {
        "name": "11. 타 행사 + 서울국제정원박람회 비교",
        "item": {
            "title": "고양꽃박람회 vs 국제정원박람회",
            "description": "두 행사를 비교해본다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/11"
        },
        "expected_category": "comparison",
        "expected_public": True
    },
    {
        "name": "12. 포켓몬 시크릿 포레스트 단독",
        "item": {
            "title": "포켓몬 시크릿 포레스트 개장",
            "description": "서울숲에서 포켓몬 행사가 열립니다",
            "author_or_channel": "",
            "canonical_url": "https://example.com/12"
        },
        "expected_category": "related_issue",  # target_terms(서울숲, 포켓몬 시크릿 포레스트) + issue_terms(포켓몬)
        "expected_public": True
    }
]

print("=" * 70)
print("검색 결과 필터링 검증 시나리오")
print("=" * 70)

passed = 0
failed = 0

for test in tests:
    result = classify_relevance(test["item"], config)
    category = result["category"]
    public = result["public_visible_default"]
    
    cat_ok = category == test["expected_category"]
    pub_ok = public == test["expected_public"]
    
    status = "✅ PASS" if (cat_ok and pub_ok) else "❌ FAIL"
    
    if cat_ok and pub_ok:
        passed += 1
    else:
        failed += 1
    
    print(f"\n{status} {test['name']}")
    print(f"  Category: {category} (expected: {test['expected_category']}) {'✓' if cat_ok else '✗'}")
    print(f"  Public:   {public} (expected: {test['expected_public']}) {'✓' if pub_ok else '✗'}")
    print(f"  Reason:   {result['filter_reason']}")
    if result.get('matched_target_terms'):
        print(f"  Target:   {result['matched_target_terms']}")
    if result.get('matched_other_event_terms'):
        print(f"  Other:    {result['matched_other_event_terms']}")
    if result.get('matched_political_terms'):
        print(f"  Political: {result['matched_political_terms']}")
    if result.get('matched_issue_terms'):
        print(f"  Issue:    {result['matched_issue_terms']}")

print(f"\n{'=' * 70}")
print(f"결과: {passed} passed, {failed} failed / {len(tests)} total")
print(f"{'=' * 70}")

if failed > 0:
    sys.exit(1)
