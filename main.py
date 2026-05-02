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
    safe = re.sub(r'[^가-힣a-zA-Z0-9]', '_', keyword)
    safe = re.sub(r'_+', '_', safe)
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
            
    found = False
    for i, item in enumerate(index_data):
        if item.get("id") == entry["id"]:
            index_data[i] = entry
            found = True
            break
    if not found:
        index_data.append(entry)
        
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
        
        if category not in allowed_categories:
            gate_reason = "safety_gate:invalid_public_category"
        elif source == "naver_blog" and seoul_score == 0:
            gate_reason = "safety_gate:blog_no_seoul_anchor"
        elif seoul_score == 0 and (other_score > 0 or noise_score > 0):
            gate_reason = "safety_gate:no_seoul_anchor_with_noise_or_other"
        elif item.get("ai_needed") and (not item.get("ai_used") or ai_result != "relevant"):
            gate_reason = "safety_gate:ai_unverified_or_uncertain"

        if gate_reason:
            if seoul_score > 0:
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
    
    logger.info(f"Starting data collection for '{search_keyword}' on {target_date} (KST)")
    
    raw_results_by_source = {}
    all_collected_items = []
    
    # Collection Logic
    if 'naver_news' in sources_to_run:
        res = fetch_naver_news(config, search_keyword, target_date)
        raw_results_by_source['naver_news'] = res
        all_collected_items.extend(res.get('data', []))
        
    if 'naver_blog' in sources_to_run:
        res = fetch_naver_blog(config, search_keyword, target_date)
        raw_results_by_source['naver_blog'] = res
        all_collected_items.extend(res.get('data', []))
        
    if 'youtube' in sources_to_run:
        res = fetch_youtube_videos(config, search_keyword, target_date)
        raw_results_by_source['youtube'] = res
        all_collected_items.extend(res.get('data', []))

    if not all_collected_items:
        logger.warning("No items collected. Exiting.")
        return

    items = normalize_data(all_collected_items)
    items = deduplicate(items)
    items = apply_relevance_classification(items, config)
    items = apply_ai_classification(items, config)
    items = apply_safety_gate(items, config)

    # Public Items Filtering
    allowed_categories = ["confirmed", "related_issue", "comparison", "political_context"]
    public_items = [
        item for item in items 
        if item.get("filter_status") == "kept" 
        and item.get("public_visible_default", False)
        and not item.get("safety_gate_reason")
        and item.get("category") in allowed_categories
        and (not item.get("ai_needed") or (item.get("ai_used") and item.get("ai_result") == "relevant"))
    ]
    
    # Create Summary Array for Frontend
    summary_array = []
    source_labels = {
        "naver_news": "네이버 뉴스",
        "naver_blog": "네이버 블로그",
        "youtube": "유튜브",
        "total": "전체"
    }
    
    sources = list(raw_results_by_source.keys()) + ["total"]
    for src in sources:
        if src == "total":
            src_items = items
            src_public = public_items
            collected_count = sum(raw_results_by_source[s].get('api_pages_called', 0) * config.get('page_size', {}).get(s, 100) for s in raw_results_by_source) # Approx
            # Actually use real collected count from raw results
            collected_count = sum(len(raw_results_by_source[s].get('raw', [])[0].get('response', {}).get('items', [])) if raw_results_by_source[s].get('raw') else 0 for s in raw_results_by_source) # Still approx
            # Better: count items before normalize/dedupe
            collected_count = len(all_collected_items)
            status = "OK"
            message = ""
            pages_called = sum(raw_results_by_source[s].get('api_pages_called', 0) for s in raw_results_by_source)
        else:
            src_items = [item for item in items if item.get('source') == src]
            src_public = [item for item in public_items if item.get('source') == src]
            collected_count = len([item for item in all_collected_items if item.get('source') == src])
            status = raw_results_by_source[src].get('status', 'OK')
            message = raw_results_by_source[src].get('message', '')
            pages_called = raw_results_by_source[src].get('api_pages_called', 0)

        s_obj = {
            "target_date": target_date,
            "keyword": search_keyword,
            "source": src,
            "source_label": source_labels.get(src, src),
            "collected_count": collected_count,
            "raw_count": collected_count,
            "current_run_deduped_count": len(src_items),
            "public_count": len(src_public),
            "excluded_count": len(src_items) - len(src_public),
            "status": status,
            "message": message,
            "api_pages_called": pages_called,
            "ai_needed_count": sum(1 for item in src_items if item.get("ai_needed")),
            "ai_used_count": sum(1 for item in src_items if item.get("ai_used")),
            "ai_relevant_count": sum(1 for item in src_items if item.get("ai_result") == "relevant"),
            "ai_uncertain_count": sum(1 for item in src_items if item.get("ai_result") == "uncertain"),
            "ai_skipped_due_to_limit_count": sum(1 for item in src_items if item.get("ai_reason") == "skipped_due_to_limit")
        }
        
        # Add category counts to summary object
        categories = ["confirmed", "related_issue", "comparison", "political_context", "weak_match", "other_event_only", "irrelevant", "ai_irrelevant"]
        for cat in categories:
            s_obj[f"{cat}_count"] = sum(1 for item in src_items if item.get("category") == cat)
            
        summary_array.append(s_obj)

    # Save files
    os.makedirs('web/public/data', exist_ok=True)
    prefix = f"{target_date}_{safe_keyword}"
    
    with open(f"web/public/data/{prefix}_filter_audit.json", 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    with open(f"web/public/data/{prefix}_details.json", 'w', encoding='utf-8') as f:
        json.dump(public_items, f, ensure_ascii=False, indent=2)
    with open(f"web/public/data/{prefix}_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary_array, f, ensure_ascii=False, indent=2)

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
