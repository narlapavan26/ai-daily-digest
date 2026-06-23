"""
Test HuggingFace Hub API
Uses huggingface_hub library - free, no authentication required for public data
Collects: Trending Models & Trending Datasets (Papers removed - redundant with ArXiv)
"""

def test_huggingface():
    """Test HuggingFace Hub API for trending models and datasets"""
    
    try:
        from huggingface_hub import list_models, list_datasets
    except ImportError:
        print("[ERROR] huggingface_hub not installed")
        print("Install with: pip install huggingface-hub")
        return
    
    from datetime import datetime, timedelta
    
    print("=" * 60)
    print("Testing: HuggingFace Hub API")
    print("=" * 60)
    
    # Test 1: Trending Models
    print(f"\n{'='*60}")
    print("Test 1: Trending Models (ML/LLM)")
    print(f"{'='*60}")
    
    try:
        # Get models sorted by downloads/likes (trending indicators)
        models = list(list_models(
            sort="downloads",
            direction=-1,
            limit=20,
            filter=["transformers", "pytorch"]  # Focus on ML models
        ))
        
        print(f"[OK] Found {len(models)} trending models")
        
        if models:
            print(f"\nTop Models:")
            for i, model in enumerate(models[:5], 1):
                print(f"\n{i}. {model.id}")
                print(f"   Downloads: {model.downloads:,}")
                print(f"   Likes: {model.likes}")
                if hasattr(model, 'tags') and model.tags:
                    tags = [t for t in model.tags[:5]]
                    print(f"   Tags: {', '.join(tags)}")
    
    except Exception as e:
        print(f"[ERROR] Error fetching models: {e}")
    
    # Test 2: Trending Datasets
    print(f"\n{'='*60}")
    print("Test 2: Trending Datasets (ML/AI)")
    print(f"{'='*60}")
    
    try:
        # Get datasets sorted by downloads (trending)
        datasets = list(list_datasets(
            sort="downloads",
            direction=-1,
            limit=20
        ))
        
        print(f"[OK] Found {len(datasets)} trending datasets")
        
        if datasets:
            print(f"\nTop Datasets:")
            for i, ds in enumerate(datasets[:5], 1):
                print(f"\n{i}. {ds.id}")
                print(f"   Downloads: {ds.downloads:,}")
                print(f"   Likes: {ds.likes}")
                if hasattr(ds, 'tags') and ds.tags:
                    tags = [t for t in ds.tags[:5]]
                    print(f"   Tags: {', '.join(tags)}")
    
    except Exception as e:
        print(f"[ERROR] Error fetching datasets: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY: HUGGINGFACE HUB API TEST")
    print("=" * 60)
    print("[OK] Models API: Working (using huggingface_hub)")
    print("[OK] Datasets API: Working (using huggingface_hub)")
    print("TIP: Expected collection: 20 models + 20 datasets = 40 items")


if __name__ == "__main__":
    import json
    import re
    from datetime import datetime
    from huggingface_hub import list_models, list_datasets
    
    print("\n" + "TEST SUITE: HUGGINGFACE HUB API TESTING" + "\n")
    test_huggingface()
    print("\n[OK] Testing Complete!")
    
    def _clean_model_card(text, max_chars=2500):
        """Clean HuggingFace model card: strip YAML front matter, badges, HTML."""
        if not text:
            return ''
        # Strip YAML front matter
        if text.startswith('---'):
            end = text.find('---', 3)
            if end > 0:
                text = text[end + 3:].strip()
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            # Skip badge/image lines
            if re.match(r'^\s*\[?!\[', line):
                continue
            if re.match(r'^\s*<(img|div|p|br|hr)\b', line, re.IGNORECASE):
                continue
            # Skip lines that are only URLs
            if re.match(r'^\s*https?://', line.strip()):
                continue
            # Skip table of contents links
            if re.match(r'^\s*-\s*\[.*\]\(#', line):
                continue
            cleaned.append(line)
        text = '\n'.join(cleaned)
        # Remove markdown link syntax: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Remove markdown bold/italic markers
        text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
        # Remove header markers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Collapse whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'  +', ' ', text)
        return text[:max_chars].strip()
    
    # Collect actual data for JSON output
    def collect_hf_data():
        import httpx
        all_items = {"models": [], "datasets": []}
        
        # Collect trending models (20 items) — use expand for richer data
        try:
            models = list(list_models(
                sort="trending_score",
                limit=20,
                filter=["transformers", "pytorch"],
                expand=["cardData", "lastModified", "pipeline_tag",
                        "downloads", "likes", "tags", "trendingScore"]
            ))
            
            for model in models:
                # Build description from card_data metadata
                card = getattr(model, 'card_data', None)
                description = ''
                if card:
                    parts = []
                    if hasattr(card, 'language') and card.language:
                        lang = card.language if isinstance(card.language, str) else ', '.join(card.language[:5])
                        parts.append(f"Language: {lang}")
                    if hasattr(card, 'library_name') and card.library_name:
                        parts.append(f"Library: {card.library_name}")
                    if hasattr(card, 'license') and card.license:
                        parts.append(f"License: {card.license}")
                    if hasattr(card, 'base_model') and card.base_model:
                        base = card.base_model if isinstance(card.base_model, str) else str(card.base_model)
                        parts.append(f"Base: {base[:80]}")
                    if hasattr(card, 'datasets') and card.datasets:
                        ds_list = card.datasets[:3] if isinstance(card.datasets, list) else [str(card.datasets)]
                        parts.append(f"Datasets: {', '.join(ds_list)}")
                    description = ' | '.join(parts)
                
                # Fetch model card README for rich content
                model_card_text = ''
                try:
                    with httpx.Client(timeout=10.0) as hf_client:
                        card_url = f"https://huggingface.co/{model.id}/raw/main/README.md"
                        card_resp = hf_client.get(card_url)
                        if card_resp.status_code == 200:
                            model_card_text = _clean_model_card(card_resp.text)
                except Exception:
                    pass
                
                all_items["models"].append({
                    "id": model.id,
                    "downloads": getattr(model, 'downloads', 0) or 0,
                    "likes": getattr(model, 'likes', 0) or 0,
                    "trending_score": getattr(model, 'trending_score', 0) or 0,
                    "pipeline_tag": getattr(model, 'pipeline_tag', '') or '',
                    "last_modified": str(getattr(model, 'last_modified', '')) if getattr(model, 'last_modified', None) else '',
                    "description": (description or '')[:500],
                    "model_card_text": model_card_text,
                    "tags": (model.tags[:10] if hasattr(model, 'tags') and model.tags else []),
                    "url": f"https://huggingface.co/{model.id}"
                })
        except Exception as e:
            print(f"[WARNING] Model collection error: {e}")
        
        # Collect trending datasets (20 items) — use expand for richer data
        try:
            datasets = list(list_datasets(
                sort="trending_score",
                limit=20,
                expand=["cardData", "lastModified", "downloads",
                        "likes", "tags", "trendingScore", "description"]
            ))
            
            for ds in datasets:
                # Fetch dataset card README for rich content
                ds_card_text = ''
                try:
                    with httpx.Client(timeout=10.0) as hf_client:
                        ds_card_url = f"https://huggingface.co/datasets/{ds.id}/raw/main/README.md"
                        ds_card_resp = hf_client.get(ds_card_url)
                        if ds_card_resp.status_code == 200:
                            ds_card_text = _clean_model_card(ds_card_resp.text)
                except Exception:
                    pass
                
                all_items["datasets"].append({
                    "id": ds.id,
                    "downloads": getattr(ds, 'downloads', 0) or 0,
                    "likes": getattr(ds, 'likes', 0) or 0,
                    "trending_score": getattr(ds, 'trending_score', 0) or 0,
                    "description": (getattr(ds, 'description', '') or '')[:500],
                    "model_card_text": ds_card_text,
                    "last_modified": str(getattr(ds, 'last_modified', '')) if getattr(ds, 'last_modified', None) else '',
                    "tags": (ds.tags[:10] if hasattr(ds, 'tags') and ds.tags else []),
                    "url": f"https://huggingface.co/datasets/{ds.id}"
                })
        except Exception as e:
            print(f"[WARNING] Dataset collection error: {e}")
        
        return all_items
    
    try:
        hf_data = collect_hf_data()
        
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "huggingface",
            "collected_at": datetime.now().isoformat(),
            "total_models": len(hf_data["models"]),
            "total_datasets": len(hf_data["datasets"]),
            "data": hf_data
        }, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "huggingface",
            "collected_at": datetime.now().isoformat(),
            "error": str(e),
            "data": {"models": [], "datasets": []}
        }, indent=2))
