def deduplicate(items):
    """
    Deduplicate items based on rules:
    - youtube: external_id
    - naver_news, naver_blog: canonical_url
    - fallback: title + published_date_kst + source
    
    Enhanced: Also deduplicates by exact 'title' within the same 'source' to remove 
    photo news spam (different URLs but same title/description).
    """
    seen_keys = set()
    seen_titles = set()
    deduped = []
    
    for item in items:
        source = item.get("source", "")
        title = item.get("title", "")
        
        # Determine the primary key
        if source == "youtube":
            primary_key = item.get("external_id")
        else:
            primary_key = item.get("canonical_url")
            
        # Use fallback if primary key is empty
        if not primary_key:
            date_kst = item.get("published_date_kst", "")
            primary_key = f"{title}_{date_kst}_{source}"
            
        title_key = f"{title}_{source}"
        
        # Uniqueness check (both primary key and title)
        if primary_key not in seen_keys and title_key not in seen_titles:
            seen_keys.add(primary_key)
            seen_titles.add(title_key)
            deduped.append(item)
            
    return deduped
