import os
import json
import logging
import argparse
from datetime import datetime
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
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    if os.path.exists(secret_path):
        with open(secret_path, 'r', encoding='utf-8') as f:
            secrets = json.load(f)
            config.update(secrets)
    return config

def apply_safety_gate(items, config):
    """
    Gemini 판별 결과 이후 최종 검증 단계.
    AI가 관련 있다고 해도 명백한 노이즈나 서울 앵커 부재 시 차단한다.
    """
    rf = config.get("relevance_filter", {})
    if not rf.get("safety_gate_enabled", True):
        return items

    for item in items:
        if item.get("filter_status") == "excluded":
            continue

        seoul_score = item.get("seoul_anchor_score", 0)
        other_score = item.get("other_event_score", 0)
        noise_score = item.get("noise_score", 0)
        source = item.get("source", "")
        ai_result = item.get("ai_result", "")
        
        gate_reason = None
        
        if source == "naver_blog" and seoul_score == 0:
            gate_reason = "safety_gate:blog_no_seoul_anchor"
        elif seoul_score == 0 and (other_score > 0 or noise_score > 0):
            gate_reason = "safety_gate:no_seoul_anchor_with_noise_or_other"
        elif item.get("ai_needed") and (not item.get("ai_used") or ai_result != "relevant"):
            gate_reason = "safety_gate:ai_unverified_or_uncertain"

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
    
    target_date = args.date or config.get('target_date', 'today')
    if target_date == 'today':
        target_date = datetime.now().strftime('%Y-%m-%d')
    elif target_date == 'yesterday':
        from datetime import timedelta
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    search_keyword = args.keyword or config.get('keywords', ['국제정원박람회'])[0]
    sources_to_run = args.sources.split(',') if args.sources else config.get('sources', [])
    
    logger.info(f"Starting data collection for '{search_keyword}' on {target_date}")
    
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

    public_items = [
        item for item in items 
        if item.get("filter_status") == "kept" 
        and item.get("public_visible_default", False)
        and not item.get("safety_gate_reason")
    ]
    
    summary = {
        "target_date": target_date,
        "search_keyword": search_keyword,
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
        "ai_uncertain_count": sum(1 for item in items if item.get("ai_result") == "uncertain")
    }
    
    for item in public_items:
        src = item.get('source', 'unknown')
        cat = item.get('category', 'unknown')
        summary['source_stats'][src] = summary['source_stats'].get(src, 0) + 1
        summary['category_stats'][cat] = summary['category_stats'].get(cat, 0) + 1

    os.makedirs('outputs', exist_ok=True)
    os.makedirs('web/public/data', exist_ok=True)
    
    prefix = f"{target_date}_{search_keyword}"
    
    with open(f"outputs/{prefix}_filter_audit.json", 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    with open(f"web/public/data/{prefix}_filter_audit.json", 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        
    with open(f"outputs/{prefix}_details.json", 'w', encoding='utf-8') as f:
        json.dump(public_items, f, ensure_ascii=False, indent=2)
    with open(f"web/public/data/{prefix}_details.json", 'w', encoding='utf-8') as f:
        json.dump(public_items, f, ensure_ascii=False, indent=2)
        
    with open(f"outputs/{prefix}_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(f"web/public/data/{prefix}_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"Output saved. Public items: {len(public_items)}/{len(items)}")

if __name__ == "__main__":
    main()
