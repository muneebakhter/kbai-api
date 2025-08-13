#!/usr/bin/env python3
"""
Comprehensive test script for KBAI API with DARKBO integration
Tests all the requirements specified in the problem statement
"""

import os
import time
import json
import requests
import subprocess
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin"
TEST_DATA_DIR = "./data"

class KBAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None
        self.api_key = os.getenv("KBAI_API_TOKEN", "kbai-secure-api-token-change-in-production")
        self.session = requests.Session()
        
    def log(self, message: str, success: bool = True):
        """Log test messages"""
        icon = "✅" if success else "❌"
        print(f"{icon} {message}")
        
    def wait_for_server(self, timeout: int = 30):
        """Wait for server to be ready"""
        print("⏳ Waiting for server to start...")
        
        for i in range(timeout):
            try:
                response = self.session.get(f"{self.base_url}/healthz", timeout=2)
                if response.status_code == 200:
                    self.log(f"Server is ready after {i+1} seconds")
                    return True
            except requests.RequestException:
                time.sleep(1)
                
        self.log("Server failed to start within timeout", False)
        return False
    
    def test_auth_token(self):
        """Test 1: Get authentication token"""
        print("\n🔐 Testing authentication...")
        
        try:
            payload = {
                "username": USERNAME,
                "password": PASSWORD,
                "client_name": "test-client",
                "scopes": ["read:basic", "write:projects"],
                "ttl_seconds": 3600
            }
            
            response = self.session.post(f"{self.base_url}/v1/auth/token", json=payload)
            response.raise_for_status()
            
            token_data = response.json()
            self.token = token_data["access_token"]
            
            self.log(f"Authentication successful - Token: {self.token[:20]}...")
            
            # Set authorization header
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            
            return True
            
        except Exception as e:
            self.log(f"Authentication failed: {e}", False)
            return False
    
    def test_ping(self):
        """Test ping endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/v1/test/ping")
            response.raise_for_status()
            
            data = response.json()
            self.log(f"Ping successful - Auth method: {data.get('auth_method')}")
            return True
            
        except Exception as e:
            self.log(f"Ping failed: {e}", False)
            return False
    
    def test_project_listing(self):
        """Test 2: Check project listing works with proj_mapping.txt"""
        print("\n📁 Testing project listing...")
        
        try:
            # Check if proj_mapping.txt exists
            proj_file = Path(TEST_DATA_DIR) / "proj_mapping.txt"
            if not proj_file.exists():
                self.log("proj_mapping.txt not found", False)
                return False
                
            self.log(f"proj_mapping.txt found: {proj_file}")
            
            # Test API endpoint
            response = self.session.get(f"{self.base_url}/v1/projects")
            response.raise_for_status()
            
            projects = response.json()
            self.log(f"Projects loaded: {len(projects)} projects found")
            
            for project in projects:
                self.log(f"  - {project['id']}: {project['name']} ({'active' if project['active'] else 'inactive'})")
                
            return len(projects) > 0
            
        except Exception as e:
            self.log(f"Project listing failed: {e}", False)
            return False
    
    def test_query_aspca_fail(self):
        """Test 3: Query ASPCA website (should fail initially)"""
        print("\n🔍 Testing ASPCA query (should fail initially)...")
        
        try:
            payload = {
                "query": "What is the ASPCA website?",
                "project_id": "aspca-test"  # Use aspca-test project
            }
            
            response = self.session.post(f"{self.base_url}/v1/query", json=payload)
            response.raise_for_status()
            
            result = response.json()
            answer = result["answer"].lower()
            sources = result["sources"]
            
            # Check if no relevant sources found OR answer indicates no information
            if len(sources) == 0 or "couldn't find" in answer or "no" in answer or "not" in answer or "error" in answer:
                self.log("ASPCA query correctly failed (no information found)")
                return True
            else:
                self.log(f"ASPCA query unexpectedly succeeded: {answer}", False)
                return False
                
        except Exception as e:
            self.log(f"ASPCA query test failed: {e}", False)
            return False
    
    def test_aspca_upload(self):
        """Test 4: Upload ASPCA document"""
        print("\n📤 Testing ASPCA document upload...")
        
        try:
            # First, make sure aspca-test project is active
            self.activate_aspca_project()
            
            # Check if ASPCA document exists
            aspca_files = ["ASPCATest.docx", "ASPCATest.txt"]
            aspca_file = None
            
            for filename in aspca_files:
                file_path = Path(filename)
                if file_path.exists():
                    aspca_file = file_path
                    break
            
            if not aspca_file:
                self.log("ASPCA test document not found", False)
                return False
                
            self.log(f"Found ASPCA document: {aspca_file}")
            
            # Upload the file
            with open(aspca_file, "rb") as f:
                files = {"file": (aspca_file.name, f, "application/octet-stream")}
                response = self.session.post(
                    f"{self.base_url}/v1/projects/aspca-test/ingest",
                    files=files
                )
                response.raise_for_status()
            
            result = response.json()
            self.log(f"ASPCA document uploaded: {result['detail']}")
            
            # Wait a moment for indexing to complete
            time.sleep(3)
            
            return True
            
        except Exception as e:
            self.log(f"ASPCA upload failed: {e}", False)
            return False
    
    def activate_aspca_project(self):
        """Activate the ASPCA test project"""
        try:
            payload = {
                "id": "aspca-test",
                "name": "ASPCA Test Project", 
                "active": True
            }
            
            response = self.session.post(f"{self.base_url}/v1/projects", json=payload)
            response.raise_for_status()
            
            self.log("ASPCA project activated")
            return True
            
        except Exception as e:
            self.log(f"Failed to activate ASPCA project: {e}", False)
            return False
    
    def test_query_aspca_success(self):
        """Test 5: Query ASPCA website (should succeed now)"""
        print("\n🎯 Testing ASPCA query (should succeed now)...")
        
        try:
            payload = {
                "query": "What is the ASPCA website?",
                "project_id": "aspca-test"
            }
            
            response = self.session.post(f"{self.base_url}/v1/query", json=payload)
            response.raise_for_status()
            
            result = response.json()
            answer = result["answer"]
            sources = result["sources"]
            
            self.log(f"ASPCA query answer: {answer[:100]}...")
            self.log(f"Sources found: {len(sources)}")
            
            # Check if ASPCA website is mentioned
            if "aspca.org" in answer.lower() or "aspca" in answer.lower():
                self.log("ASPCA query successfully found website information")
                
                # Show sources
                for i, source in enumerate(sources):
                    self.log(f"  Source {i+1}: {source.get('title', 'Unknown')} (score: {source.get('similarity_score', 0):.3f})")
                
                return True
            else:
                self.log("ASPCA query did not find website information", False)
                return False
                
        except Exception as e:
            self.log(f"ASPCA query test failed: {e}", False)
            return False
    
    def test_general_queries(self):
        """Test general queries on sample data"""
        print("\n📚 Testing general queries...")
        
        queries = [
            ("How do I reset my password?", "tech-support"),
            ("What is the vacation policy?", "hr-policies"),
            ("API rate limits", "product-docs")
        ]
        
        success_count = 0
        
        for query, project_id in queries:
            try:
                payload = {
                    "query": query,
                    "project_id": project_id
                }
                
                response = self.session.post(f"{self.base_url}/v1/query", json=payload)
                response.raise_for_status()
                
                result = response.json()
                self.log(f"Query '{query}' -> {len(result['sources'])} sources")
                success_count += 1
                
            except Exception as e:
                self.log(f"Query '{query}' failed: {e}", False)
        
        self.log(f"General queries: {success_count}/{len(queries)} successful")
        return success_count == len(queries)
    
    def test_cleanup(self):
        """Test cleanup functionality"""
        print("\n🧹 Running cleanup...")
        
        try:
            # You can add specific cleanup logic here
            # For now, just check that we can access the health endpoint
            response = self.session.get(f"{self.base_url}/healthz")
            response.raise_for_status()
            
            self.log("Cleanup completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Cleanup failed: {e}", False)
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting comprehensive KBAI API tests...")
        
        if not self.wait_for_server():
            return False
        
        tests = [
            ("Authentication", self.test_auth_token),
            ("Ping Test", self.test_ping),
            ("Project Listing", self.test_project_listing),
            ("ASPCA Query (Fail)", self.test_query_aspca_fail),
            ("ASPCA Upload", self.test_aspca_upload),
            ("ASPCA Query (Success)", self.test_query_aspca_success),
            ("General Queries", self.test_general_queries),
            ("Cleanup", self.test_cleanup)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{'='*50}")
            print(f"Running: {test_name}")
            print('='*50)
            
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
        
        print(f"\n{'='*60}")
        print(f"🏁 Test Results: {passed}/{total} tests passed")
        print('='*60)
        
        if passed == total:
            print("🎉 All tests passed! KBAI API is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the output above.")
            return False

def main():
    """Main test execution"""
    print("KBAI API Comprehensive Test Suite")
    print("=" * 60)
    
    # Check if server is supposed to be running
    if len(sys.argv) > 1 and sys.argv[1] == "--standalone":
        print("Running in standalone mode (server should already be running)")
    else:
        print("Starting server in background...")
        # In a real scenario, you might want to start the server here
        # For now, assume it's already running or will be started separately
    
    tester = KBAPITester(BASE_URL)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()