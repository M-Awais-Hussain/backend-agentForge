import requests
import json

def test_refactor():
    url = "http://localhost:8000/refactor"
    code = """
def calculate_area(radius):
    import math
    return math.pi * radius * radius

def print_area(radius):
    area = calculate_area(radius)
    print("The area is " + str(area))

print_area(5)
"""
    payload = {
        "code": code,
        "language": "python"
    }
    
    print("Sending request to /refactor...")
    try:
        # Start server in background or just use TestClient style if not running
        from fastapi.testclient import TestClient
        from backend.main import app
        
        client = TestClient(app)
        response = client.post("/refactor", json=payload)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("\n--- Intent ---")
            print(result.get("intent").encode('ascii', 'ignore').decode('ascii'))
            print("\n--- Refactored Code ---")
            print(result.get("refactored_code").encode('ascii', 'ignore').decode('ascii'))
            print("\n--- Diff ---")
            print(result.get("diff").encode('ascii', 'ignore').decode('ascii'))
            print("\n--- Metrics ---")
            print(json.dumps(result.get("metrics"), indent=2))
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_refactor()
