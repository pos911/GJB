import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta
import pandas as pd
import re
import pytz

KST = pytz.timezone('Asia/Seoul')

from collectors.naver import fetch_naver_news, fetch_naver_blog
from collectors.youtube import fetch_youtube_videos
from processors.normalize import normalize_data
from processors.dedupe import deduplicate

def setup_directories():
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

def setup_logging(target_date, keyword):
    safe_keyword = re.sub(r'[^a-zA-Z0-9가-힣]', '_', keyword)
    log_filename = f"logs/{target_date}_{safe_keyword}_run.log"
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
        
    fh = logging.FileHandler(log_filename, encoding='utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 로그 시간을 KST로 강제
    formatter.converter = lambda *args: datetime.now(KST).timetuple()
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger, safe_keyword

def load_config(config_path):
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
    # Load secrets
    secret_str = os.getenv("SECRET_JSON")
    if secret_str:
        try:
            secrets = json.loads(secret_str)
            config.update(secrets)
        except json.JSONDecodeError:
            print("오류: SECRET_JSON 환경변수가 올바른 JSON 포맷이 아닙니다.")
    elif os.path.exists("secret.json"):
        with open("secret.json", 'r', encoding='utf-8') as f:
            secrets = json.load(f)
            config.update(secrets)
            
    return config

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-channel PR/Public Opinion Data Collector")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config file")
    parser.add_argument("--date", type=str, help="Target date in YYYY-MM-DD KST")
    parser.add_argument("--keyword", type=str, help="Search keyword")
    parser.add_argument("--sources", type=str, help="Comma-separated sources (naver_news,naver_blog,youtube)")
    parser.add_argument("--max-pages", type=int, help="Max pages to fetch")
    
    # Mutually exclusive group for detail
    detail_group = parser.add_mutually_exclusive_group()
    detail_group.add_argument("--detail", action="store_true", help="Print detailed list to console")
    detail_group.add_argument("--no-detail", action="store_false", dest="detail", help="Do not print detailed list")
    parser.set_defaults(detail=None)
    return parser.parse_args()


def merge_config(file_config, args):
    config = file_config.copy()
    now_kst = datetime.now(KST)
    
    date_val = args.date if args.date else file_config.get("target_date")
    if date_val == "today":
        config["target_date"] = now_kst.strftime("%Y-%m-%d")
    elif date_val == "yesterday":
        config["target_date"] = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        config["target_date"] = date_val

    if args.keyword:
        config["keywords"] = [args.keyword]
    if args.sources:
        config["sources"] = [s.strip() for s in args.sources.split(",")]
    if args.max_pages is not None:
        if "max_pages" not in config:
            config["max_pages"] = {}
        for src in ["naver_news", "naver_blog", "youtube"]:
            config["max_pages"][src] = args.max_pages
            
    if args.detail is not None:
        config["include_detail_list"] = args.detail
        
    return config

def check_required_keys(config):
    if not config.get("naver_client_id") or not config.get("naver_client_secret"):
        print("오류: 네이버 API 키(naver_client_id, naver_client_secret)가 secret.json 또는 SECRET_JSON에 설정되지 않았습니다.")
        sys.exit(1)
    if "youtube" in config.get("sources", []) and not config.get("youtube_api_key"):
        print("오류: YouTube API 키(youtube_api_key)가 secret.json 또는 SECRET_JSON에 설정되지 않았습니다.")
        sys.exit(1)

def save_outputs(target_date, safe_keyword, summary_data, detail_data, raw_data):
    base_prefix = f"outputs/{target_date}_{safe_keyword}"
    web_data_dir = "web/public/data"
    os.makedirs(web_data_dir, exist_ok=True)
    web_prefix = f"{web_data_dir}/{target_date}_{safe_keyword}"
    
    summary_df = pd.DataFrame(summary_data)
    detail_df = pd.DataFrame(detail_data)
    
    # 1. xlsx
    xlsx_path = f"{base_prefix}_summary.xlsx"
    with pd.ExcelWriter(xlsx_path) as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        detail_df.to_excel(writer, sheet_name="Details", index=False)
        
        # Build raw stats
        raw_stats = []
        for rd in raw_data:
            source = rd.get("source")
            keyword = rd.get("keyword")
            for page in rd.get("pages", []):
                resp = page.get("response", {})
                count = len(resp.get("items", [])) if isinstance(resp, dict) else 0
                raw_stats.append({
                    "source": source,
                    "keyword": keyword,
                    "page_no": page.get("page_no"),
                    "requested_at_kst": page.get("requested_at_kst"),
                    "response_count": count,
                    "status_code": 200 if count >= 0 else 500, # Approximate for success
                    "error_message": rd.get("error_message", "")
                })
        pd.DataFrame(raw_stats).to_excel(writer, sheet_name="RawStats", index=False)
        
    # 2. csv
    summary_csv_path = f"{base_prefix}_summary.csv"
    summary_df.to_csv(summary_csv_path, index=False, encoding="utf-8-sig")
    
    detail_csv_path = f"{base_prefix}_details.csv"
    detail_df.to_csv(detail_csv_path, index=False, encoding="utf-8-sig")
    
    # 3. json
    detail_json_path = f"{base_prefix}_details.json"
    with open(detail_json_path, 'w', encoding='utf-8') as f:
        json.dump(detail_data, f, ensure_ascii=False, indent=2)
        
    raw_json_path = f"{base_prefix}_raw.json"
    with open(raw_json_path, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
        
    # 4. Web Data Export
    summary_json_path = f"{web_prefix}_summary.json"
    with open(summary_json_path, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
        
    web_detail_json_path = f"{web_prefix}_details.json"
    with open(web_detail_json_path, 'w', encoding='utf-8') as f:
        json.dump(detail_data, f, ensure_ascii=False, indent=2)
        
    # Update index.json
    index_path = f"{web_data_dir}/index.json"
    index_data = []
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
        except:
            pass
            
    # Check if entry already exists and update
    entry_id = f"{target_date}_{safe_keyword}"
    existing = next((item for item in index_data if item["id"] == entry_id), None)
    if not existing:
        index_data.append({
            "id": entry_id,
            "target_date": target_date,
            "keyword": safe_keyword,
            "summary_file": f"/data/{entry_id}_summary.json",
            "details_file": f"/data/{entry_id}_details.json",
            "generated_at": datetime.now(KST).isoformat()
        })
    else:
        existing["generated_at"] = datetime.now(KST).isoformat()
        
    # Sort descending by date
    index_data.sort(key=lambda x: x["target_date"], reverse=True)
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
        
    return xlsx_path, detail_csv_path, detail_json_path, raw_json_path

def print_console(target_date, keyword, summary_data, detail_data, include_detail_list, paths):
    print("=" * 50)
    print("다채널 홍보/여론 데이터 수집 결과")
    print(f"수집 기준일: {target_date} KST")
    print(f"검색어: {keyword}")
    print("=" * 50)
    print()
    print(f"{'영역':<15} {'수집 건수':<10} {'원천 건수':<10} {'중복 제거':<10} {'상태'}")
    print("-" * 50)
    
    total_deduped = 0
    for s in summary_data:
        label = s["source_label"]
        deduped = s["deduped_count"]
        raw = s["raw_count"]
        collected = s["collected_count"]
        status = s["status"]
        print(f"{label:<15} {collected:<10} {raw:<10} {collected - deduped:<10} {status}")
        total_deduped += deduped
        
    print("-" * 50)
    print(f"총합{'':<11} {total_deduped}개")
    print()
    
    print("저장 파일:")
    for path in paths:
        print(f"- {path}")
    print()
    
    if include_detail_list:
        print("상세 리스트 출력 옵션: 활성화됨\n")
        sources = {"naver_news": "[네이버 뉴스]", "naver_blog": "[네이버 블로그]", "youtube": "[유튜브]"}
        
        for src_key, src_title in sources.items():
            print(src_title)
            items = [item for item in detail_data if item["source"] == src_key]
            for idx, item in enumerate(items, 1):
                title = item["title"]
                url = item["canonical_url"]
                
                if src_key == "naver_news":
                    date_str = item["published_at_kst"]
                    print(f"{idx}. {title}\n   - 일시: {date_str}\n   - 링크: {url}")
                elif src_key == "naver_blog":
                    date_str = item["published_date_kst"]
                    author = item["author_or_channel"]
                    print(f"{idx}. {title}\n   - 작성자: {author}\n   - 일시: {date_str}\n   - 링크: {url}")
                elif src_key == "youtube":
                    date_str = item["published_at_kst"]
                    channel = item["author_or_channel"]
                    print(f"{idx}. {title}\n   - 채널: {channel}\n   - 일시: {date_str}\n   - 링크: {url}")
            print()
    else:
        print("상세 리스트 출력 옵션: 파일 저장 경로만 출력 (비활성화됨)\n")

def main():
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    setup_directories()
    args = parse_args()
    file_config = load_config(args.config)
    config = merge_config(file_config, args)
    
    check_required_keys(config)
    
    keywords = config.get("keywords", [])
    target_date = config.get("target_date")
    sources = config.get("sources", [])
    include_detail_list = config.get("include_detail_list", False)
    
    if not keywords or not target_date:
        print("오류: 검색어(keywords)와 기준일(target_date)은 필수입니다.")
        sys.exit(1)
        
    for keyword in keywords:
        logger, safe_keyword = setup_logging(target_date, keyword)
        logger.info(f"Starting data collection for '{keyword}' on {target_date}")
        
        all_detail_data = []
        summary_data = []
        raw_data = []
        
        for source in sources:
            logger.info(f"Fetching from {source}...")
            
            if source == "naver_news":
                res = fetch_naver_news(config, keyword, target_date)
                source_label = "네이버 뉴스"
            elif source == "naver_blog":
                res = fetch_naver_blog(config, keyword, target_date)
                source_label = "네이버 블로그"
            elif source == "youtube":
                res = fetch_youtube_videos(config, keyword, target_date)
                source_label = "유튜브"
            else:
                logger.warning(f"Unknown source: {source}")
                continue
                
            status = res["status"]
            message = res["message"]
            raw_items = res["data"]
            api_pages = res["api_pages_called"]
            
            if status == "ERROR":
                logger.error(f"Error in {source}: {message}")
            else:
                logger.info(f"Success in {source}. Items collected: {len(raw_items)}")
                
            # Keep raw data
            raw_data.append({
                "source": source,
                "keyword": keyword,
                "pages": res["raw"],
                "error_message": message if status == "ERROR" else ""
            })
            
            normalized_items = normalize_data(raw_items)
            deduped_items = deduplicate(normalized_items)
            
            collected_count = len(normalized_items)
            deduped_count = len(deduped_items)
            
            summary_data.append({
                "target_date": target_date,
                "keyword": keyword,
                "source": source,
                "source_label": source_label,
                "collected_count": collected_count,
                "raw_count": collected_count, # raw match since we filtered by date in collector
                "deduped_count": deduped_count,
                "error_count": 1 if status == "ERROR" else 0,
                "api_pages_called": api_pages,
                "status": status,
                "message": message
            })
            
            all_detail_data.extend(deduped_items)
            
        # Save Outputs
        try:
            paths = save_outputs(target_date, safe_keyword, summary_data, all_detail_data, raw_data)
            logger.info("Output files saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save output files: {e}")
            paths = []
            
        # Print Console
        print_console(target_date, keyword, summary_data, all_detail_data, include_detail_list, paths)

if __name__ == "__main__":
    main()
