import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
VPNGATE_API_URL = "https://raw.githubusercontent.com/fdciabdul/Vpngate-Scraper-API/refs/heads/main/json/data.json"
IPDATA_API_URL = "https://api.ipdata.co/{ip}"
# IPDATA_API_KEY = os.getenv("IPDATA_API_KEY")  # You should set this in .env file
IPDATA_API_KEY = "eca677b284b3bac29eb72f5e496aa9047f26543605efe99ff2ce35c9"

# Proxy settings
PROXIES = {
    'http': 'socks5h://127.0.0.1:7890',
    'https': 'socks5h://127.0.0.1:7890'
}

# Fields to exclude (these are already in VPNGate data or not needed)
EXCLUDE_FIELDS = {'ip', 'count'}

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

def check_ip_risk(ip, session):
    """Check risk score for a single IP using ipdata.co API"""
    try:
        # Add delay between requests
        time.sleep(2)  # 2 seconds delay between requests
        
        headers = {
            'Referer': 'https://ipdata.co/',
            'Origin': 'https://ipdata.co',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        for attempt in range(3):  # 每个IP最多尝试3次
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
                
                return ip, ip_info
                
            except requests.exceptions.RequestException as e:
                if attempt == 2:  # 最后一次尝试
                    print(f"Failed to check IP {ip} after 3 attempts: {str(e)}")
                    return ip, None
                print(f"Attempt {attempt + 1} failed for IP {ip}: {str(e)}")
                time.sleep(5)  # 失败后等待5秒再重试
                
    except Exception as e:
        print(f"Unexpected error checking IP {ip}: {str(e)}")
        return ip, None

def main():
    # Create session with retry strategy
    session = create_session()
    
    # Fetch VPNGate data
    try:
        response = session.get(VPNGATE_API_URL, timeout=15)
        response.raise_for_status()
        vpn_data = response.json()
        
        if not vpn_data or not isinstance(vpn_data, list) or len(vpn_data) < 1:
            raise ValueError("Invalid VPNGate data format")
            
        servers_data = vpn_data[0].get("servers", [])
        ip_map = {server["ip"]: server for server in servers_data if server.get("ip")}
        
        print(f"Found {len(ip_map)} servers to check")
        
        # Use ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=1) as executor:
            # Submit all requests
            future_to_ip = {
                executor.submit(check_ip_risk, ip, session): ip 
                for ip in ip_map.keys()
            }
            
            # Process completed requests
            for future in as_completed(future_to_ip):
                ip, ip_info = future.result()
                if ip_info and ip in ip_map:
                    # 将所有IP数据存储在ipdata字段中
                    ip_map[ip]["ipdata"] = ip_info
                    # 获取threat数据用于显示
                    threat_data = ip_info.get("threat", {})
                    scores = threat_data.get("scores", {})
                    trust_score = scores.get("trust_score", 0)
                    print(f"Added IP data for {ip} - Trust Score: {trust_score}")
        
        # Save updated data back to a new file
        with open("vpngate_with_risk.json", "w", encoding="utf-8") as f:
            json.dump(vpn_data, f, indent=2, ensure_ascii=False)
            
        print("Successfully updated VPN data with IP information!")
        
    except Exception as e:
        print(f"Error processing VPN data: {str(e)}")

if __name__ == "__main__":
    if not IPDATA_API_KEY:
        print("Error: IPDATA_API_KEY not found in environment variables")
        exit(1)
    main() 
