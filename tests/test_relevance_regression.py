import json
import pytest
from processors.relevance import classify_relevance

# Mock Config
MOCK_CONFIG = {
    "relevance_filter": {
        "enabled": True,
        "classification_policy_version": "2026-05-seoul-anchor-v1",
        "official_event_terms": ["서울국제정원박람회", "2026 서울국제정원박람회"],
        "location_anchor_terms": ["서울숲", "성동구", "성수동", "뚝섬"],
        "program_anchor_terms": ["포켓몬 시크릿 포레스트", "포켓몬 정원"],
        "ambiguous_event_terms": ["국제정원박람회", "정원박람회"],
        "other_event_terms": ["순천", "순천만", "순천만국제정원박람회", "고양국제꽃박람회", "태안", "울산"],
        "noise_terms": ["파크골프장", "도시재생", "쓰레기 매립지", "민박", "주차", "입장료", "예약", "추천", "가이드", "코스"],
        "issue_terms": ["포켓몬", "인파", "혼잡", "행사 중단"],
        "blog_requires_seoul_anchor": True
    }
}

TEST_CASES = [
    # 반드시 제외되는 케이스
    {
        "title": "쓰레기 매립지에서 명품 파크골프장으로…울산, 도시 재생의 새로운 모델 제시",
        "description": "울산의 새로운 공원화 사업을 소개합니다.",
        "source": "naver_news",
        "expected_status": "excluded",
        "note": "울산 + 파크골프장 + 도시재생 (서울 앵커 없음)"
    },
    {
        "title": "순천민박 2026년 추천 5곳 빠른 예약 가이드",
        "description": "순천만국제정원박람회 인근 숙소 정보",
        "source": "naver_blog",
        "expected_status": "excluded",
        "note": "순천 + 민박 (서울 앵커 없음)"
    },
    {
        "title": "태안 국제 원예 치유박람회 주차부터 입장료, 티니핑과 함께하는...",
        "description": "태안의 원예박람회 방문 정보",
        "source": "naver_news",
        "expected_status": "excluded",
        "note": "태안 + 원예 (서울 앵커 없음)"
    },
    {
        "title": "정원박람회 추천 여행 코스",
        "description": "다양한 박람회 코스를 소개합니다.",
        "source": "naver_blog",
        "expected_status": "excluded",
        "note": "서울 앵커 없는 블로그 정원박람회"
    },
    
    # 반드시 노출되는 케이스
    {
        "title": "서울숲 2026 서울국제정원박람회 개막 첫날 30만명",
        "description": "현장의 열기를 전해드립니다.",
        "source": "naver_news",
        "expected_status": "kept",
        "expected_category": "confirmed",
        "note": "서울숲 + 공식명칭"
    },
    {
        "title": "포켓몬 시크릿 포레스트 서울국제정원박람회 연계",
        "description": "서울숲에서 열리는 포켓몬 행사",
        "source": "naver_news",
        "expected_status": "kept",
        "expected_category": "related_issue",
        "note": "프로그램 앵커 + 공식명칭"
    },
    {
        "title": "성수동 서울숲 정원박람회 방문 후기",
        "description": "주말 데이트 코스로 다녀왔습니다.",
        "source": "naver_blog",
        "expected_status": "kept",
        "expected_category": "confirmed",
        "note": "성수동 + 서울숲 (서울 앵커 확실한 블로그)"
    },
    {
        "title": "서울국제정원박람회 주차 입장료 추천 코스 총정리",
        "description": "방문 전 꼭 확인하세요.",
        "source": "naver_news",
        "expected_status": "kept",
        "note": "공식명칭이 있으므로 주차/입장료/추천 코스가 있어도 생존"
    }
]

@pytest.mark.parametrize("case", TEST_CASES)
def test_relevance_logic(case):
    item = {
        "title": case["title"],
        "description": case["description"],
        "source": case["source"]
    }
    result = classify_relevance(item, MOCK_CONFIG)
    
    assert result["filter_status"] == case["expected_status"], f"Failed: {case['note']}"
    if "expected_category" in case:
        assert result["category"] == case["expected_category"], f"Category mismatch: {case['note']}"

if __name__ == "__main__":
    # 직접 실행시 결과 출력
    for case in TEST_CASES:
        item = {
            "title": case["title"],
            "description": case["description"],
            "source": case["source"]
        }
        res = classify_relevance(item, MOCK_CONFIG)
        print(f"[{'PASS' if res['filter_status'] == case['expected_status'] else 'FAIL'}] {case['title']}")
        print(f"  - Result: status={res['filter_status']}, cat={res['category']}, reason={res['filter_reason']}")
        print(f"  - Scores: seoul={res['seoul_anchor_score']}, other={res['other_event_score']}, noise={res['noise_score']}")
