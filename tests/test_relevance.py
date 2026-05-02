import pytest
import json
from processors.relevance import classify_relevance

# Mock config
mock_config = {
    "relevance_filter": {
        "enabled": True,
        "official_event_terms": ["서울국제정원박람회", "서울정원박람회"],
        "location_anchor_terms": ["서울숲", "뚝섬", "성수동"],
        "program_anchor_terms": ["포켓몬", "시크릿 포레스트"],
        "ambiguous_event_terms": ["국제정원박람회", "정원박람회"],
        "other_event_terms": ["순천", "태안", "고양", "울산", "도시재생", "파크골프장", "원예"],
        "noise_terms": ["주차", "입장료", "추천", "예약", "가이드", "코스", "꿀팁"],
        "political_terms": ["오세훈", "서울시"],
        "issue_terms": ["인파", "대기", "마감"],
        "politician_terms": {},
        "blog_requires_seoul_anchor": True,
        "classification_policy_version": "2026-05-v2-test"
    }
}

@pytest.mark.parametrize("title, source, expected_status, expected_cat, desc", [
    # Public 제외 필수
    ("쓰레기 매립지에서 명품 파크골프장으로…울산, 도시 재생의 새로운 모델 제시", "naver_news", "excluded", "other_event_only", "울산/파크골프 단독"),
    ("순천민박 2026년 추천 5곳 빠른 예약 가이드", "naver_blog", "excluded", "other_event_only", "순천/민박 단독"),
    ("태안 국제 원예 치유박람회 주차부터 입장료, 티니핑과 함께하는...", "naver_blog", "excluded", "other_event_only", "태안/원예 단독"),
    ("고양국제꽃박람회 우천 한정 이벤트", "naver_news", "excluded", "other_event_only", "고양 단독"),
    ("정원박람회 추천 여행 코스", "naver_blog", "excluded", "irrelevant", "모호한 블로그 (서울앵커없음)"),
    ("울산 도시재생 공원화 사업 명품 파크골프장", "naver_news", "excluded", "other_event_only", "울산/파크골프 단독"),

    # Public 노출 필수
    ("서울숲 2026 서울국제정원박람회 개막 첫날 30만명", "naver_news", "kept", "confirmed", "서울 공식행사"),
    ("포켓몬 시크릿 포레스트 서울국제정원박람회 연계", "naver_news", "kept", "confirmed", "서울 연계프로그램"),
    ("성수동 서울숲 정원박람회 방문 후기", "naver_blog", "kept", "confirmed", "서울 장소 앵커"),
    ("서울국제정원박람회와 고양국제꽃박람회 비교", "naver_news", "kept", "comparison", "비교 글"),
    ("서울국제정원박람회 주차 입장료 추천 코스 총정리", "naver_blog", "kept", "confirmed", "서울 행사 가이드"),
    ("서울숲 정원박람회 주차 꿀팁", "naver_blog", "kept", "confirmed", "서울 행사 주차"),
    ("성수동 서울국제정원박람회 방문 후기 추천", "naver_blog", "kept", "confirmed", "서울 행사 추천")
])
def test_relevance_cases(title, source, expected_status, expected_cat, desc):
    item = {
        "title": title,
        "description": f"This is a description about {title}",
        "source": source,
        "author_or_channel": "test_user",
        "canonical_url": f"https://example.com/{title}"
    }
    
    result = classify_relevance(item, mock_config)
    
    assert result["filter_status"] == expected_status, f"Failed: {title} ({desc})"
    assert result["category"] == expected_cat, f"Failed Category: {title} ({desc})"
