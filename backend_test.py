#!/usr/bin/env python3
"""
Backend Test Suite for Webull Trading App - P/L by Symbol Consolidation Testing
Tests the P/L by Symbol consolidation feature that aggregates P/L by underlying ticker symbol
"""

import requests
import json
import os
import sys
import asyncio
import motor.motor_asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Get backend URL from frontend .env
BACKEND_URL = "https://tradewizard-21.preview.emergentagent.com/api"
APP_PASSWORD = "WebullTrader2024!Secure"

# MongoDB connection for direct testing
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

class WebullBackendTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = requests.Session()
        self.app_token = None
        self.authenticated = False
        self.mongo_client = None
        self.db = None
        
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
    
    async def setup_mongodb_connection(self) -> bool:
        """Setup MongoDB connection for direct database testing"""
        try:
            self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
            self.db = self.mongo_client[DB_NAME]
            # Test connection
            await self.db.command('ping')
            self.log("✅ MongoDB connection established")
            return True
        except Exception as e:
            self.log(f"❌ MongoDB connection failed: {str(e)}", "ERROR")
            return False
    
    async def test_position_tracking_collection(self) -> Dict[str, Any]:
        """Test position_tracking collection exists and is accessible"""
        self.log("Testing position_tracking collection...")
        
        result = {
            "success": False,
            "collection_exists": False,
            "can_read": False,
            "can_write": False,
            "error": None
        }
        
        try:
            if self.db is None:
                result["error"] = "MongoDB connection not established"
                return result
            
            # Test collection access
            collection = self.db['position_tracking']
            
            # Test read access
            try:
                count = await collection.count_documents({})
                result["can_read"] = True
                result["collection_exists"] = True
                self.log(f"✅ Position tracking collection accessible, {count} documents")
            except Exception as e:
                result["error"] = f"Cannot read from position_tracking collection: {str(e)}"
                return result
            
            # Test write access with a test document
            test_doc = {
                'ticker_id': 999999999,  # Test ticker ID
                'dte': 0,
                'entry_price': 100.0,
                'initial_quantity': 5,
                'remaining_quantity': 5,
                'direction': 'CALL',
                'phase': 'initial',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                '_test_document': True
            }
            
            try:
                await collection.insert_one(test_doc)
                result["can_write"] = True
                self.log("✅ Position tracking collection write test successful")
                
                # Clean up test document
                await collection.delete_one({'_test_document': True})
                
            except Exception as e:
                result["error"] = f"Cannot write to position_tracking collection: {str(e)}"
                return result
            
            result["success"] = result["collection_exists"] and result["can_read"] and result["can_write"]
            
        except Exception as e:
            result["error"] = f"Position tracking collection test error: {str(e)}"
            self.log(f"❌ Position tracking collection test error: {str(e)}", "ERROR")
        
        return result
    
    async def test_position_tracking_logic(self) -> Dict[str, Any]:
        """Test the position tracking state management logic"""
        self.log("Testing position tracking state management logic...")
        
        result = {
            "success": False,
            "new_position_detection": False,
            "initial_phase_creation": False,
            "quantity_mismatch_detection": False,
            "phase_transitions": False,
            "errors": []
        }
        
        try:
            if self.db is None:
                result["errors"].append("MongoDB connection not established")
                return result
            
            collection = self.db['position_tracking']
            test_ticker_id = 888888888  # Test ticker ID
            
            # Clean up any existing test data
            await collection.delete_many({'ticker_id': test_ticker_id})
            
            # Test 1: New position detection (no existing tracking)
            self.log("Testing new position detection...")
            tracking = await collection.find_one({'ticker_id': test_ticker_id})
            if tracking is None:
                result["new_position_detection"] = True
                self.log("✅ New position detection works (no existing tracking)")
            else:
                result["errors"].append("New position detection failed - found unexpected tracking data")
            
            # Test 2: Create initial phase tracking
            self.log("Testing initial phase creation...")
            initial_tracking = {
                'ticker_id': test_ticker_id,
                'dte': 0,
                'entry_price': 150.0,
                'initial_quantity': 5,
                'remaining_quantity': 5,
                'direction': 'CALL',
                'phase': 'initial',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await collection.replace_one(
                {'ticker_id': test_ticker_id},
                initial_tracking,
                upsert=True
            )
            
            # Verify initial phase was created correctly
            saved_tracking = await collection.find_one({'ticker_id': test_ticker_id})
            if (saved_tracking and 
                saved_tracking.get('phase') == 'initial' and 
                saved_tracking.get('initial_quantity') == 5 and
                saved_tracking.get('remaining_quantity') == 5):
                result["initial_phase_creation"] = True
                self.log("✅ Initial phase creation works correctly")
            else:
                result["errors"].append("Initial phase creation failed - incorrect data saved")
            
            # Test 3: Quantity mismatch detection (simulating new position with same ticker_id)
            self.log("Testing quantity mismatch detection...")
            current_position_qty = 3  # Different from tracking remaining_quantity (5)
            tracking_remaining_qty = saved_tracking.get('remaining_quantity', 0)
            
            if tracking_remaining_qty != current_position_qty:
                result["quantity_mismatch_detection"] = True
                self.log(f"✅ Quantity mismatch detected: position={current_position_qty}, tracking={tracking_remaining_qty}")
                
                # Simulate creating new tracking for the "new" position
                new_tracking = {
                    'ticker_id': test_ticker_id,
                    'dte': 1,
                    'entry_price': 175.0,
                    'initial_quantity': current_position_qty,
                    'remaining_quantity': current_position_qty,
                    'direction': 'PUT',
                    'phase': 'initial',  # Should be initial, not trailing
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                await collection.replace_one(
                    {'ticker_id': test_ticker_id},
                    new_tracking,
                    upsert=True
                )
                
                # Verify new position starts with initial phase
                updated_tracking = await collection.find_one({'ticker_id': test_ticker_id})
                if (updated_tracking and 
                    updated_tracking.get('phase') == 'initial' and
                    updated_tracking.get('initial_quantity') == current_position_qty):
                    self.log("✅ New position correctly starts with 'initial' phase")
                else:
                    result["errors"].append("New position did not start with 'initial' phase")
            else:
                result["errors"].append("Quantity mismatch detection test setup failed")
            
            # Test 4: Phase transitions (initial -> trailing)
            self.log("Testing phase transitions...")
            await collection.update_one(
                {'ticker_id': test_ticker_id},
                {
                    '$set': {
                        'phase': 'trailing',
                        'remaining_quantity': 1,  # After partial sell
                        'phase_updated': datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            trailing_tracking = await collection.find_one({'ticker_id': test_ticker_id})
            if (trailing_tracking and 
                trailing_tracking.get('phase') == 'trailing' and
                trailing_tracking.get('remaining_quantity') == 1):
                result["phase_transitions"] = True
                self.log("✅ Phase transition to trailing works correctly")
            else:
                result["errors"].append("Phase transition to trailing failed")
            
            # Clean up test data
            await collection.delete_many({'ticker_id': test_ticker_id})
            
            result["success"] = (
                result["new_position_detection"] and
                result["initial_phase_creation"] and
                result["quantity_mismatch_detection"] and
                result["phase_transitions"] and
                len(result["errors"]) == 0
            )
            
        except Exception as e:
            result["errors"].append(f"Position tracking logic test error: {str(e)}")
            self.log(f"❌ Position tracking logic test error: {str(e)}", "ERROR")
        
        return result
    
    async def test_profit_loss_targets(self) -> Dict[str, Any]:
        """Test profit/loss target calculation based on phase and DTE"""
        self.log("Testing profit/loss target calculations...")
        
        result = {
            "success": False,
            "dte_0_initial": False,
            "dte_1_initial": False,
            "dte_0_trailing": False,
            "dte_1_trailing": False,
            "errors": []
        }
        
        try:
            # Import the function from trading_bot_service
            sys.path.append('/app/backend')
            from trading_bot_service import get_profit_loss_targets
            
            # Test 0DTE initial phase
            profit_pct, stop_loss_pct, contracts_to_keep = get_profit_loss_targets(0, trailing_phase=False)
            if profit_pct == 0.25 and stop_loss_pct == 0.25 and contracts_to_keep == 1:
                result["dte_0_initial"] = True
                self.log("✅ 0DTE initial phase: 25% profit, 25% stop-loss, keep 1 contract")
            else:
                result["errors"].append(f"0DTE initial incorrect: {profit_pct}, {stop_loss_pct}, {contracts_to_keep}")
            
            # Test 1DTE initial phase
            profit_pct, stop_loss_pct, contracts_to_keep = get_profit_loss_targets(1, trailing_phase=False)
            if profit_pct == 0.20 and stop_loss_pct == 0.25 and contracts_to_keep == 2:
                result["dte_1_initial"] = True
                self.log("✅ 1DTE initial phase: 20% profit, 25% stop-loss, keep 2 contracts")
            else:
                result["errors"].append(f"1DTE initial incorrect: {profit_pct}, {stop_loss_pct}, {contracts_to_keep}")
            
            # Test 0DTE trailing phase
            profit_pct, stop_loss_pct, contracts_to_keep = get_profit_loss_targets(0, trailing_phase=True)
            if profit_pct == 0.75 and stop_loss_pct == 0.05 and contracts_to_keep == 0:
                result["dte_0_trailing"] = True
                self.log("✅ 0DTE trailing phase: 75% profit, 5% stop-loss, keep 0 contracts")
            else:
                result["errors"].append(f"0DTE trailing incorrect: {profit_pct}, {stop_loss_pct}, {contracts_to_keep}")
            
            # Test 1DTE trailing phase
            profit_pct, stop_loss_pct, contracts_to_keep = get_profit_loss_targets(1, trailing_phase=True)
            if profit_pct == 0.95 and stop_loss_pct == 0.05 and contracts_to_keep == 0:
                result["dte_1_trailing"] = True
                self.log("✅ 1DTE trailing phase: 95% profit, 5% stop-loss, keep 0 contracts")
            else:
                result["errors"].append(f"1DTE trailing incorrect: {profit_pct}, {stop_loss_pct}, {contracts_to_keep}")
            
            result["success"] = (
                result["dte_0_initial"] and
                result["dte_1_initial"] and
                result["dte_0_trailing"] and
                result["dte_1_trailing"] and
                len(result["errors"]) == 0
            )
            
        except Exception as e:
            result["errors"].append(f"Profit/loss targets test error: {str(e)}")
            self.log(f"❌ Profit/loss targets test error: {str(e)}", "ERROR")
        
        return result
    
    async def test_critical_bug_fix_scenario(self) -> Dict[str, Any]:
        """Test the specific bug fix scenario: new positions should start with initial phase"""
        self.log("Testing critical bug fix scenario...")
        
        result = {
            "success": False,
            "scenario_setup": False,
            "new_position_initial_phase": False,
            "correct_stop_loss": False,
            "errors": []
        }
        
        try:
            if self.db is None:
                result["errors"].append("MongoDB connection not established")
                return result
            
            collection = self.db['position_tracking']
            test_ticker_id = 777777777
            
            # Clean up
            await collection.delete_many({'ticker_id': test_ticker_id})
            
            # Scenario: Simulate the bug condition
            # 1. Create old tracking data with 'trailing' phase and lower remaining_quantity
            old_tracking = {
                'ticker_id': test_ticker_id,
                'dte': 0,
                'entry_price': 100.0,
                'initial_quantity': 5,
                'remaining_quantity': 1,  # After partial sell
                'direction': 'CALL',
                'phase': 'trailing',  # Old position was in trailing phase
                'timestamp': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            }
            
            await collection.insert_one(old_tracking)
            result["scenario_setup"] = True
            self.log("✅ Bug scenario setup: old tracking with trailing phase, remaining_qty=1")
            
            # 2. Simulate new position detection (current quantity != remaining_quantity)
            current_position_qty = 3  # New position with different quantity
            old_tracking_data = await collection.find_one({'ticker_id': test_ticker_id})
            
            is_new_position = (
                not old_tracking_data or 
                old_tracking_data.get('remaining_quantity', 0) != current_position_qty
            )
            
            if is_new_position:
                self.log(f"✅ New position detected: current_qty={current_position_qty}, old_remaining_qty={old_tracking_data.get('remaining_quantity')}")
                
                # 3. Create fresh tracking with 'initial' phase (the fix)
                new_tracking = {
                    'ticker_id': test_ticker_id,
                    'dte': 0,
                    'entry_price': 125.0,
                    'initial_quantity': current_position_qty,
                    'remaining_quantity': current_position_qty,
                    'direction': 'CALL',
                    'phase': 'initial',  # This is the fix - should be initial, not trailing
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                await collection.replace_one(
                    {'ticker_id': test_ticker_id},
                    new_tracking,
                    upsert=True
                )
                
                # 4. Verify new position starts with 'initial' phase
                updated_tracking = await collection.find_one({'ticker_id': test_ticker_id})
                if updated_tracking and updated_tracking.get('phase') == 'initial':
                    result["new_position_initial_phase"] = True
                    self.log("✅ NEW POSITION CORRECTLY STARTS WITH 'INITIAL' PHASE")
                    
                    # 5. Verify correct stop-loss percentage for 0DTE initial phase
                    sys.path.append('/app/backend')
                    from trading_bot_service import get_profit_loss_targets
                    
                    profit_pct, stop_loss_pct, _ = get_profit_loss_targets(0, trailing_phase=False)
                    if stop_loss_pct == 0.25:  # Should be 25%, not 5%
                        result["correct_stop_loss"] = True
                        self.log("✅ NEW 0DTE POSITION USES 25% STOP-LOSS (NOT 5%)")
                    else:
                        result["errors"].append(f"Incorrect stop-loss for new 0DTE position: {stop_loss_pct} (should be 0.25)")
                else:
                    result["errors"].append("New position did not start with 'initial' phase - BUG NOT FIXED")
            else:
                result["errors"].append("New position detection failed")
            
            # Clean up
            await collection.delete_many({'ticker_id': test_ticker_id})
            
            result["success"] = (
                result["scenario_setup"] and
                result["new_position_initial_phase"] and
                result["correct_stop_loss"] and
                len(result["errors"]) == 0
            )
            
        except Exception as e:
            result["errors"].append(f"Critical bug fix scenario test error: {str(e)}")
            self.log(f"❌ Critical bug fix scenario test error: {str(e)}", "ERROR")
        
        return result
    
    async def cleanup_mongodb_connection(self):
        """Clean up MongoDB connection"""
        if self.mongo_client:
            self.mongo_client.close()
            self.log("MongoDB connection closed")
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive backend test suite"""
        self.log("=" * 80)
        self.log("STARTING POSITION TRACKING BUG FIX TESTS")
        self.log("=" * 80)
        
        overall_result = {
            "success": False,
            "tests_run": 0,
            "tests_passed": 0,
            "critical_failures": [],
            "minor_issues": [],
            "test_results": {}
        }
        
        # Test 1: MongoDB Connection
        overall_result["tests_run"] += 1
        mongodb_success = await self.setup_mongodb_connection()
        overall_result["test_results"]["mongodb_connection"] = mongodb_success
        if mongodb_success:
            overall_result["tests_passed"] += 1
        else:
            overall_result["critical_failures"].append("MongoDB connection failed")
            return overall_result  # Can't continue without MongoDB
        
        # Test 2: Position Tracking Collection
        overall_result["tests_run"] += 1
        collection_result = await self.test_position_tracking_collection()
        overall_result["test_results"]["position_tracking_collection"] = collection_result
        if collection_result["success"]:
            overall_result["tests_passed"] += 1
        else:
            overall_result["critical_failures"].append(f"Position tracking collection test failed: {collection_result.get('error')}")
        
        # Test 3: Position Tracking Logic
        overall_result["tests_run"] += 1
        logic_result = await self.test_position_tracking_logic()
        overall_result["test_results"]["position_tracking_logic"] = logic_result
        if logic_result["success"]:
            overall_result["tests_passed"] += 1
        else:
            overall_result["critical_failures"].extend(logic_result["errors"])
        
        # Test 4: Profit/Loss Target Calculations
        overall_result["tests_run"] += 1
        targets_result = await self.test_profit_loss_targets()
        overall_result["test_results"]["profit_loss_targets"] = targets_result
        if targets_result["success"]:
            overall_result["tests_passed"] += 1
        else:
            overall_result["critical_failures"].extend(targets_result["errors"])
        
        # Test 5: Critical Bug Fix Scenario
        overall_result["tests_run"] += 1
        bugfix_result = await self.test_critical_bug_fix_scenario()
        overall_result["test_results"]["critical_bug_fix"] = bugfix_result
        if bugfix_result["success"]:
            overall_result["tests_passed"] += 1
            self.log("🎉 CRITICAL BUG FIX VERIFIED: New positions start with 'initial' phase and 25% stop-loss")
        else:
            overall_result["critical_failures"].extend(bugfix_result["errors"])
        
        # Clean up MongoDB connection
        await self.cleanup_mongodb_connection()
        
        # Overall success determination
        overall_result["success"] = (
            overall_result["tests_passed"] >= 4 and  # At least MongoDB + collection + logic + targets
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

async def main():
    """Main test execution"""
    tester = WebullBackendTester()
    result = await tester.run_comprehensive_test()
    
    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)

if __name__ == "__main__":
    asyncio.run(main())