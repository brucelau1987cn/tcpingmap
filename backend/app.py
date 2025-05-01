import os
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
from flask_cors import CORS
import requests
from statistics import mean
from flask import Flask, jsonify, request
import logging

# 初始化日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)  # 启用跨域请求支持

# 全局变量存储最新结果
latest_results = {}

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_FILE = os.path.join(BASE_DIR, "result.json")

# 远程配置文件 URL
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/TogawaSakiko363/tcpingmap/refs/heads/main/backend/config.json"

# 加载远程配置文件（带重试机制）
def load_remote_config(max_retries=3, retry_delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(REMOTE_CONFIG_URL)
            if response.status_code == 200:
                config = response.json()
                logging.info("Successfully loaded remote config.")
                return config
            else:
                logging.warning(f"Attempt {attempt} failed. Status code: {response.status_code}")
                time.sleep(retry_delay)
        except Exception as e:
            logging.error(f"Attempt {attempt} error: {e}")
            time.sleep(retry_delay)
    logging.error("Failed to load remote config after all retries.")
    return {}

# 保存结果到文件（原子写入，防止文件损坏）
def save_result(data):
    try:
        temp_file = RESULT_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, RESULT_FILE)
        logging.info(f"Successfully saved results to {RESULT_FILE}")
    except Exception as e:
        logging.error(f"Error saving result file: {e}")

# 判断是否为合法的 IP 地址
def is_valid_ip(address):
    try:
        socket.inet_aton(address)  # IPv4
        return True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, address)  # IPv6
            return True
        except socket.error:
            return False

# 解析域名到 IP 地址（仅在输入不是 IP 地址时解析）
def resolve_domain(domain_or_ip):
    if is_valid_ip(domain_or_ip):
        logging.info(f"Resolved {domain_or_ip} (already an IP)")
        return domain_or_ip
    try:
        addr_info = socket.getaddrinfo(domain_or_ip, None)
        for info in addr_info:
            if info[0] == socket.AF_INET:  # 优先 IPv4
                ipv4 = info[4][0]
                logging.info(f"Resolved {domain_or_ip} to {ipv4}")
                return ipv4
        # 若无 IPv4，则使用第一个 IPv6
        ipv6 = addr_info[0][4][0]
        logging.info(f"Resolved {domain_or_ip} to {ipv6}")
        return ipv6
    except Exception as e:
        logging.error(f"Error resolving domain {domain_or_ip}: {e}")
        return None

# 执行 TCP Ping 测试（支持多次测试并计算平均延迟）
def tcp_ping(ip, port, timeout=1, count=3, max_delay=500):
    delays = []
    for _ in range(count):
        try:
            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                connect_start_time = time.time()
                result = sock.connect_ex((ip, port))
                connect_end_time = time.time()

                if result == 0:
                    delay = (connect_end_time - connect_start_time) * 1000  # 毫秒
                    if delay <= max_delay:
                        delays.append(delay)

            time.sleep(1)  # 强制等待 1 秒
        except Exception as e:
            logging.error(f"Error performing TCP ping for {ip}:{port}: {e}")

    average_delay = round(mean(delays), 2) if delays else None
    return {"average_delay": average_delay}

# 解析配置为扁平化结构
def parse_config(config):
    resolved_ips = {}
    for province, cities in config.items():
        for city, operators in cities.items():
            for operator, target in operators.items():
                ip = target.get("ip")
                port = target.get("port")
                if port is None:
                    logging.warning(f"Missing port for {province}-{city}-{operator}")
                    continue
                resolved_ip = resolve_domain(ip)
                if resolved_ip:
                    key = f"{province}-{city}-{operator}"
                    resolved_ips[key] = {"ip": resolved_ip, "port": port}
                else:
                    logging.warning(f"Failed to resolve IP for {province}-{city}-{operator}: {ip}")
    return resolved_ips

# 并发测试所有 IP 地址
def execute_tests(resolved_ips):
    results = {}
    if not resolved_ips:
        logging.warning("No IPs resolved. Skipping test.")
        return results

    max_workers = min(len(resolved_ips), 50)
    logging.info(f"Using {max_workers} workers for concurrent testing.")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(tcp_ping, target["ip"], target["port"]): key
            for key, target in resolved_ips.items()
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
            except Exception as e:
                logging.error(f"Error processing future {key}: {str(e)}")
                result = {"average_delay": None}

            # 解析 IP 地址
            ip = resolved_ips[key]["ip"]
            delay = result["average_delay"]
            delay_str = f"{delay}ms" if delay is not None else "N/A"

            # 格式化日志输出
            logging.info(f"Ping result for {key} (IP: {ip}): {delay_str}")
            results[key] = result

    return results

# 转换为扁平化结构
def process_results(results):
    flat_results = {}
    for key, data in results.items():
        province, city, operator = key.split("-")
        flat_results[f"{province}-{city} ({operator})"] = {
            "average_delay": data["average_delay"]
        }
    return flat_results

# 并发测试所有 IP 地址
def test_all_ips(config):
    resolved_ips = parse_config(config)
    results = execute_tests(resolved_ips)
    flat_results = process_results(results)
    save_result(flat_results)
    return flat_results

# 后台定时任务：每 120 秒执行一次测试
def run_periodic_tests():
    global latest_results
    while True:
        try:
            config = load_remote_config()
            if not config:
                logging.warning("No valid configuration found. Skipping test.")
                time.sleep(120)
                continue
            latest_results = test_all_ips(config)
        except Exception as e:
            logging.error(f"Error during periodic tests: {e}")
        time.sleep(120)  # 每 120 秒执行一次

# 启动后台任务
def start_background_task():
    thread = threading.Thread(target=run_periodic_tests, daemon=True)
    thread.start()

# 路由：首页
@app.route("/")
def index():
    return "API Server is running. Use /get_results to fetch data."

# 路由：获取当前测试结果（带缓存控制）
@app.route("/get_results", methods=["GET"])
def get_results():
    global latest_results
    if not latest_results:
        return jsonify({"error": "No results available yet."}), 404
    response = jsonify(latest_results)
    response.headers['Cache-Control'] = 'public, max-age=60'
    return response

if __name__ == "__main__":
    start_background_task()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)