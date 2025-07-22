"""
Script para probar la API con Ray
"""
import requests
import json
import time

def test_ray_api():
    base_url = "http://localhost:8000"
    
    print("🚀 Probando API con Ray...")
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    response = requests.get(f"{base_url}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Test 2: Status
    print("\n2. Testing status endpoint...")
    response = requests.get(f"{base_url}/status")
    print(f"Status: {response.status_code}")
    print(f"Ray Status: {json.dumps(response.json(), indent=2)}")
    
    # Test 3: Portfolio analysis
    print("\n3. Testing portfolio analysis with Ray...")
    portfolio_request = {
        "sentiment_url": "https://raw.githubusercontent.com/SalomeAc/Infraestructuras-proyecto/refs/heads/main/sentiment_data.csv",
        "start_date": "2021-01-01",
        "end_date": "2023-03-01",
        "top_n_stocks": 5,
        "benchmark_ticker": "QQQ"
    }
    
    start_time = time.time()
    response = requests.post(f"{base_url}/portfolio/analyze", json=portfolio_request)
    end_time = time.time()
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Processing time: {result.get('processing_time_seconds', 'N/A')} seconds")
        print(f"Total time: {end_time - start_time:.2f} seconds")
        print(f"Portfolio return: {result['analysis']['total_portfolio_return']:.4f}")
        print(f"Benchmark return: {result['analysis']['total_benchmark_return']:.4f}")
        print(f"Excess return: {result['analysis']['excess_return']:.4f}")
        print(f"Stocks analyzed: {result['analysis']['unique_stocks_analyzed']}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_ray_api()
