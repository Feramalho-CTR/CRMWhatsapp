import requests
import sys
import json
from datetime import datetime

class WhatsAppCRMTester:
    def __init__(self, base_url="https://web-interface-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.agent_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            
            if success:
                print(f"✅ Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                error_detail = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_response = response.json()
                    error_detail += f" - {error_response.get('detail', '')}"
                except:
                    error_detail += f" - {response.text[:100]}"
                
                print(f"❌ {error_detail}")
                self.log_test(name, False, error_detail)
                return False, {}

        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.log_test(name, False, error_msg)
            return False, {}

    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": "admin", "password": "admin123"}
        )
        if success and 'access_token' in response:
            self.admin_token = response['access_token']
            self.log_test("Admin Login", True, f"User role: {response.get('user', {}).get('role', 'unknown')}")
            return True
        else:
            self.log_test("Admin Login", False, "No access token received")
            return False

    def test_agent_login(self):
        """Test agent login"""
        success, response = self.run_test(
            "Agent Login",
            "POST",
            "auth/login",
            200,
            data={"username": "agent1", "password": "agent123"}
        )
        if success and 'access_token' in response:
            self.agent_token = response['access_token']
            self.log_test("Agent Login", True, f"User role: {response.get('user', {}).get('role', 'unknown')}")
            return True
        else:
            self.log_test("Agent Login", False, "No access token received")
            return False

    def test_invalid_login(self):
        """Test invalid login credentials"""
        success, response = self.run_test(
            "Invalid Login",
            "POST",
            "auth/login",
            401,
            data={"username": "invalid", "password": "invalid"}
        )
        self.log_test("Invalid Login", success, "Correctly rejected invalid credentials")
        return success

    def test_auth_me(self):
        """Test /auth/me endpoint"""
        if not self.admin_token:
            self.log_test("Auth Me", False, "No admin token available")
            return False
            
        success, response = self.run_test(
            "Auth Me",
            "GET",
            "auth/me",
            200,
            token=self.admin_token
        )
        if success:
            self.log_test("Auth Me", True, f"Username: {response.get('username', 'unknown')}")
        return success

    def test_conversations_endpoint(self):
        """Test conversations endpoint"""
        if not self.admin_token:
            self.log_test("Get Conversations", False, "No admin token available")
            return False
            
        success, response = self.run_test(
            "Get Conversations",
            "GET",
            "conversations",
            200,
            token=self.admin_token
        )
        if success:
            conversations_count = len(response) if isinstance(response, list) else 0
            self.log_test("Get Conversations", True, f"Found {conversations_count} conversations")
        return success

    def test_clients_endpoint(self):
        """Test clients endpoint"""
        if not self.admin_token:
            self.log_test("Get Clients", False, "No admin token available")
            return False
            
        success, response = self.run_test(
            "Get Clients",
            "GET",
            "clients",
            200,
            token=self.admin_token
        )
        if success:
            clients_count = len(response) if isinstance(response, list) else 0
            self.log_test("Get Clients", True, f"Found {clients_count} clients")
        return success

    def test_whatsapp_send_mock(self):
        """Test WhatsApp send mock endpoint"""
        if not self.admin_token:
            self.log_test("WhatsApp Send Mock", False, "No admin token available")
            return False
            
        # First get a client to send message to
        success, clients = self.run_test(
            "Get Clients for WhatsApp Test",
            "GET",
            "clients",
            200,
            token=self.admin_token
        )
        
        if not success or not clients:
            self.log_test("WhatsApp Send Mock", False, "No clients available for testing")
            return False
            
        client_id = clients[0]['id']
        
        success, response = self.run_test(
            "WhatsApp Send Mock",
            "POST",
            "whatsapp/send",
            200,
            data={
                "client_id": client_id,
                "sender_type": "agent",
                "sender_id": "test-agent",
                "content": "Test message from API test"
            },
            token=self.admin_token
        )
        if success:
            self.log_test("WhatsApp Send Mock", True, f"Message sent successfully: {response.get('message_id', 'unknown')}")
        return success

    def test_unauthorized_access(self):
        """Test unauthorized access"""
        success, response = self.run_test(
            "Unauthorized Access",
            "GET",
            "conversations",
            401
        )
        self.log_test("Unauthorized Access", success, "Correctly rejected unauthorized request")
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting WhatsApp CRM Backend API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)

        # Authentication tests
        print("\n📋 Authentication Tests")
        self.test_admin_login()
        self.test_agent_login()
        self.test_invalid_login()
        self.test_unauthorized_access()
        
        if self.admin_token:
            print("\n📋 Authenticated Endpoint Tests")
            self.test_auth_me()
            self.test_conversations_endpoint()
            self.test_clients_endpoint()
            self.test_whatsapp_send_mock()
        else:
            print("\n❌ Skipping authenticated tests - no valid token")

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed. Check details above.")
            return 1

def main():
    tester = WhatsAppCRMTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())