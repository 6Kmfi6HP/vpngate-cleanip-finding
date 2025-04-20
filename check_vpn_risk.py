import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import threading
from datetime import datetime
import random

# Load environment variables
load_dotenv()

# Constants
VPNGATE_API_URL = "https://raw.githubusercontent.com/6Kmfi6HP/Vpngate-Scraper-API/refs/heads/main/json/data.json"
IPDATA_API_URL = "https://api.ipdata.co/{ip}"
# IPDATA_API_KEY = os.getenv("IPDATA_API_KEY")  # You should set this in .env file
IPDATA_API_KEY = "eca677b284b3bac29eb72f5e496aa9047f26543605efe99ff2ce35c9"

# User Agent List
USER_AGENTS = [
    # Windows Chrome
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    
    # Windows Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    
    # Windows Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    
    # macOS Chrome
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    
    # macOS Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    
    # macOS Firefox
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
    
    # Linux Chrome
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    
    # Linux Firefox
    'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
    
    # Mobile Chrome (Android)
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; Samsung S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
    
    # Mobile Safari (iOS)
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
]

# Proxy settings
PROXIES = {
    'http': 'socks5h://127.0.0.1:7890',
    'https': 'socks5h://127.0.0.1:7890'
}

# Fields to exclude (these are already in VPNGate data or not needed)
EXCLUDE_FIELDS = {'ip', 'count'}

# Add rate limiting semaphore
MAX_CONCURRENT_REQUESTS = 10
request_semaphore = threading.Semaphore(MAX_CONCURRENT_REQUESTS)

# Create session with retry strategy
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # 最多重试5次
        backoff_factor=1,  # 重试间隔时间
        status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
        allowed_methods=["HEAD", "GET", "OPTIONS"]  # 允许重试的请求方法
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = PROXIES
    return session

def check_ip_risk(ip):
    """Check risk score for a single IP using ipdata.co API"""
    start_time = time.time()
    # Use semaphore to limit concurrent requests
    with request_semaphore:
        try:
            headers = {
                'Referer': 'https://ipdata.co/',
                'Origin': 'https://ipdata.co',
                'User-Agent': random.choice(USER_AGENTS)  # 随机选择一个User-Agent
            }
            
            for attempt in range(3):  # 每个IP最多尝试3次
                try:
                    # 为每次请求创建新的 session
                    session = create_session()
                    try:
                        response = session.get(
                            IPDATA_API_URL.format(ip=ip),
                            params={"api-key": IPDATA_API_KEY},
                            headers=headers,
                            timeout=10
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        # 创建新的数据结构，排除不需要的字段
                        ip_info = {k: v for k, v in data.items() if k not in EXCLUDE_FIELDS}
                        
                        elapsed_time = time.time() - start_time
                        return ip, ip_info, elapsed_time
                        
                    finally:
                        # 确保 session 被关闭
                        session.close()
                        
                except requests.exceptions.RequestException as e:
                    if attempt == 2:  # 最后一次尝试
                        print(f"Failed to check IP {ip} after 3 attempts: {str(e)}")
                        elapsed_time = time.time() - start_time
                        return ip, None, elapsed_time
                    print(f"Attempt {attempt + 1} failed for IP {ip}: {str(e)}")
                    time.sleep(5)  # 失败后等待5秒再重试
                    
        except Exception as e:
            print(f"Unexpected error checking IP {ip}: {str(e)}")
            elapsed_time = time.time() - start_time
            return ip, None, elapsed_time

def main():
    start_time = time.time()
    start_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Started at: {start_datetime}")
    
    # Fetch VPNGate data
    try:
        # 创建临时 session 只用于获取 VPNGate 数据
        session = create_session()
        try:
            response = session.get(VPNGATE_API_URL, timeout=15)
            response.raise_for_status()
            vpn_data = response.json()
        finally:
            session.close()
        
        if not vpn_data or not isinstance(vpn_data, dict) or 'data' not in vpn_data:
            raise ValueError("Invalid VPNGate data format")
            
        servers_data = vpn_data['data'].get("servers", [])
        ip_map = {server["ip"]: server for server in servers_data if server.get("ip")}
        
        print(f"Found {len(ip_map)} servers to check")
        print(f"Using {MAX_CONCURRENT_REQUESTS} concurrent requests")
        
        # Statistics variables
        total_success = 0
        total_failed = 0
        min_time = float('inf')
        max_time = 0
        total_time = 0
        
        # Use ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            # Submit all requests
            future_to_ip = {
                executor.submit(check_ip_risk, ip): ip 
                for ip in ip_map.keys()
            }
            
            completed = 0
            total = len(future_to_ip)
            
            # Process completed requests
            for future in as_completed(future_to_ip):
                ip, ip_info, request_time = future.result()
                completed += 1
                
                # Update statistics
                min_time = min(min_time, request_time)
                max_time = max(max_time, request_time)
                total_time += request_time
                
                if ip_info and ip in ip_map:
                    total_success += 1
                    # 将所有IP数据存储在ipdata字段中
                    ip_map[ip]["ipdata"] = ip_info
                    # 获取threat数据用于显示
                    threat_data = ip_info.get("threat", {})
                    scores = threat_data.get("scores", {})
                    trust_score = scores.get("trust_score", 0)
                    print(f"[{completed}/{total}] Added IP data for {ip} - Trust Score: {trust_score} (took {request_time:.2f}s)")
                else:
                    total_failed += 1
                    print(f"[{completed}/{total}] Failed to get data for {ip} (took {request_time:.2f}s)")
        
        # Save updated data back to a new file
        with open("vpngate_with_risk.json", "w", encoding="utf-8") as f:
            json.dump(vpn_data, f, indent=2, ensure_ascii=False)
        
        # Calculate and display final statistics
        end_time = time.time()
        total_elapsed = end_time - start_time
        avg_time = total_time / total if total > 0 else 0
        
        print("\n=== Final Statistics ===")
        print(f"Total time: {total_elapsed:.2f} seconds")
        print(f"Successful requests: {total_success}")
        print(f"Failed requests: {total_failed}")
        print(f"Average request time: {avg_time:.2f} seconds")
        print(f"Fastest request: {min_time:.2f} seconds")
        print(f"Slowest request: {max_time:.2f} seconds")
        print(f"Requests per second: {total / total_elapsed:.2f}")
        print("=====================")
            
    except Exception as e:
        print(f"Error processing VPN data: {str(e)}")

if __name__ == "__main__":
    if not IPDATA_API_KEY:
        print("Error: IPDATA_API_KEY not found in environment variables")
        exit(1)
    main() 
