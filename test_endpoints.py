import requests

def test_create_session(base_url):
    """Test the /session endpoint."""
    url = f"{base_url}/session"
    response = requests.post(url, json={})
    if response.status_code == 200:
        print("/session endpoint test passed.")
        print("Response:", response.json())
        return response.json().get("session_id")
    else:
        print("/session endpoint test failed.")
        print("Status Code:", response.status_code)
        print("Response:", response.text)
        return None

def test_query_endpoint(base_url, session_id):
    """Test the /query endpoint."""
    url = f"{base_url}/query"
    payload = {
        "session_id": session_id,
        "query": "What are your store hours?"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("/query endpoint test passed.")
        print("Response:", response.json())
    else:
        print("/query endpoint test failed.")
        print("Status Code:", response.status_code)
        print("Response:", response.text)

def main():
    base_url = "http://127.0.0.1:8000"
    print("Testing /session endpoint...")
    session_id = test_create_session(base_url)

    if session_id:
        print("\nTesting /query endpoint...")
        test_query_endpoint(base_url, session_id)

if __name__ == "__main__":
    main()
