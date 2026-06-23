"""
Test Groq API - Primary AI Provider
Tests single item and batch processing
"""
import os
from openai import OpenAI

def test_groq_single_item():
    """Test Groq with a single news item"""
    
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY not found in environment")
        print("Set it with: export GROQ_API_KEY='your_key'")
        return
    
    # Initialize Groq client (OpenAI-compatible)
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Sample AI/ML news item
    test_item = {
        "title": "LangGraph 0.2.0 Released with Streaming Support",
        "source": "GitHub Release",
        "content": """
        LangGraph announces major update with streaming capabilities for agentic workflows.
        Key features include:
        - Streaming support for long-running agent tasks
        - Improved error handling and retry logic
        - Better integration with LangChain LCEL
        - New documentation and examples
        This update enables developers to build more responsive AI agents.
        """
    }
    
    print("=" * 60)
    print("Testing: Groq API - Single Item")
    print("=" * 60)
    print(f"Model: llama-3.3-70b-versatile")
    print(f"Item: {test_item['title']}\n")
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI/ML news analyzer. Return ONLY valid JSON, no markdown formatting."
                },
                {
                    "role": "user",
                    "content": f"""Analyze this AI/ML news item:

Title: {test_item['title']}
Source: {test_item['source']}
Content: {test_item['content']}

Return JSON with this exact structure:
{{
  "summary": "A 2-sentence technical summary",
  "relevance_score": 8,
  "tags": ["LangChain", "Agentic", "Streaming"],
  "is_breaking": false,
  "framework_mentions": ["LangGraph", "LangChain"]
}}"""
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        print("[OK] Groq API Response:")
        print("-" * 60)
        print(response.choices[0].message.content)
        print("-" * 60)
        print(f"\nToken Usage:")
        # pyrefly: ignore [missing-attribute]
        print(f"  Prompt tokens: {response.usage.prompt_tokens}")
        # pyrefly: ignore [missing-attribute]
        print(f"  Completion tokens: {response.usage.completion_tokens}")
        # pyrefly: ignore [missing-attribute]
        print(f"  Total tokens: {response.usage.total_tokens}")
        print(f"\nModel: {response.model}")
        
        # Verify JSON parsing
        import json
        try:
            # pyrefly: ignore [bad-argument-type]
            result = json.loads(response.choices[0].message.content)
            print(f"\n[OK] JSON parsing: SUCCESS")
            print(f"   Summary length: {len(result.get('summary', ''))} chars")
            print(f"   Score: {result.get('relevance_score', 'N/A')}/10")
            print(f"   Tags: {result.get('tags', [])}")
            print(f"   Breaking: {result.get('is_breaking', False)}")
        except json.JSONDecodeError as e:
            print(f"\n[ERROR] JSON parsing: FAILED - {e}")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        if "401" in str(e):
            print("   → Check your GROQ_API_KEY is correct")
        elif "429" in str(e):
            print("   → Rate limit hit (wait 1 minute)")
        else:
            print(f"   → {type(e).__name__}: {e}")


def test_groq_batch():
    """Test Groq with a batch of 10 items"""
    
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY not found in environment")
        return
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Sample batch of 10 items
    items = [
        {"title": "LangGraph 0.2.0 Released", "content": "Streaming support for agents..."},
        {"title": "New ArXiv Paper on RAG", "content": "Novel approach to retrieval..."},
        {"title": "FastAPI 0.110.0 Update", "content": "Performance improvements..."},
        {"title": "OpenAI GPT-5 Rumors", "content": "Speculation about next model..."},
        {"title": "Anthropic Claude 4 Beta", "content": "New multimodal features..."},
        {"title": "HuggingFace New Models", "content": "3 new LLMs released..."},
        {"title": "Kaggle ML Competition", "content": "New challenge with $50k prize..."},
        {"title": "PyTorch 2.3 Released", "content": "Enhanced compilation features..."},
        {"title": "Reddit Discusses AGI", "content": "Debate on current progress..."},
        {"title": "GitHub Copilot Update", "content": "Improved code suggestions..."}
    ]
    
    print("\n" + "=" * 60)
    print("Testing: Groq API - Batch Processing (10 items)")
    print("=" * 60)
    print(f"Batch size: {len(items)} items\n")
    
    # Build batch prompt
    batch_prompt = "Analyze these 10 AI/ML news items:\n\n"
    for i, item in enumerate(items, 1):
        batch_prompt += f"Item {i}:\nTitle: {item['title']}\nContent: {item['content']}\n\n"
    
    batch_prompt += """
Return a JSON array with 10 objects (one per item):
[
  {
    "item_index": 1,
    "summary": "2-sentence summary",
    "relevance_score": 8,
    "tags": ["tag1", "tag2"],
    "is_breaking": false
  },
  ...
]
"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an AI/ML news analyzer. Return ONLY valid JSON array."},
                {"role": "user", "content": batch_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        print("[OK] Batch Response Received")
        print("-" * 60)
        # pyrefly: ignore [unsupported-operation]
        print(response.choices[0].message.content[:500] + "...")
        print("-" * 60)
        print(f"\nToken Usage for 10 items:")
        # pyrefly: ignore [missing-attribute]
        print(f"  Prompt tokens: {response.usage.prompt_tokens}")
        # pyrefly: ignore [missing-attribute]
        print(f"  Completion tokens: {response.usage.completion_tokens}")
        # pyrefly: ignore [missing-attribute]
        print(f"  Total tokens: {response.usage.total_tokens}")
        # pyrefly: ignore [missing-attribute]
        print(f"  Tokens per item: ~{response.usage.total_tokens // 10}")
        
        # Verify JSON parsing
        import json
        try:
            # pyrefly: ignore [bad-argument-type]
            results = json.loads(response.choices[0].message.content)
            print(f"\n[OK] JSON parsing: SUCCESS")
            print(f"   Items returned: {len(results)}")
            print(f"   Expected: 10")
            if len(results) == 10:
                print(f"   [OK] Correct count!")
            else:
                print(f"   [WARNING] Count mismatch")
        except json.JSONDecodeError as e:
            print(f"\n[ERROR] JSON parsing: FAILED - {e}")
        
        # Estimate for 200 items (production scenario)
        # pyrefly: ignore [missing-attribute]
        estimated_tokens = (response.usage.total_tokens / 10) * 200
        print(f"\nProjection for 200 items/day:")
        print(f"   Estimated total tokens: ~{int(estimated_tokens):,}")
        print(f"   Daily limit: 100,000 tokens")
        print(f"   Usage: {(estimated_tokens/100000)*100:.1f}%")
        
        # Batch calculation
        batch_size = 40
        num_batches = 200 // batch_size
        print(f"\nBatching Strategy:")
        print(f"   Batch size: {batch_size} items")
        print(f"   Number of batches: {num_batches}")
        print(f"   Tokens per batch: ~{int(estimated_tokens/num_batches):,}")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")


if __name__ == "__main__":
    import json
    from datetime import datetime
    
    print("\n" + "TEST SUITE: GROQ API TESTING" + "\n")
    
    # Test 1: Single item
    test_groq_single_item()
    
    # Test 2: Batch
    print("\n" + "Waiting 5 seconds before batch test...")
    import time
    time.sleep(5)
    test_groq_batch()
    
    print("\n" + "=" * 60)
    print("[OK] Testing Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Document results in TESTING_RESULTS.md")
    print("2. Test Gemini API (test_gemini_api.py)")
    print("3. Compare quality and speed")
    
    # Collect API test results for JSON output
    api_key = os.environ.get("GROQ_API_KEY")
    
    try:
        if api_key:
            # Test a simple summarization to show Groq is working
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            
            test_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an AI assistant. Return only JSON."},
                    {"role": "user", "content": "Return JSON: {\"test\": \"success\", \"model\": \"llama-3.3-70b-versatile\"}"}
                ],
                temperature=0.0,
                max_tokens=100
            )
            
            result = {
                "api_status": "working",
                "model": "llama-3.3-70b-versatile",
                "response": test_response.choices[0].message.content,
                # pyrefly: ignore [missing-attribute]
                "tokens_used": test_response.usage.total_tokens
            }
        else:
            result = {"api_status": "no_api_key", "error": "GROQ_API_KEY not found"}
        
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "groq_api",
            "collected_at": datetime.now().isoformat(),
            "data": result
        }, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({"source": "groq_api", "error": str(e), "data": {}}, indent=2))
