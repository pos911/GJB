"""
processors/existing_dedupe.py
기존 적재 데이터 기준 중복 제거 모듈.

web/public/data/index.json에 등록된 기존 details 파일들을 읽어
신규 수집 item과의 중복을 판별한다.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def build_item_key(item):
    """
    중복 기준 키를 생성한다.
    
    우선순위:
    1. external_id가 있으면 source + external_id
    2. canonical_url이 있으면 source + canonical_url
    3. original_url이 있으면 source + original_url
    4. 위 값이 없으면 source + title + published_date_kst
    """
    source = item.get("source", "")
    external_id = item.get("external_id", "")
    canonical_url = item.get("canonical_url", "")
    original_url = item.get("original_url", "")
    title = item.get("title", "")
    published_date = item.get("published_date_kst", "")
    
    if external_id:
        return f"{source}::eid::{external_id}"
    if canonical_url:
        return f"{source}::curl::{canonical_url}"
    if original_url:
        return f"{source}::ourl::{original_url}"
    return f"{source}::tpd::{title}::{published_date}"


def load_existing_item_keys(web_data_dir, current_entry_id=None, allow_overwrite_same_report_id=True):
    """
    web/public/data/index.json을 읽어 기존 적재된 item들의 키 세트를 반환한다.
    
    Args:
        web_data_dir: web/public/data 디렉토리 경로
        current_entry_id: 현재 생성하려는 entry_id (예: "2026-05-01_국제정원박람회")
        allow_overwrite_same_report_id: True이면 current_entry_id와 같은 파일은 중복 검사에서 제외
    
    Returns:
        set: 기존 적재된 item들의 키 세트
    """
    existing_keys = set()
    index_path = os.path.join(web_data_dir, "index.json")
    
    if not os.path.exists(index_path):
        logger.info("No existing index.json found. No existing duplicates to check.")
        return existing_keys
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to read index.json: {e}")
        return existing_keys
    
    for entry in index_data:
        entry_id = entry.get("id", "")
        
        # allow_overwrite_same_report_id가 True이면 현재 생성 중인 entry는 건너뜀
        if allow_overwrite_same_report_id and entry_id == current_entry_id:
            logger.info(f"Skipping existing entry '{entry_id}' (same report id, overwrite allowed)")
            continue
        
        details_file = entry.get("details_file", "")
        if not details_file:
            continue
        
        # details_file은 "/data/xxx_details.json" 형식
        # web_data_dir 기준으로 실제 경로 구성
        if details_file.startswith("/data/"):
            file_path = os.path.join(web_data_dir, details_file[len("/data/"):])
        else:
            file_path = os.path.join(web_data_dir, os.path.basename(details_file))
        
        if not os.path.exists(file_path):
            logger.warning(f"Details file not found: {file_path}")
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                details = json.load(f)
            
            for item in details:
                key = build_item_key(item)
                existing_keys.add(key)
            
            logger.info(f"Loaded {len(details)} items from existing entry '{entry_id}'")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read details file '{file_path}': {e}")
    
    logger.info(f"Total existing item keys loaded: {len(existing_keys)}")
    return existing_keys


def filter_existing_duplicates(items, existing_keys):
    """
    신규 items에서 기존 적재 데이터와 중복되는 항목을 제거한다.
    
    Args:
        items: 신규 수집된 item 리스트
        existing_keys: load_existing_item_keys로 로드한 기존 키 세트
    
    Returns:
        tuple: (non_duplicate_items, skipped_count)
    """
    if not existing_keys:
        return items, 0
    
    non_duplicates = []
    skipped_count = 0
    
    for item in items:
        key = build_item_key(item)
        if key in existing_keys:
            skipped_count += 1
            logger.debug(f"Existing duplicate skipped: {item.get('title', '')[:50]}")
        else:
            non_duplicates.append(item)
    
    if skipped_count > 0:
        logger.info(f"Existing duplicate check: {skipped_count} items skipped, {len(non_duplicates)} items remain")
    
    return non_duplicates, skipped_count
