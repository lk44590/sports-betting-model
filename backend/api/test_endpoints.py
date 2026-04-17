"""
API endpoint testing and validation script.
Tests all endpoints and validates responses.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, data=None, params=None):
    """Test an API endpoint and return result."""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return {"success": False, "error": f"Unknown method: {method}"}
        
        response.raise_for_status()
        return {
            "success": True,
            "status": response.status_code,
            "data": response.json()
        }
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to server. Is it running?"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_result(test_name, result):
    """Print test result in formatted way."""
    if result["success"]:
        print(f"✅ {test_name}: PASSED (HTTP {result['status']})")
        if 'data' in result:
            print(f"   Response keys: {list(result['data'].keys())}")
    else:
        print(f"❌ {test_name}: FAILED")
        print(f"   Error: {result['error']}")
    return result["success"]

def run_all_tests():
    """Run comprehensive API tests."""
    print("=" * 70)
    print("SPORTS BETTING MODEL - API ENDPOINT TESTING")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    passed = 0
    failed = 0
    
    # Test 1: Root endpoint
    result = test_endpoint("GET", "/")
    if print_result("1. Root Endpoint", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Test 2: Model config
    result = test_endpoint("GET", "/api/model/config")
    if print_result("2. Model Config", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Test 3: Evaluate single bet
    test_bet = {
        "bet_id": "test-001",
        "sport": "NBA",
        "event": "Lakers vs Warriors",
        "event_id": "401234567",
        "market_type": "moneyline",
        "bet_type": "moneyline",
        "selection": "Lakers",
        "odds": -110,
        "model_probability": 0.55,
        "data_quality": 85,
        "sample_size": 35
    }
    result = test_endpoint("POST", "/api/model/evaluate", data=test_bet)
    if print_result("3. Evaluate Single Bet", result):
        passed += 1
        if result["success"]:
            data = result["data"]
            print(f"   EV: {data.get('ev_pct')}%")
            print(f"   Kelly Stake: ${data.get('stake')}")
            print(f"   Qualified: {data.get('qualified')}")
    else:
        failed += 1
    print()
    
    # Test 4: Evaluate batch
    test_bets = [
        {
            "bet_id": "test-002",
            "sport": "NBA",
            "event": "Game 1",
            "event_id": "401234568",
            "market_type": "moneyline",
            "bet_type": "moneyline",
            "selection": "Team A",
            "odds": -105,
            "model_probability": 0.52,
            "data_quality": 80,
            "sample_size": 30
        },
        {
            "bet_id": "test-003",
            "sport": "NHL",
            "event": "Game 2",
            "event_id": "501234569",
            "market_type": "moneyline",
            "bet_type": "moneyline",
            "selection": "Team B",
            "odds": +150,
            "model_probability": 0.42,
            "data_quality": 75,
            "sample_size": 25
        }
    ]
    result = test_endpoint("POST", "/api/model/evaluate-batch", data=test_bets)
    if print_result("4. Evaluate Batch", result):
        passed += 1
        if result["success"]:
            print(f"   Evaluated: {result['data'].get('total_evaluated')}")
            print(f"   Qualified: {result['data'].get('qualified_picks')}")
    else:
        failed += 1
    print()
    
    # Test 5: Today's picks
    result = test_endpoint("GET", "/api/picks/today")
    if print_result("5. Today's Picks", result):
        passed += 1
        if result["success"]:
            print(f"   Date: {result['data'].get('date')}")
            print(f"   Sports checked: {result['data'].get('sports_checked')}")
            print(f"   Candidates: {result['data'].get('total_candidates')}")
            print(f"   Qualified: {result['data'].get('qualified_picks')}")
    else:
        failed += 1
    print()
    
    # Test 6: Performance summary
    result = test_endpoint("GET", "/api/performance/summary")
    if print_result("6. Performance Summary", result):
        passed += 1
        if result["success"]:
            print(f"   Total Bets: {result['data'].get('total_bets')}")
            print(f"   ROI: {result['data'].get('roi_pct')}%")
    else:
        failed += 1
    print()
    
    # Test 7: Performance by sport
    result = test_endpoint("GET", "/api/performance/by-sport")
    if print_result("7. Performance by Sport", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Test 8: Bankroll status
    result = test_endpoint("GET", "/api/bankroll/status")
    if print_result("8. Bankroll Status", result):
        passed += 1
        if result["success"]:
            print(f"   Current: ${result['data'].get('current_bankroll')}")
            print(f"   Peak: ${result['data'].get('peak_bankroll')}")
            print(f"   Drawdown: {result['data'].get('current_drawdown_pct')}%")
    else:
        failed += 1
    print()
    
    # Test 9: Bankroll history
    result = test_endpoint("GET", "/api/bankroll/history", params={"days": 30})
    if print_result("9. Bankroll History", result):
        passed += 1
        if result["success"]:
            print(f"   Data points: {result['data'].get('data_points')}")
    else:
        failed += 1
    print()
    
    # Test 10: Open bets
    result = test_endpoint("GET", "/api/bets/open")
    if print_result("10. Open Bets", result):
        passed += 1
        if result["success"]:
            print(f"   Open bets: {result['data'].get('count')}")
    else:
        failed += 1
    print()
    
    # Test 11: Bet history
    result = test_endpoint("GET", "/api/bets/history", params={"days": 30})
    if print_result("11. Bet History", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Test 12: Data stats
    result = test_endpoint("GET", "/api/data/stats")
    if print_result("12. Data Stats", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Test 13: Active sports
    result = test_endpoint("GET", "/api/sports/active")
    if print_result("13. Active Sports", result):
        passed += 1
        if result["success"]:
            print(f"   Active: {len(result['data'].get('active_sports', []))} sports")
    else:
        failed += 1
    print()
    
    # Test 14: Place a test bet
    test_place_bet = {
        "bet_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "sport": "NBA",
        "event": "Test Game",
        "event_id": "test-123",
        "market_type": "moneyline",
        "bet_type": "moneyline",
        "selection": "Test Team",
        "odds": -110,
        "true_probability": 0.55,
        "ev_pct": 8.5,
        "edge_score": 75,
        "stake": 25.50,
        "stake_pct": 2.5,
        "date": datetime.now().strftime('%Y-%m-%d'),
        "notes": "Test bet from API testing"
    }
    result = test_endpoint("POST", "/api/bets/place", data=test_place_bet)
    if print_result("14. Place Bet", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Test 15: Update bankroll
    result = test_endpoint("POST", "/api/model/update-bankroll", 
                          params={"new_bankroll": 1500.00})
    if print_result("15. Update Bankroll", result):
        passed += 1
    else:
        failed += 1
    print()
    
    # Summary
    print("=" * 70)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} test(s) failed. Check errors above.")
    
    return failed == 0

if __name__ == "__main__":
    run_all_tests()
