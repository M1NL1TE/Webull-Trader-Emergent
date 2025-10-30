#!/usr/bin/env python3
"""
Backend Test Suite for Webull Trading App P/L Calculation
Tests the /api/account/activities endpoint and P/L calculation functionality
"""

import requests
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Get backend URL from frontend .env
BACKEND_URL = "https://webull-auto.preview.emergentagent.com/api"
APP_PASSWORD = "WebullTrader2024!Secure"

class WebullBackendTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = requests.Session()
        self.app_token = None
        self.authenticated = False
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def test_app_password_auth(self) -> bool:
        """Test app password authentication"""
        self.log("Testing app password authentication...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/auth/app-password",
                json={"password": APP_PASSWORD},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("token"):
                    self.app_token = data["token"]
                    self.log("✅ App password authentication successful")
                    return True
                else:
                    self.log(f"❌ App password auth failed: {data}", "ERROR")
                    return False
            else:
                self.log(f"❌ App password auth failed with status {response.status_code}: {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ App password auth error: {str(e)}", "ERROR")
            return False
    
    def test_session_restore(self) -> bool:
        """Test if there's an existing Webull session"""
        self.log("Testing session restore...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/auth/restore",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.authenticated = True
                    self.log("✅ Session restored successfully")
                    return True
                else:
                    self.log("⚠️ Session restore failed - no existing session")
                    return False
            else:
                self.log(f"⚠️ Session restore failed with status {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ Session restore error: {str(e)}", "ERROR")
            return False
    
    def test_activities_endpoint_structure(self) -> Dict[str, Any]:
        """Test the /api/account/activities endpoint structure"""
        self.log("Testing /api/account/activities endpoint structure...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/account/activities",
                timeout=30
            )
            
            result = {
                "success": False,
                "status_code": response.status_code,
                "response_data": None,
                "structure_valid": False,
                "pl_summary_present": False,
                "orders_present": False,
                "error": None
            }
            
            if response.status_code == 401:
                result["error"] = "Authentication required - no valid Webull session"
                self.log("⚠️ Activities endpoint requires authentication")
                return result
            elif response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
                self.log(f"❌ Activities endpoint failed with status {response.status_code}")
                return result
            
            try:
                data = response.json()
                result["response_data"] = data
                
                # Check response structure
                if isinstance(data, dict):
                    result["structure_valid"] = all(key in data for key in ["success", "code", "msg", "data"])
                    
                    if result["structure_valid"]:
                        data_section = data.get("data", {})
                        result["pl_summary_present"] = "pl_summary" in data_section
                        result["orders_present"] = "orders" in data_section
                        
                        if result["pl_summary_present"] and result["orders_present"]:
                            result["success"] = True
                            self.log("✅ Activities endpoint structure is valid")
                        else:
                            missing = []
                            if not result["pl_summary_present"]:
                                missing.append("pl_summary")
                            if not result["orders_present"]:
                                missing.append("orders")
                            result["error"] = f"Missing required fields in data: {missing}"
                            self.log(f"❌ Activities endpoint missing fields: {missing}")
                    else:
                        result["error"] = "Invalid response structure - missing required top-level fields"
                        self.log("❌ Activities endpoint has invalid structure")
                else:
                    result["error"] = "Response is not a JSON object"
                    self.log("❌ Activities endpoint returned non-object response")
                    
            except json.JSONDecodeError as e:
                result["error"] = f"Invalid JSON response: {str(e)}"
                self.log(f"❌ Activities endpoint returned invalid JSON: {str(e)}")
                
            return result
            
        except Exception as e:
            self.log(f"❌ Activities endpoint test error: {str(e)}", "ERROR")
            return {
                "success": False,
                "error": str(e),
                "status_code": None,
                "response_data": None,
                "structure_valid": False,
                "pl_summary_present": False,
                "orders_present": False
            }
    
    def test_pl_calculation_values(self, activities_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test P/L calculation values against expected results"""
        self.log("Testing P/L calculation values...")
        
        result = {
            "success": False,
            "pl_values": {},
            "expected_values": {
                "today": 0.0,
                "week": 0.0, 
                "month": -70.0,
                "year": -833.0,
                "all_time": -833.0
            },
            "matches": {},
            "errors": []
        }
        
        try:
            if not activities_data.get("success"):
                result["errors"].append("Activities data indicates failure")
                return result
                
            data_section = activities_data.get("response_data", {}).get("data", {})
            pl_summary = data_section.get("pl_summary", {})
            
            if not pl_summary:
                result["errors"].append("No pl_summary found in response")
                return result
            
            result["pl_values"] = pl_summary
            
            # Check each time period
            for period, expected_value in result["expected_values"].items():
                actual_value = pl_summary.get(period)
                
                if actual_value is None:
                    result["errors"].append(f"Missing {period} in pl_summary")
                    result["matches"][period] = False
                else:
                    # Convert to float for comparison
                    try:
                        actual_float = float(actual_value)
                        expected_float = float(expected_value)
                        
                        # Allow small floating point differences
                        matches = abs(actual_float - expected_float) < 0.01
                        result["matches"][period] = matches
                        
                        if matches:
                            self.log(f"✅ {period}: ${actual_float:.2f} matches expected ${expected_float:.2f}")
                        else:
                            self.log(f"❌ {period}: ${actual_float:.2f} does not match expected ${expected_float:.2f}")
                            result["errors"].append(f"{period}: got ${actual_float:.2f}, expected ${expected_float:.2f}")
                            
                    except (ValueError, TypeError) as e:
                        result["errors"].append(f"Invalid {period} value: {actual_value} ({str(e)})")
                        result["matches"][period] = False
            
            # Overall success if all periods match
            result["success"] = all(result["matches"].values()) and len(result["errors"]) == 0
            
            if result["success"]:
                self.log("✅ All P/L values match expected results")
            else:
                self.log(f"❌ P/L calculation has {len(result['errors'])} issues")
                
        except Exception as e:
            result["errors"].append(f"P/L calculation test error: {str(e)}")
            self.log(f"❌ P/L calculation test error: {str(e)}", "ERROR")
            
        return result
    
    def test_time_period_filtering(self, activities_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test that time period filtering is working correctly"""
        self.log("Testing time period filtering logic...")
        
        result = {
            "success": False,
            "orders_count": 0,
            "time_periods_logical": True,
            "errors": []
        }
        
        try:
            if not activities_data.get("success"):
                result["errors"].append("Activities data indicates failure")
                return result
                
            data_section = activities_data.get("response_data", {}).get("data", {})
            orders = data_section.get("orders", [])
            pl_summary = data_section.get("pl_summary", {})
            
            result["orders_count"] = len(orders) if isinstance(orders, list) else 0
            
            # Check logical consistency of time periods
            # all_time >= year >= month >= week >= today
            periods = ["today", "week", "month", "year", "all_time"]
            values = {}
            
            for period in periods:
                value = pl_summary.get(period, 0)
                try:
                    values[period] = float(value)
                except (ValueError, TypeError):
                    result["errors"].append(f"Invalid {period} value: {value}")
                    result["time_periods_logical"] = False
            
            if len(values) == len(periods):
                # Check logical ordering (considering negative values)
                # For P/L, we expect: |all_time| >= |year| >= |month| >= |week| >= |today|
                if not (abs(values["all_time"]) >= abs(values["year"]) >= abs(values["month"]) >= abs(values["week"]) >= abs(values["today"])):
                    # More flexible check - at least all_time should contain year, and year should contain month
                    if values["all_time"] != values["year"] and abs(values["all_time"]) < abs(values["year"]):
                        result["errors"].append("all_time P/L should be >= year P/L in absolute terms")
                        result["time_periods_logical"] = False
                    
                    if values["year"] != values["month"] and abs(values["year"]) < abs(values["month"]):
                        result["errors"].append("year P/L should be >= month P/L in absolute terms")
                        result["time_periods_logical"] = False
            
            result["success"] = result["time_periods_logical"] and len(result["errors"]) == 0
            
            if result["success"]:
                self.log("✅ Time period filtering appears logical")
            else:
                self.log("❌ Time period filtering has issues")
                
        except Exception as e:
            result["errors"].append(f"Time period filtering test error: {str(e)}")
            self.log(f"❌ Time period filtering test error: {str(e)}", "ERROR")
            
        return result
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive backend test suite"""
        self.log("=" * 60)
        self.log("STARTING WEBULL BACKEND P/L CALCULATION TESTS")
        self.log("=" * 60)
        
        overall_result = {
            "success": False,
            "tests_run": 0,
            "tests_passed": 0,
            "critical_failures": [],
            "minor_issues": [],
            "test_results": {}
        }
        
        # Test 1: App Password Authentication
        overall_result["tests_run"] += 1
        app_auth_success = self.test_app_password_auth()
        overall_result["test_results"]["app_password_auth"] = app_auth_success
        if app_auth_success:
            overall_result["tests_passed"] += 1
        else:
            overall_result["critical_failures"].append("App password authentication failed")
        
        # Test 2: Session Restore (optional)
        session_restored = self.test_session_restore()
        overall_result["test_results"]["session_restore"] = session_restored
        if not session_restored:
            overall_result["minor_issues"].append("No existing Webull session found - authentication required")
        
        # Test 3: Activities Endpoint Structure
        overall_result["tests_run"] += 1
        activities_result = self.test_activities_endpoint_structure()
        overall_result["test_results"]["activities_endpoint"] = activities_result
        
        if activities_result["success"]:
            overall_result["tests_passed"] += 1
            
            # Test 4: P/L Calculation Values (only if endpoint works)
            overall_result["tests_run"] += 1
            pl_result = self.test_pl_calculation_values(activities_result)
            overall_result["test_results"]["pl_calculation"] = pl_result
            
            if pl_result["success"]:
                overall_result["tests_passed"] += 1
            else:
                overall_result["critical_failures"].extend(pl_result["errors"])
            
            # Test 5: Time Period Filtering (only if endpoint works)
            overall_result["tests_run"] += 1
            time_result = self.test_time_period_filtering(activities_result)
            overall_result["test_results"]["time_filtering"] = time_result
            
            if time_result["success"]:
                overall_result["tests_passed"] += 1
            else:
                overall_result["minor_issues"].extend(time_result["errors"])
                
        else:
            if activities_result.get("status_code") == 401:
                overall_result["critical_failures"].append("Activities endpoint requires Webull authentication")
            else:
                overall_result["critical_failures"].append(f"Activities endpoint failed: {activities_result.get('error')}")
        
        # Overall success determination
        overall_result["success"] = (
            overall_result["tests_passed"] >= 2 and  # At least app auth + endpoint structure
            len(overall_result["critical_failures"]) == 0
        )
        
        # Summary
        self.log("=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)
        self.log(f"Tests Run: {overall_result['tests_run']}")
        self.log(f"Tests Passed: {overall_result['tests_passed']}")
        self.log(f"Critical Failures: {len(overall_result['critical_failures'])}")
        self.log(f"Minor Issues: {len(overall_result['minor_issues'])}")
        
        if overall_result["critical_failures"]:
            self.log("\nCRITICAL FAILURES:")
            for failure in overall_result["critical_failures"]:
                self.log(f"  ❌ {failure}")
        
        if overall_result["minor_issues"]:
            self.log("\nMINOR ISSUES:")
            for issue in overall_result["minor_issues"]:
                self.log(f"  ⚠️ {issue}")
        
        if overall_result["success"]:
            self.log("\n🎉 OVERALL RESULT: SUCCESS")
        else:
            self.log("\n💥 OVERALL RESULT: FAILURE")
        
        return overall_result

def main():
    """Main test execution"""
    tester = WebullBackendTester()
    result = tester.run_comprehensive_test()
    
    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)

if __name__ == "__main__":
    main()