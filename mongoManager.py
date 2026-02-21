"""
MongoDB State Management for Test Cycle AI Automation
Handles test execution state, self-healing decisions, and multi-tenant data isolation
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoDBManager:
    """
    Centralized MongoDB manager for test automation state management
    Supports multi-tenant (8 hospital clients) with database-per-tenant strategy
    """
    
    def __init__(self, hospital_id: str, connection_string: str = "mongodb://localhost:27017/"):
        """
        Initialize MongoDB connection for specific hospital
        
        Args:
            hospital_id: Unique identifier for hospital (e.g., 'client_A', 'client_B')
            connection_string: MongoDB connection URI
        """
        self.hospital_id = hospital_id
        self.client = MongoClient(
            connection_string,
            maxPoolSize=50,
            retryWrites=True,
            serverSelectionTimeoutMS=5000
        )
        
        # Database per tenant for data isolation
        self.db = self.client[f"test_automation_{hospital_id}"]
        self.shared_db = self.client["test_automation_shared"]
        
        # Collection references
        self.test_cases = self.db.test_cases
        self.executions = self.db.test_executions
        self.self_heal = self.db.self_heal_decisions
        self.ui_snapshots = self.db.ui_snapshots
        self.code_changes = self.db.code_changes
        self.llm_cache = self.db.llm_context_cache
        
        self._ensure_indexes()
        logger.info(f"MongoDB Manager initialized for hospital: {hospital_id}")
    
    def _ensure_indexes(self):
        """Create necessary indexes for performance"""
        # Test cases indexes
        self.test_cases.create_index([("test_id", ASCENDING)], unique=True)
        self.test_cases.create_index([("status", ASCENDING), ("last_modified", DESCENDING)])
        self.test_cases.create_index([("tags", ASCENDING)])
        
        # Executions indexes
        self.executions.create_index([("test_case_id", ASCENDING), ("timestamp", DESCENDING)])
        self.executions.create_index([("status", ASCENDING), ("timestamp", DESCENDING)])
        self.executions.create_index([("hospital", ASCENDING), ("timestamp", DESCENDING)])
        
        # Self-heal indexes
        self.self_heal.create_index([("test_id", ASCENDING), ("timestamp", DESCENDING)])
        self.self_heal.create_index([("engineer_approved", ASCENDING)])
        
        logger.info("Database indexes ensured")
    
    # ==================== TEST CASE MANAGEMENT ====================
    
    def create_test_case(self, test_case: Dict[str, Any]) -> str:
        """
        Store a new test case with metadata
        
        Args:
            test_case: Test case document
            
        Returns:
            test_id of created test case
        """
        test_case.update({
            "hospital": self.hospital_id,
            "created_at": datetime.utcnow(),
            "last_modified": datetime.utcnow(),
            "status": "active"
        })
        
        try:
            result = self.test_cases.insert_one(test_case)
            logger.info(f"Created test case: {test_case.get('test_id')}")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Test case {test_case.get('test_id')} already exists")
            raise
    
    def get_test_case(self, test_id: str) -> Optional[Dict]:
        """Retrieve test case by ID"""
        return self.test_cases.find_one({"test_id": test_id})
    
    def update_test_case(self, test_id: str, updates: Dict[str, Any]) -> bool:
        """Update test case with new data"""
        updates["last_modified"] = datetime.utcnow()
        result = self.test_cases.update_one(
            {"test_id": test_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    # ==================== TEST EXECUTION TRACKING ====================
    
    def record_execution(self, execution_data: Dict[str, Any]) -> str:
        """
        Record test execution result with full context
        
        Args:
            execution_data: Execution details including status, duration, screenshots, etc.
            
        Returns:
            execution_id
        """
        execution_data.update({
            "hospital": self.hospital_id,
            "timestamp": datetime.utcnow()
        })
        
        result = self.executions.insert_one(execution_data)
        logger.info(f"Recorded execution for test: {execution_data.get('test_case_id')}")
        return str(result.inserted_id)
    
    def get_execution_history(
        self, 
        test_case_id: str, 
        limit: int = 10
    ) -> List[Dict]:
        """Get recent execution history for a test case"""
        return list(
            self.executions.find({"test_case_id": test_case_id})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
    
    def get_flaky_tests(self, pass_rate_min: float = 0.3, pass_rate_max: float = 0.7) -> List[Dict]:
        """
        Identify flaky tests across all executions
        Flaky = tests with pass rate between 30-70%
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$test_case_id",
                    "total_runs": {"$sum": 1},
                    "pass_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "passed"]}, 1, 0]}
                    },
                    "latest_execution": {"$max": "$timestamp"}
                }
            },
            {
                "$addFields": {
                    "pass_rate": {"$divide": ["$pass_count", "$total_runs"]}
                }
            },
            {
                "$match": {
                    "pass_rate": {"$gte": pass_rate_min, "$lte": pass_rate_max},
                    "total_runs": {"$gte": 5}  # At least 5 runs to be statistically valid
                }
            },
            {"$sort": {"pass_rate": ASCENDING}}
        ]
        
        return list(self.executions.aggregate(pipeline))
    
    # ==================== SELF-HEALING STATE MANAGEMENT ====================
    
    def record_self_heal_decision(self, heal_data: Dict[str, Any]) -> str:
        """
        Record a self-healing decision for audit and learning
        
        Example heal_data:
        {
            "test_id": "TC_LOGIN_001",
            "failure_reason": "Element not found: #submit-btn",
            "ui_change_detected": {
                "old_selector": "#submit-btn",
                "new_selector": "#submit-button-v2",
                "confidence": 0.95
            },
            "fix_applied": {
                "file": "tests/login.py",
                "line": 45,
                "change": "page.click('#submit-button-v2')"
            },
            "engineer_approved": False  # Pending approval
        }
        """
        heal_data.update({
            "hospital": self.hospital_id,
            "timestamp": datetime.utcnow(),
            "engineer_approved": heal_data.get("engineer_approved", False)
        })
        
        result = self.self_heal.insert_one(heal_data)
        logger.info(f"Recorded self-heal decision for test: {heal_data.get('test_id')}")
        return str(result.inserted_id)
    
    def get_pending_approvals(self) -> List[Dict]:
        """Get self-heal decisions awaiting engineer approval"""
        return list(
            self.self_heal.find({"engineer_approved": False})
            .sort("timestamp", DESCENDING)
        )
    
    def approve_self_heal(self, heal_id: str, engineer_notes: str = "") -> bool:
        """Engineer approves a self-healing fix"""
        result = self.self_heal.update_one(
            {"_id": heal_id},
            {
                "$set": {
                    "engineer_approved": True,
                    "approved_at": datetime.utcnow(),
                    "engineer_notes": engineer_notes
                }
            }
        )
        return result.modified_count > 0
    
    def find_similar_past_heals(self, failure_reason: str, limit: int = 5) -> List[Dict]:
        """
        Find similar past self-healing decisions (text search)
        Useful for suggesting fixes based on historical data
        """
        # Simple text matching - upgrade to vector search for better results
        return list(
            self.self_heal.find(
                {
                    "$text": {"$search": failure_reason},
                    "engineer_approved": True
                }
            )
            .limit(limit)
        )
    
    # ==================== UI SNAPSHOT TRACKING ====================
    
    def save_ui_snapshot(self, ui_data: Dict[str, Any]) -> str:
        """
        Save UI structure from browser-use for change detection
        
        Args:
            ui_data: UI metadata (selectors, hierarchy, screenshots)
        """
        ui_data.update({
            "hospital": self.hospital_id,
            "timestamp": datetime.utcnow()
        })
        
        result = self.ui_snapshots.insert_one(ui_data)
        return str(result.inserted_id)
    
    def get_latest_ui_snapshot(self, page_identifier: str) -> Optional[Dict]:
        """Get most recent UI snapshot for a page"""
        return self.ui_snapshots.find_one(
            {"page_identifier": page_identifier},
            sort=[("timestamp", DESCENDING)]
        )
    
    def detect_ui_changes(self, page_identifier: str, current_snapshot: Dict) -> Dict:
        """
        Compare current UI snapshot with previous to detect changes
        Returns diff of what changed
        """
        previous = self.get_latest_ui_snapshot(page_identifier)
        if not previous:
            return {"is_new": True, "changes": []}
        
        changes = []
        prev_selectors = set(previous.get("selectors", []))
        curr_selectors = set(current_snapshot.get("selectors", []))
        
        removed = prev_selectors - curr_selectors
        added = curr_selectors - prev_selectors
        
        if removed:
            changes.append({"type": "removed", "selectors": list(removed)})
        if added:
            changes.append({"type": "added", "selectors": list(added)})
        
        return {
            "is_new": False,
            "has_changes": len(changes) > 0,
            "changes": changes,
            "previous_timestamp": previous.get("timestamp")
        }
    
    # ==================== LLM CONTEXT CACHING ====================
    
    def cache_llm_context(self, prompt_hash: str, context_data: Dict[str, Any], ttl_hours: int = 24):
        """
        Cache LLM prompt context to avoid redundant vector searches
        
        Args:
            prompt_hash: Hash of the prompt for cache key
            context_data: Retrieved context (test cases, embeddings, etc.)
            ttl_hours: Time-to-live in hours
        """
        expiry = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        self.llm_cache.update_one(
            {"prompt_hash": prompt_hash},
            {
                "$set": {
                    "context_data": context_data,
                    "created_at": datetime.utcnow(),
                    "expires_at": expiry
                }
            },
            upsert=True
        )
    
    def get_cached_context(self, prompt_hash: str) -> Optional[Dict]:
        """Retrieve cached LLM context if not expired"""
        cached = self.llm_cache.find_one({
            "prompt_hash": prompt_hash,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        return cached.get("context_data") if cached else None
    
    # ==================== ANALYTICS & REPORTING ====================
    
    def get_self_heal_success_rate(self, days: int = 30) -> float:
        """Calculate self-healing success rate over time period"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "approved": {
                        "$sum": {"$cond": [{"$eq": ["$engineer_approved", True]}, 1, 0]}
                    }
                }
            }
        ]
        
        result = list(self.self_heal.aggregate(pipeline))
        if result:
            return result[0]["approved"] / result[0]["total"]
        return 0.0
    
    def get_test_execution_stats(self, days: int = 7) -> Dict:
        """Get execution statistics for dashboard"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$duration_ms"}
                }
            }
        ]
        
        results = list(self.executions.aggregate(pipeline))
        return {r["_id"]: {"count": r["count"], "avg_duration_ms": r["avg_duration"]} for r in results}
    
    def health_check(self) -> bool:
        """Verify MongoDB connection is healthy"""
        try:
            self.client.admin.command('ping')
            return True
        except ConnectionFailure:
            logger.error("MongoDB connection failed")
            return False


# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    # Initialize for hospital client A
    db_manager = MongoDBManager(hospital_id="client_A")
    
    # Example 1: Create a test case
    test_case = {
        "test_id": "TC_PATIENT_REG_001",
        "name": "Patient Registration - Epic v2025.11",
        "description": "Verify patient can register with insurance info",
        "steps": [
            "Navigate to patient registration",
            "Fill personal details",
            "Add insurance information",
            "Submit form"
        ],
        "selectors": {
            "first_name": "#patient-first-name",
            "last_name": "#patient-last-name",
            "submit": "#submit-registration"
        },
        "tags": ["patient", "registration", "epic"],
        "epic_version": "2025.11"
    }
    
    try:
        test_id = db_manager.create_test_case(test_case)
        print(f"Created test case: {test_id}")
    except DuplicateKeyError:
        print("Test case already exists")
    
    # Example 2: Record test execution
    execution = {
        "test_case_id": "TC_PATIENT_REG_001",
        "status": "failed",
        "duration_ms": 5200,
        "failure_reason": "Element not found: #submit-registration",
        "screenshot_path": "/screenshots/failure_001.png",
        "execution_context": {
            "browser": "chromium",
            "viewport": "1920x1080"
        }
    }
    
    exec_id = db_manager.record_execution(execution)
    print(f"Recorded execution: {exec_id}")
    
    # Example 3: Record self-healing decision
    heal_decision = {
        "test_id": "TC_PATIENT_REG_001",
        "failure_reason": "Element not found: #submit-registration",
        "ui_change_detected": {
            "old_selector": "#submit-registration",
            "new_selector": "#submit-registration-btn-v2",
            "confidence": 0.92,
            "detection_method": "browser-use + LLaMA analysis"
        },
        "fix_applied": {
            "file": "tests/patient_registration.py",
            "line": 78,
            "old_code": "page.click('#submit-registration')",
            "new_code": "page.click('#submit-registration-btn-v2')"
        },
        "engineer_approved": False
    }
    
    heal_id = db_manager.record_self_heal_decision(heal_decision)
    print(f"Recorded self-heal decision: {heal_id}")
    
    # Example 4: Get flaky tests
    flaky_tests = db_manager.get_flaky_tests()
    print(f"\nFlaky tests found: {len(flaky_tests)}")
    for test in flaky_tests:
        print(f"  - {test['_id']}: {test['pass_rate']:.2%} pass rate")
    
    # Example 5: Get self-heal success rate
    success_rate = db_manager.get_self_heal_success_rate(days=30)
    print(f"\nSelf-heal success rate (30 days): {success_rate:.2%}")
    
    # Example 6: Get execution stats
    stats = db_manager.get_test_execution_stats(days=7)
    print(f"\nExecution stats (7 days): {stats}")
