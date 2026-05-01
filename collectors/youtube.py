import requests
import time
import urllib.parse
from datetime import datetime, timedelta
from dateutil import parser
import pytz

def get_utc_bounds_from_kst(target_date_str, timezone_str='Asia/Seoul'):
    target_tz = pytz.timezone(timezone_str)
    dt_start = target_tz.localize(datetime.strptime(target_date_str, "%Y-%m-%d"))
    dt_end = dt_start + timedelta(days=1)
    
    utc_start = dt_start.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    utc_end = dt_end.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return utc_start, utc_end

def fetch_with_retry(url, config, error_context="YouTube API"):
    max_attempts = config.get("retry", {}).get("max_attempts", 3)
    backoff_seconds = config.get("retry", {}).get("backoff_seconds", 2)
    interval = config.get("request_interval_seconds", 0.2)
    
    for attempt in range(max_attempts):
        try:
            time.sleep(interval)
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return data, None
            else:
                error_reason = "Unknown Error"
                if "error" in data and "errors" in data["error"]:
                    reasons = [e.get("reason", "") for e in data["error"]["errors"]]
                    error_reason = ", ".join(reasons)
                
                error_msg = f"{error_context} Error: {response.status_code} - {error_reason}"
                
                # Fatal errors that shouldn't be retried
                if any(r in error_reason for r in ["quotaExceeded", "dailyLimitExceeded", "keyInvalid", "forbidden"]):
                    return None, error_msg
                    
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

def fetch_youtube_videos(config, keyword, target_date_str):
    api_key = config.get("youtube_api_key")
    max_pages = config.get("max_pages", {}).get("youtube", 10)
    page_size = config.get("page_size", {}).get("youtube", 50)
    timezone_str = config.get("timezone", "Asia/Seoul")
    safe_search = config.get("youtube_safe_search", "none")
    
    if not api_key:
        return {"status": "ERROR", "message": "YouTube API key missing", "data": [], "raw": [], "api_pages_called": 0}
        
    utc_start, utc_end = get_utc_bounds_from_kst(target_date_str, timezone_str)
    encoded_keyword = urllib.parse.quote(keyword)
    
    results = []
    raw_responses = []
    error_message = None
    pages_called = 0
    next_page_token = ""
    
    for i in range(max_pages):
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={encoded_keyword}&order=date&maxResults={page_size}&regionCode=KR&relevanceLanguage=ko&safeSearch={safe_search}&publishedAfter={utc_start}&publishedBefore={utc_end}&key={api_key}"
        
        if next_page_token:
            url += f"&pageToken={next_page_token}"
            
        pages_called += 1
        data, err = fetch_with_retry(url, config, "YouTube")
        if err:
            error_message = err
            break
            
        raw_responses.append({"page_no": i+1, "requested_at_kst": datetime.now(pytz.timezone(timezone_str)).isoformat(), "response": data})
        
        items = data.get("items", [])
        if not items:
            break
            
        for item in items:
            snippet = item.get("snippet", {})
            videoId = item.get("id", {}).get("videoId", "")
            if not videoId:
                continue
                
            publishedAt = snippet.get("publishedAt", "")
            try:
                dt_utc = parser.parse(publishedAt)
                target_tz = pytz.timezone(timezone_str)
                dt_kst = dt_utc.astimezone(target_tz)
                item_date_str = dt_kst.strftime("%Y-%m-%d")
            except:
                continue
                
            if item_date_str != target_date_str:
                continue
                
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channelTitle = snippet.get("channelTitle", "")
            channelId = snippet.get("channelId", "")
            thumbnails = snippet.get("thumbnails", {})
            thumb_url = thumbnails.get("high", thumbnails.get("default", {})).get("url", "")
            
            canonical_url = f"https://www.youtube.com/watch?v={videoId}"
            
            results.append({
                "source": "youtube",
                "source_label": "유튜브",
                "keyword": keyword,
                "target_date": target_date_str,
                "title": title,
                "description": description,
                "author_or_channel": channelTitle,
                "published_at_original": publishedAt,
                "published_at_kst": dt_kst.isoformat(),
                "published_date_kst": item_date_str,
                "canonical_url": canonical_url,
                "original_url": canonical_url,
                "external_id": videoId,
                "collected_at_kst": datetime.now(pytz.timezone(timezone_str)).isoformat(),
                "raw_rank": len(results) + 1,
                "page_no": i + 1,
                "channel_id": channelId,
                "thumbnail_url": thumb_url
            })
            
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
            
    status = "OK" if not error_message else "ERROR"
    message = error_message if error_message else "Success"
        
    return {
        "status": status,
        "message": message,
        "data": results,
        "raw": raw_responses,
        "api_pages_called": pages_called
    }
