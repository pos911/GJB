import os
import json
import logging
import argparse
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collectors.naver import fetch_naver_news, fetch_naver_blog
from collectors.youtube import fetch_youtube_videos
from processors.normalize import normalize_data
from processors.dedupe import deduplicate
from processors.relevance import apply_relevance_classification
from processors.ai_classifier import apply_ai_classification

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path='config.json', secret_path='secret.json'):
    # 1) config.json 로딩
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 2) SECRET_JSON 환경변수 (GitHub Actions)
    secret_json_env = os.getenv("SECRET_JSON")
    if secret_json_env:
        try:
            secrets = json.loads(secret_json_env)
            config.update(secrets)
            logger.info("Merged SECRET_JSON from environment variables.")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid SECRET_JSON environment variable: {e}")
    
    # 3) secret.json (로컬 개발용)
    if os.path.exists(secret_path):
        try:
            with open(secret_path, 'r', encoding='utf-8') as f:
                secrets = json.load(f)
                config.update(secrets)
                logger.info(f"Merged {secret_path} from local filesystem.")
        except Exception as e:
            logger.error(f"Error reading {secret_path}: {e}")
            
    return config

def get_safe_keyword(keyword):
    """
    한글, 영문, 숫자 외 문자는 _로 치환. 연속된 _는 하나로 정리. 앞뒤 _ 제거.
    """
    if not keyword:
        return "default"
    # 한글, 영문, 숫자 외 제거
    safe = re.sub(r'[^가-힣a-zA-Z0-9]', '_', keyword)
    # 연속된 _ 하나로
    safe = re.sub(r'_+', '_', safe)
    # 앞뒤 _ 제거
    return safe.strip('_')

def update_index(index_path, entry):
    """
    web/public/data/index.json을 갱신한다.
    target_date 내림차순 정렬.
    """
    index_data = []
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading index.json: {e}")
            index_data = []
            
    # 기존에 동일 id가 있으면 교체, 없으면 추가
    found = False
    for i, item in enumerate(index_data):
        if item.get("id") == entry["id"]:
            index_data[i] = entry
            found = True
            break
    if not found:
        index_data.append(entry)
        
    # target_date 기준 내림차순 정렬 (동일 날짜면 generated_at 내림차순)
    index_data.sort(key=lambda x: (x.get("target_date", ""), x.get("generated_at", "")), reverse=True)
    
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Updated index.json at {index_path}")

def apply_safety_gate(items, config):
    """
    Gemini 판별 결과 이후 최종 검증 단계.
    """
    rf = config.get("relevance_filter", {})
    if not rf.get("safety_gate_enabled", True):
        return items

    allowed_categories = ["confirmed", "related_issue", "comparison", "political_context"]

    for item in items:
        if item.get("filter_status") == "excluded":
            continue

        seoul_score = item.get("seoul_anchor_score", 0)
        other_score = item.get("other_event_score", 0)
        noise_score = item.get("noise_score", 0)
        source = item.get("source", "")
        ai_result = item.get("ai_result", "")
        category = item.get("category", "")
        
        gate_reason = None
        
        # 1. 카테고리 허용값 검증
        if category not in allowed_categories:
            gate_reason = "safety_gate:invalid_public_category"

        # 2. 블로그인데 서울 앵커가 전혀 없음
        elif source == "naver_blog" and seoul_score == 0:
            gate_reason = "safety_gate:blog_no_seoul_anchor"
            
        # 3. 서울 앵커가 없는데 노이즈나 타지역 점수가 있음
        elif seoul_score == 0 and (other_score > 0 or noise_score > 0):
            gate_reason = "safety_gate:no_seoul_anchor_with_noise_or_other"
            
        # 4. AI 검토 대상이었으나 검증 실패/오류/불확실
        elif item.get("ai_needed") and (not item.get("ai_used") or ai_result != "relevant"):
            gate_reason = "safety_gate:ai_unverified_or_uncertain"

        # 예외: 서울 앵커가 확실하고 가이드 성 정보인 경우 차단 해제 (위 조건들보다 우선 순위 낮음)
        # 하지만 여기서는 위 조건들이 엄격하므로, seoul_score > 0 인 경우는 대부분 통과됨.
        # noise_terms가 '주차/추천' 등만 있는 경우 relevance.py에서 이미 noise_score로 잡히지만 
        # seoul_anchor_score > 0 이면 'kept' 상태로 옴.
        
        if gate_reason:
            # 예외 체크: 서울 앵커가 0보다 크면 2,3번 조건은 해당 안됨. 
            # 1번(카테고리)과 4번(AI)이 주된 차단 요인이 됨.
            if seoul_score > 0:
                # 서울 앵커가 있으면 웬만하면 살려두되, AI가 명시적으로 부적합 판정했거나 카테고리가 이상한 경우만 차단
                if category in allowed_categories and (not item.get("ai_needed") or (item.get("ai_used") and ai_result == "relevant")):
                    gate_reason = None

        if gate_reason:
            item["safety_gate_reason"] = gate_reason
            item["filter_status"] = "excluded"
            item["public_visible_default"] = False
            if ai_result == "relevant":
                item["category"] = "ai_irrelevant"

    return items

def main():
    parser = argparse.ArgumentParser(description='GJB Data Collector Pipeline')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD or "today" or "yesterday")')
    parser.add_argument('--keyword', type=str, help='Search keyword override')
    parser.add_argument('--sources', type=str, help='Comma-separated sources (e.g., youtube,naver_news)')
    parser.add_argument('--max-pages', type=int, help='Max pages override')
    args = parser.parse_args()

    config = load_config()
    kst = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(kst)
    
    target_date = args.date or config.get('target_date', 'today')
    if target_date == 'today':
        target_date = now_kst.strftime('%Y-%m-%d')
    elif target_date == 'yesterday':
        target_date = (now_kst - timedelta(days=1)).strftime('%Y-%m-%d')
    
    search_keyword = args.keyword or config.get('keywords', ['국제정원박람회'])[0]
    safe_keyword = get_safe_keyword(search_keyword)
    sources_to_run = args.sources.split(',') if args.sources else config.get('sources', [])
    
    logger.info(f"Starting data collection for '{search_keyword}' (safe: '{safe_keyword}') on {target_date} (KST)")
    
    all_items = []
    
    if 'naver_news' in sources_to_run:
        res = fetch_naver_news(config, search_keyword, target_date)
        all_items.extend(res.get('data', []))
        
    if 'naver_blog' in sources_to_run:
        res = fetch_naver_blog(config, search_keyword, target_date)
        all_items.extend(res.get('data', []))
        
    if 'youtube' in sources_to_run:
        res = fetch_youtube_videos(config, search_keyword, target_date)
        all_items.extend(res.get('data', []))

    if not all_items:
        logger.warning("No items collected. Exiting.")
        return

    items = normalize_data(all_items)
    items = deduplicate(items)
    items = apply_relevance_classification(items, config)
    items = apply_ai_classification(items, config)
    items = apply_safety_gate(items, config)

    # Public Items Filtering (엄격한 조건)
    allowed_categories = ["confirmed", "related_issue", "comparison", "political_context"]
    public_items = []
    for item in items:
        keep = True
        if item.get("filter_status") != "kept": keep = False
        if not item.get("public_visible_default", False): keep = False
        if item.get("safety_gate_reason"): keep = False
        if item.get("category") not in allowed_categories: keep = False
        
        # AI 결과 검증
        if item.get("ai_needed"):
            if not item.get("ai_used") or item.get("ai_result") != "relevant":
                keep = False
        
        if keep:
            public_items.append(item)
    
    # Calculate statistics
    summary = {
        "target_date": target_date,
        "search_keyword": search_keyword,
        "safe_keyword": safe_keyword,
        "generated_at": now_kst.isoformat(),
        "total_collected": len(all_items),
        "total_processed": len(items),
        "public_count": len(public_items),
        "source_stats": {},
        "category_stats": {},
        "seoul_anchor_count": sum(1 for item in items if item.get("seoul_anchor_score", 0) > 0),
        "other_event_excluded_count": sum(1 for item in items if item.get("category") == "other_event_only"),
        "noise_excluded_count": sum(1 for item in items if item.get("noise_score", 0) > 0 and item.get("filter_status") == "excluded"),
        "safety_gate_excluded_count": sum(1 for item in items if item.get("safety_gate_reason")),
        "ai_candidate_count": sum(1 for item in items if item.get("ai_needed")),
        "ai_called_count": sum(1 for item in items if item.get("ai_used")),
        "ai_relevant_count": sum(1 for item in items if item.get("ai_result") == "relevant"),
        "ai_irrelevant_count": sum(1 for item in items if item.get("ai_result") == "irrelevant"),
        "ai_uncertain_count": sum(1 for item in items if item.get("ai_result") == "uncertain"),
        "ai_skipped_due_to_limit_count": sum(1 for item in items if item.get("ai_reason") == "skipped_due_to_limit")
    }
    
    for item in public_items:
        src = item.get('source', 'unknown')
        cat = item.get('category', 'unknown')
        summary['source_stats'][src] = summary['source_stats'].get(src, 0) + 1
        summary['category_stats'][cat] = summary['category_stats'].get(cat, 0) + 1

    # Save files
    os.makedirs('outputs', exist_ok=True)
    os.makedirs('web/public/data', exist_ok=True)
    
    prefix = f"{target_date}_{safe_keyword}"
    
    # Audit & Details & Summary
    with open(f"web/public/data/{prefix}_filter_audit.json", 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        
    with open(f"web/public/data/{prefix}_details.json", 'w', encoding='utf-8') as f:
        json.dump(public_items, f, ensure_ascii=False, indent=2)
        
    with open(f"web/public/data/{prefix}_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Index Update
    index_entry = {
        "id": prefix,
        "target_date": target_date,
        "keyword": search_keyword,
        "safe_keyword": safe_keyword,
        "summary_file": f"/data/{prefix}_summary.json",
        "details_file": f"/data/{prefix}_details.json",
        "filter_audit_file": f"/data/{prefix}_filter_audit.json",
        "generated_at": now_kst.isoformat()
    }
    update_index("web/public/data/index.json", index_entry)

    logger.info(f"Pipeline complete. Public items: {len(public_items)}/{len(items)}")

if __name__ == "__main__":
    main()
