def normalize_data(raw_items):
    """
    Ensure all items match the common data model.
    Since collectors already map most fields, this function guarantees
    the schema is consistent and fills missing optional fields.
    """
    schema = [
        "target_date",
        "keyword",
        "source",
        "source_label",
        "title",
        "description",
        "author_or_channel",
        "published_at_original",
        "published_at_kst",
        "published_date_kst",
        "canonical_url",
        "original_url",
        "external_id",
        "collected_at_kst",
        "raw_rank",
        "page_no"
    ]
    
    normalized = []
    for item in raw_items:
        norm_item = {}
        for key in schema:
            norm_item[key] = item.get(key, "")
        normalized.append(norm_item)
        
    return normalized
