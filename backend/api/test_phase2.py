"""
Phase 2 Feature Testing Script
Tests all new ML, NLP, and Odds API endpoints.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, data=None, params=None):
    """Test an API endpoint."""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, params=params, timeout=10)
        else:
            return {"success": False, "error": f"Unknown method: {method}"}
        
        response.raise_for_status()
        return {
            "success": True,
            "status": response.status_code,
            "data": response.json()
        }
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to server"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_result(test_name, result):
    """Print test result."""
    if result["success"]:
        print(f"✅ {test_name}: PASSED (HTTP {result['status']})")
        return True
    else:
        print(f"❌ {test_name}: FAILED")
        print(f"   Error: {result['error']}")
        return False

def run_phase2_tests():
    """Run all Phase 2 tests."""
    print("=" * 70)
    print("PHASE 2 FEATURE TESTING - ML, NLP, Odds API")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    passed = 0
    failed = 0
    
    # === ODDs API Tests ===
    print("📊 ODDs API TESTS")
    print("-" * 70)
    
    # 1. Odds API Status
    result = test_endpoint("GET", "/api/odds/status")
    if print_result("1. Odds API Status", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   Configured: {data.get('configured')}")
            print(f"   Requests today: {data.get('requests_today')}/{data.get('request_limit')}")
    else:
        failed += 1
    print()
    
    # 2. Odds API Sports
    result = test_endpoint("GET", "/api/odds/sports")
    if print_result("2. Odds API Sports", result):
        passed += 1
        if result["success"]:
            sports = result["data"].get("supported_sports", [])
            print(f"   Supported: {len(sports)} sports")
    else:
        failed += 1
    print()
    
    # 3. Live Odds (with ESPN fallback)
    result = test_endpoint("GET", "/api/odds/live", params={"sports": "NBA,NFL"})
    if print_result("3. Live Odds", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   Source: {data.get('source')}")
            print(f"   Candidates: {data.get('total_candidates')}")
            print(f"   Qualified: {data.get('qualified_picks')}")
    else:
        failed += 1
    print()
    
    # === ML/Neural Tests ===
    print("🧠 ML/NEURAL TESTS")
    print("-" * 70)
    
    # 4. Neural Model Status
    result = test_endpoint("GET", "/api/ml/neural/status")
    if print_result("4. Neural Model Status", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   TensorFlow: {data.get('tensorflow_available')}")
            print(f"   Model loaded: {data.get('model_loaded')}")
    else:
        failed += 1
    print()
    
    # 5. Neural Prediction
    test_candidate = {
        "bet_id": "test-neural-001",
        "sport": "NBA",
        "event": "Test Game",
        "event_id": "evt-test",
        "market_type": "moneyline",
        "bet_type": "moneyline",
        "selection": "Test Team",
        "odds": -110,
        "model_probability": 0.55,
        "data_quality": 85,
        "sample_size": 30
    }
    result = test_endpoint("POST", "/api/ml/neural/predict", data=test_candidate)
    if print_result("5. Neural Prediction", result):
        passed += 1
        if result["success"] and result["data"].get("success"):
            data = result["data"]
            print(f"   Probability: {data.get('probability')}")
            print(f"   Confidence: {data.get('confidence')}")
    else:
        failed += 1
    print()
    
    # === NLP/Sentiment Tests ===
    print("💬 NLP/SENTIMENT TESTS")
    print("-" * 70)
    
    # 6. Sentiment Analysis - Injury
    result = test_endpoint(
        "POST", 
        "/api/nlp/analyze",
        params={"text": "LeBron James questionable with hamstring injury", "category": "injury"}
    )
    if print_result("6. Sentiment - Injury", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   Sentiment: {data.get('sentiment')}")
            print(f"   Category: {data.get('category')}")
            print(f"   Impact: {data.get('impact_score')}")
            print(f"   Interpretation: {data.get('interpretation')}")
    else:
        failed += 1
    print()
    
    # 7. Sentiment Analysis - Momentum
    result = test_endpoint(
        "POST",
        "/api/nlp/analyze",
        params={"text": "Lakers on a 5-game winning streak, dominating opponents", "category": "momentum"}
    )
    if print_result("7. Sentiment - Momentum", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   Sentiment: {data.get('sentiment')}")
            print(f"   Impact: {data.get('impact_score')}")
    else:
        failed += 1
    print()
    
    # 8. Lineup Detection
    result = test_endpoint(
        "POST",
        "/api/nlp/detect-lineup",
        params={"text": "Stephen Curry will start tonight after returning from injury"}
    )
    if print_result("8. Lineup Detection", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   Detected: {data.get('detected')}")
            if data.get('detected'):
                print(f"   Type: {data.get('change_type')}")
                print(f"   Impact: {data.get('impact_score')}")
    else:
        failed += 1
    print()
    
    # 9. Team Sentiment Summary
    team_news = [
        {"text": "Lakers lose third straight game, defense struggling"},
        {"text": "Anthony Davis returns to practice, questionable for Friday"},
        {"text": "LeBron James scores 40 points in dominant performance"},
        {"text": "Lakers trade for defensive specialist at deadline"}
    ]
    result = test_endpoint(
        "POST",
        "/api/nlp/team-summary",
        data={"team": "Lakers", "news_items": team_news}
    )
    if print_result("9. Team Sentiment Summary", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   Team: {data.get('team')}")
            print(f"   Overall: {data.get('overall_sentiment')}")
            print(f"   News count: {data.get('news_count')}")
            print(f"   Impact: {data.get('impact_score')}")
    else:
        failed += 1
    print()
    
    # === Summary ===
    print("=" * 70)
    print(f"PHASE 2 TEST SUMMARY: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    
    if failed == 0:
        print("🎉 ALL PHASE 2 TESTS PASSED!")
    else:
        print(f"⚠️  {failed} test(s) failed. Check server is running on port 8000.")
    
    print("\nNext steps:")
    print("1. Get The Odds API key: https://the-odds-api.com/")
    print("2. Install TensorFlow: pip install tensorflow")
    print("3. Install Transformers: pip install transformers torch")
    print("4. Train neural network on historical data")
    
    return failed == 0

if __name__ == "__main__":
    run_phase2_tests()
