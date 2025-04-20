#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import random
import tempfile
from datetime import datetime
from typing import Dict, Optional, Tuple

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from tqdm import tqdm # type: ignore

# --- 加载环境变量 ---
load_dotenv()

# --- 配置区（可通过 .env 覆盖） ---
VPNGATE_API_URL = os.getenv(
    "VPNGATE_API_URL",
    "https://raw.githubusercontent.com/6Kmfi6HP/Vpngate-Scraper-API/refs/heads/main/json/data.json"
)
IPDATA_API_URL_TEMPLATE = os.getenv("IPDATA_API_URL_TEMPLATE", "https://api.ipdata.co/{ip}")
IPDATA_API_KEY = "eca677b284b3bac29eb72f5e496aa9047f26543605efe99ff2ce35c9"
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))
RETRY_TOTAL = int(os.getenv("RETRY_TOTAL", "5"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "1"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "vpngate_with_risk.json")

# 如果没有设置 API_KEY，立即退出
if not IPDATA_API_KEY:
    raise RuntimeError("请在 .env 文件中设置 IPDATA_API_KEY 环境变量")

# 排除字段
EXCLUDE_FIELDS = {"ip", "count"}

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- 用户代理列表 ---
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

# 如果需要代理，请在 .env 配置 PROXIES_JSON，例如:
# PROXIES_JSON='{"http":"socks5h://127.0.0.1:7890","https":"socks5h://127.0.0.1:7890"}'
PROXIES = json.loads(os.getenv("PROXIES_JSON", "{}"))

def create_session() -> requests.Session:
    """创建带重试策略和可选代理的 Session"""
    session = requests.Session()
    retry = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if PROXIES:
        session.proxies.update(PROXIES)
    return session

def check_ip_risk(ip: str, session: requests.Session) -> Tuple[str, Optional[Dict], float]:
    """
    调用 ipdata.co 接口获取单个 IP 的风险数据。
    返回 (ip, 过滤后的数据 or None, 耗时秒数)
    """
    start = time.time()
    headers = {
        "Referer": "https://ipdata.co/",
        "Origin": "https://ipdata.co",
        "User-Agent": random.choice(USER_AGENTS)
    }
    try:
        resp = session.get(
            IPDATA_API_URL_TEMPLATE.format(ip=ip),
            params={"api-key": IPDATA_API_KEY},
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        filtered = {k: v for k, v in data.items() if k not in EXCLUDE_FIELDS}
        return ip, filtered, time.time() - start
    except Exception as e:
        logger.warning(f"IP {ip} 请求失败: {e}")
        return ip, None, time.time() - start

def fetch_vpngate_data() -> Dict:
    """从 VPNGate 仓库拉取 JSON 并校验格式"""
    logger.info("Fetching VPNGate data...")
    session = create_session()
    try:
        resp = session.get(VPNGATE_API_URL, timeout=REQUEST_TIMEOUT * 1.5)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "data" not in data or "servers" not in data["data"]:
            raise ValueError("VPNGate 返回的数据格式不符合预期")
        return data
    finally:
        session.close()

def save_atomic(data: Dict, path: str) -> None:
    """原子性地将 data 写入 path"""
    dirpath = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=dirpath, encoding="utf-8") as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)
    logger.info(f"Output saved to {path}")

def main():
    start_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Script started at {start_dt}")

    try:
        vpn_data = fetch_vpngate_data()
        servers = vpn_data["data"]["servers"]
        ips = [srv["ip"] for srv in servers if srv.get("ip")]
        logger.info(f"Found {len(ips)} IPs; using {MAX_WORKERS} workers")

        session = create_session()
        stats = {"success": 0, "failed": 0, "times": []}

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(check_ip_risk, ip, session): ip for ip in ips}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Checking IP"):
                ip, info, elapsed = future.result()
                stats["times"].append(elapsed)
                if info:
                    stats["success"] += 1
                    # 将结果写回原数据结构
                    for srv in servers:
                        if srv.get("ip") == ip:
                            srv["ipdata"] = info
                            break
                else:
                    stats["failed"] += 1

        session.close()

        # 汇总日志
        total = len(ips)
        total_time = sum(stats["times"]) if stats["times"] else 0
        avg_time = total_time / total if total else 0
        logger.info(f"Total requests: {total}, Success: {stats['success']}, Failed: {stats['failed']}")
        logger.info(f"Avg time: {avg_time:.2f}s, Min: {min(stats['times']):.2f}s, Max: {max(stats['times']):.2f}s")

        save_atomic(vpn_data, OUTPUT_FILE)

    except KeyboardInterrupt:
        logger.error("用户中断执行，已停止")
    except Exception as e:
        logger.exception(f"脚本运行出错: {e}")

if __name__ == "__main__":
    main()