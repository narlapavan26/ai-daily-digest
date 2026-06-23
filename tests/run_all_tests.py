"""
Comprehensive Test Runner - Run all API tests and collect data
Saves all outputs to tests/outputs/
"""
import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding — prevent charmap errors on Unicode output
# pyrefly: ignore [missing-attribute]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
# pyrefly: ignore [missing-attribute]
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Get paths
TESTS_DIR = Path(__file__).parent
OUTPUTS_DIR = TESTS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# Prefer conda `ai` env when present; otherwise use the interpreter running this script
_PREFERRED_AI = Path(r"C:\Users\narla\anaconda3\envs\ai\python.exe")
PYTHON_EXE = str(_PREFERRED_AI) if _PREFERRED_AI.is_file() else sys.executable

print("="*80)
print("AI/ML DAILY DIGEST - COMPREHENSIVE TEST SUITE")
print("="*80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Python: {PYTHON_EXE}")
print(f"Outputs: {OUTPUTS_DIR}")
print("="*80)

# Load .env
env_file = TESTS_DIR.parent / ".env"
if env_file.exists():
    print(f"[OK] Loading environment from: {env_file}\n")
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Test configuration
test_files = [
    ("Groq API", "test_groq_api.py"),
    ("ArXiv", "test_arxiv.py"),
    ("Reddit", "test_reddit.py"),
    ("Hacker News", "test_hackernews.py"),
    ("HuggingFace", "test_huggingface.py"),
    ("Semantic Scholar", "test_semantic_scholar.py"),
    ("Stack Overflow", "test_stackoverflow.py"),
    ("RSS Feeds", "test_rss_feeds.py"),
    ("GitHub", "test_github.py"),
]

# Results containers
all_results = {
    "test_suite": "AI/ML Daily Digest - Complete API Testing",
    "timestamp": datetime.now().isoformat(),
    "python_executable": PYTHON_EXE,
    "tests": [],
    "summary": {}
}

# Collected data from all APIs
collected_data = {
    "collection_date": datetime.now().isoformat(),
    "apis": {}
}

# Run each test
for test_name, test_file in test_files:
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}\n")
    
    test_result = {
        "name": test_name,
        "file": test_file,
        "started_at": datetime.now().isoformat(),
    }
    
    try:
        # Run test
        result = subprocess.run(
            [PYTHON_EXE, test_file],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300,
            cwd=TESTS_DIR,
            env=os.environ.copy()
        )
        
        # pyrefly: ignore [bad-typed-dict-key]
        test_result["exit_code"] = result.returncode
        test_result["status"] = "PASS" if result.returncode == 0 else "FAIL"
        test_result["completed_at"] = datetime.now().isoformat()
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        # Extract JSON data from output
        if "=== DATA OUTPUT ===" in result.stdout:
            try:
                json_start = result.stdout.index("=== DATA OUTPUT ===") + len("=== DATA OUTPUT ===")
                json_str = result.stdout[json_start:].strip()
                
                # Parse JSON
                api_data = json.loads(json_str)
                api_key = test_name.lower().replace(" ", "_")
                collected_data["apis"][api_key] = api_data
                
                # Count items — use total_* fields first, then scan lists (including nested)
                item_count = sum(
                    v for k, v in api_data.items()
                    if k.startswith("total_") and isinstance(v, int)
                )
                if item_count == 0:
                    for key, value in api_data.items():
                        if isinstance(value, list):
                            item_count += len(value)
                        elif isinstance(value, dict):
                            for subvalue in value.values():
                                if isinstance(subvalue, list):
                                    item_count += len(subvalue)
                
                print(f"[OK] Collected {item_count} items from {test_name}")
                
            except (ValueError, json.JSONDecodeError) as e:
                print(f"[WARN] Could not parse JSON from {test_name}: {str(e)}")
                collected_data["apis"][test_name.lower().replace(" ", "_")] = {
                    "error": "JSON parsing failed"
                }
        else:
            print(f"[SKIP] {test_name}: No data output (test needs update)")
            collected_data["apis"][test_name.lower().replace(" ", "_")] = {
                "status": "no_data_output"
            }
        
        # Extract metrics
        metrics = {
            "success_count": result.stdout.count("[OK]"),
            "failure_count": result.stdout.count("[ERROR]")
        }
        # pyrefly: ignore [bad-typed-dict-key]
        test_result["metrics"] = metrics
        
        if result.returncode == 0:
            print(f"\n[OK] {test_name}: PASSED")
        else:
            print(f"\n[ERROR] {test_name}: FAILED")
            
    except subprocess.TimeoutExpired:
        test_result["status"] = "TIMEOUT"
        test_result["error"] = "Test exceeded 60 second timeout"
        print(f"\n[TIMEOUT] {test_name}: TIMEOUT")
        collected_data["apis"][test_name.lower().replace(" ", "_")] = {"error": "timeout"}
        
    except Exception as e:
        test_result["status"] = "ERROR"
        test_result["error"] = str(e)
        print(f"\n[ERROR] {test_name}: ERROR - {str(e)}")
        collected_data["apis"][test_name.lower().replace(" ", "_")] = {"error": str(e)}
    
    all_results["tests"].append(test_result)

# Generate summary
print(f"\n{'='*80}")
print("TEST SUITE SUMMARY")
print(f"{'='*80}\n")

passed = sum(1 for t in all_results["tests"] if t.get("status") == "PASS")
failed = sum(1 for t in all_results["tests"] if t.get("status") in ["FAIL", "ERROR"])
timeout = sum(1 for t in all_results["tests"] if t.get("status") == "TIMEOUT")
total = len(all_results["tests"])

all_results["summary"] = {
    "total_tests": total,
    "passed": passed,
    "failed": failed,
    "timeout": timeout,
    "success_rate": f"{(passed/total*100):.1f}%" if total > 0 else "0%",
    "completed_at": datetime.now().isoformat()
}

print(f"Total Tests: {total}")
print(f"[OK] Passed: {passed}")
print(f"[ERROR] Failed: {failed}")
print(f"Success Rate: {all_results['summary']['success_rate']}")

# Save test results
output_file = OUTPUTS_DIR / "test_results.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)

print(f"\nTest results saved to: {output_file.relative_to(TESTS_DIR.parent)}")

# Save collected data
data_file = OUTPUTS_DIR / "collected_api_data.json"
with open(data_file, 'w', encoding='utf-8') as f:
    json.dump(collected_data, f, indent=2, ensure_ascii=False)

print(f"API data saved to: {data_file.relative_to(TESTS_DIR.parent)}")

# Print data collection summary
print(f"\n{'='*80}")
print("DATA COLLECTION SUMMARY")
print(f"{'='*80}\n")

for api_name, api_data in collected_data["apis"].items():
    if "error" in api_data:
        print(f"[ERROR] {api_name}: {api_data['error']}")
    elif "status" in api_data and api_data["status"] == "no_data_output":
        print(f"[SKIP] {api_name}: Test needs update")
    else:
        # Count items — use total_* fields first, then scan lists (including nested)
        item_count = sum(
            v for k, v in api_data.items()
            if k.startswith("total_") and isinstance(v, int)
        )
        if item_count == 0:
            for key, value in api_data.items():
                if isinstance(value, list):
                    item_count += len(value)
                elif isinstance(value, dict):
                    for subvalue in value.values():
                        if isinstance(subvalue, list):
                            item_count += len(subvalue)
        print(f"[OK] {api_name}: {item_count} items")

print(f"\n{'='*80}")
print("COMPREHENSIVE TEST SUITE COMPLETE!")
print(f"{'='*80}\n")

# Exit with appropriate code
sys.exit(0 if failed == 0 else 1)
