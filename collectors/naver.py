import requests
import re
import time
import urllib.parse
from datetime import datetime
from dateutil import parser
import pytz

def strip_html_tags(text):
    if not text:
        return ""
    # Remove HTML tags, especially <b> and </b>
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

def parse_naver_pubdate(pubdate_str, timezone_str='Asia/Seoul'):
    """Parse Naver News pubDate and convert to KST YYYY-MM-DD"""
    try:
        # pubDate format: "Tue, 01 May 2026 09:00:00 +0900"
        dt = parser.parse(pubdate_str)
        target_tz = pytz.timezone(timezone_str)
        dt_kst = dt.astimezone(target_tz)
        return dt_kst
    except Exception as e:
        return None

def fetch_with_retry(url, headers, config, error_context="Naver API"):
    max_attempts = config.get("retry", {}).get("max_attempts", 3)
    backoff_seconds = config.get("retry", {}).get("backoff_seconds", 2)
    interval = config.get("request_interval_seconds", 0.2)
    
    for attempt in range(max_attempts):
        try:
            time.sleep(interval)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json(), None
            else:
                error_msg = f"{error_context} Error: {response.status_code} - {response.text}"
                if attempt < max_attempts - 1:
                    time.sleep(backoff_seconds * (attempt + 1))
                    continue
                return None, error_msg
        except Exception as e:
            error_msg = f"{error_context} Network Error: {str(e)}"
            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            return None, error_msg
    return None, f"{error_context} Max retries exceeded"

def fetch_naver_news(config, keyword, target_date_str):
    client_id = config.get("naver_client_id")
    client_secret = config.get("naver_client_secret")
    max_pages = config.get("max_pages", {}).get("naver_news", 10)
    page_size = config.get("page_size", {}).get("naver_news", 100)
    timezone_str = config.get("timezone", "Asia/Seoul")
    
    if not client_id or not client_secret:
        return {"status": "ERROR", "message": "Naver API keys missing", "data": [], "raw": [], "api_pages_called": 0}
        
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    encoded_keyword = urllib.parse.quote(keyword)
    
    results = []
    raw_responses = []
    error_message = None
    pages_called = 0
    warning_limit_exceeded = False
    
    for i in range(max_pages):
        start = i * page_size + 1
        if start > 1000:
            warning_limit_exceeded = True
            break
            
        url = f"https://openapi.naver.com/v1/search/news.json?query={encoded_keyword}&display={page_size}&start={start}&sort=date"
        
        pages_called += 1
        data, err = fetch_with_retry(url, headers, config, "Naver News")
        if err:
            error_message = err
            break
            
        raw_responses.append({"page_no": i+1, "requested_at_kst": datetime.now(pytz.timezone(timezone_str)).isoformat(), "response": data})
        
        items = data.get("items", [])
        if not items:
            break
            
        for item in items:
            pubDate = item.get("pubDate", "")
            dt_kst = parse_naver_pubdate(pubDate, timezone_str)
            if not dt_kst:
                continue
                
            item_date_str = dt_kst.strftime("%Y-%m-%d")
            
            # Filter by target_date
            if item_date_str != target_date_str:
                continue
                
            title = strip_html_tags(item.get("title", ""))
            description = strip_html_tags(item.get("description", ""))
            originallink = item.get("originallink", "")
            link = item.get("link", "")
            
            canonical_url = originallink if originallink else link
            if not canonical_url:
                canonical_url = link
                
            results.append({
                "source": "naver_news",
                "source_label": "네이버 뉴스",
                "keyword": keyword,
                "target_date": target_date_str,
                "title": title,
                "description": description,
                "author_or_channel": "", # Naver news doesn't provide author easily here
                "published_at_original": pubDate,
                "published_at_kst": dt_kst.isoformat(),
                "published_date_kst": item_date_str,
                "canonical_url": canonical_url,
                "original_url": link,
                "external_id": "",
                "collected_at_kst": datetime.now(pytz.timezone(timezone_str)).isoformat(),
                "raw_rank": start + len(results), # Approximate
                "page_no": i + 1
            })
            
    # Deduplicate inside collector just in case, but we will rely on processors/dedupe.py too.
    # Actually, let's keep all and dedupe later as per plan, but we can do a preliminary dedupe if needed.
    # The requirement says "processors/dedupe.py" handles it. Let's output raw.
    
    status = "OK" if not error_message else "ERROR"
    if warning_limit_exceeded:
        message = "Limit exceeded warning" if not error_message else error_message + " (Limit exceeded warning)"
    else:
        message = error_message if error_message else "Success"
        
    return {
        "status": status,
        "message": message,
        "data": results,
        "raw": raw_responses,
        "api_pages_called": pages_called
    }

def fetch_naver_blog(config, keyword, target_date_str):
    client_id = config.get("naver_client_id")
    client_secret = config.get("naver_client_secret")
    max_pages = config.get("max_pages", {}).get("naver_blog", 10)
    page_size = config.get("page_size", {}).get("naver_blog", 100)
    timezone_str = config.get("timezone", "Asia/Seoul")
    
    if not client_id or not client_secret:
        return {"status": "ERROR", "message": "Naver API keys missing", "data": [], "raw": [], "api_pages_called": 0}
        
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    encoded_keyword = urllib.parse.quote(keyword)
    
    results = []
    raw_responses = []
    error_message = None
    pages_called = 0
    warning_limit_exceeded = False
    
    for i in range(max_pages):
        start = i * page_size + 1
        if start > 1000:
            warning_limit_exceeded = True
            break
            
        url = f"https://openapi.naver.com/v1/search/blog.json?query={encoded_keyword}&display={page_size}&start={start}&sort=date"
        
        pages_called += 1
        data, err = fetch_with_retry(url, headers, config, "Naver Blog")
        if err:
            error_message = err
            break
            
        raw_responses.append({"page_no": i+1, "requested_at_kst": datetime.now(pytz.timezone(timezone_str)).isoformat(), "response": data})
        
        items = data.get("items", [])
        if not items:
            break
            
        for item in items:
            postdate = item.get("postdate", "")
            # postdate is YYYYMMDD
            if len(postdate) == 8:
                item_date_str = f"{postdate[:4]}-{postdate[4:6]}-{postdate[6:]}"
            else:
                item_date_str = postdate # fallback
                
            if item_date_str != target_date_str:
                continue
                
            title = strip_html_tags(item.get("title", ""))
            description = strip_html_tags(item.get("description", ""))
            link = item.get("link", "")
            bloggername = strip_html_tags(item.get("bloggername", ""))
            
            canonical_url = link
                
            results.append({
                "source": "naver_blog",
                "source_label": "네이버 블로그",
                "keyword": keyword,
                "target_date": target_date_str,
                "title": title,
                "description": description,
                "author_or_channel": bloggername,
                "published_at_original": postdate,
                "published_at_kst": item_date_str + "T00:00:00+09:00", # approximate
                "published_date_kst": item_date_str,
                "canonical_url": canonical_url,
                "original_url": link,
                "external_id": "",
                "collected_at_kst": datetime.now(pytz.timezone(timezone_str)).isoformat(),
                "raw_rank": start + len(results),
                "page_no": i + 1
            })
            
    status = "OK" if not error_message else "ERROR"
    if warning_limit_exceeded:
        message = "Limit exceeded warning" if not error_message else error_message + " (Limit exceeded warning)"
    else:
        message = error_message if error_message else "Success"
        
    return {
        "status": status,
        "message": message,
        "data": results,
        "raw": raw_responses,
        "api_pages_called": pages_called
    }
