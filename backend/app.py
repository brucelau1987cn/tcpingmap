import os
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
import requests  # 用于从远程 URL 获取配置文件
from statistics import mean
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 启用 CORS，允许跨域请求

# 全局变量存储最新结果
latest_results = {}

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 获取当前脚本所在目录
RESULT_FILE = os.path.join(BASE_DIR, "result.json")

# 远程配置文件 URL
REMOTE_CONFIG_URL = "https://tcpingmap.pages.dev/config.json"

# 加载远程配置文件
def load_remote_config():
    try:
        response = requests.get(REMOTE_CONFIG_URL)
        if response.status_code == 200:
            config = response.json()
            print("Successfully loaded remote config:", config)
            return config
        else:
            print(f"Failed to fetch remote config. Status code: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error loading remote config: {e}")
        return {}

# 保存结果到文件
def save_result(data):
    try:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved results to {RESULT_FILE}")
    except Exception as e:
        print(f"Error saving result file: {e}")

# 判断是否为合法的 IP 地址
def is_valid_ip(address):
    try:
        socket.inet_aton(address)  # 检查 IPv4
        return True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, address)  # 检查 IPv6
            return True
        except socket.error:
            return False

# 解析域名到 IP 地址（仅在输入不是 IP 地址时解析）
def resolve_domain(domain_or_ip):
    if is_valid_ip(domain_or_ip):  # 如果是合法的 IP 地址，直接返回
        print(f"Resolved {domain_or_ip} (already an IP)")
        return domain_or_ip
    try:
        # 使用 getaddrinfo 支持 IPv4 和 IPv6
        addr_info = socket.getaddrinfo(domain_or_ip, None)
        # 优先返回 IPv4 地址，如果没有则返回 IPv6 地址
        for info in addr_info:
            if info[0] == socket.AF_INET:  # IPv4
                ipv4 = info[4][0]
                print(f"Resolved {domain_or_ip} to {ipv4}")
                return ipv4
        # 如果没有 IPv4，则返回第一个 IPv6 地址
        ipv6 = addr_info[0][4][0]
        print(f"Resolved {domain_or_ip} to {ipv6}")
        return ipv6
    except Exception as e:
        print(f"Error resolving domain {domain_or_ip}: {e}")
        return None

# 执行 TCP Ping 测试（支持多次测试并计算平均延迟）
def tcp_ping(ip, port, timeout=1, count=3, max_delay=500):
    delays = []

    for _ in range(count):
        try:
            # 根据 IP 地址类型选择合适的协议族
            if ":" in ip:  # IPv6 地址包含 ":"
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            else:  # 默认为 IPv4
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            sock.settimeout(timeout)
            connect_start_time = time.time()
            result = sock.connect_ex((ip, port))
            connect_end_time = time.time()
            sock.close()

            if result == 0:  # 成功连接
                delay = (connect_end_time - connect_start_time) * 1000  # 转换为毫秒
                if delay <= max_delay:  # 过滤掉异常偏高的延迟
                    delays.append(delay)

            # 强制等待 1 秒，确保每秒只测试一次
            time.sleep(1)

        except Exception as e:
            print(f"Error performing TCP ping for {ip}:{port}: {e}")

    # 计算平均延迟
    average_delay = round(mean(delays), 2) if delays else None

    return {
        "average_delay": average_delay
    }

# 并发测试所有 IP 地址
def test_all_ips(config):
    results = {}
    resolved_ips = {}

    # 遍历嵌套配置，解析域名并存储解析后的 IP 和端口
    for province, cities in config.items():
        for city, operators in cities.items():
            for operator, target in operators.items():
                ip = target.get("ip")
                port = target.get("port")  # 从配置文件中获取端口号
                if port is None:
                    print(f"Missing port for {province}-{city}-{operator}")
                    continue
                resolved_ip = resolve_domain(ip)
                if resolved_ip:
                    key = f"{province}-{city}-{operator}"
                    resolved_ips[key] = {"ip": resolved_ip, "port": port}
                else:
                    print(f"Failed to resolve IP for {province}-{city}-{operator}: {ip}")

    # 动态调整并发线程池大小
    max_workers = min(len(resolved_ips), 50)  # 最大并发数限制为 50
    print(f"Using {max_workers} workers for concurrent testing.")

    # 并发执行 TCP Ping 测试
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(tcp_ping, target["ip"], target["port"]): key
            for key, target in resolved_ips.items()
        }
        for future in as_completed(future_to_key):  # 使用 as_completed 处理并发任务
            key = future_to_key[future]
            result = future.result()
            results[key] = result
            print(f"Ping result for {key}: {result}")

    # 将嵌套结构转换为扁平化结构，方便前端使用
    flat_results = {}
    for key, data in results.items():
        province, city, operator = key.split("-")
        flat_results[f"{province}-{city} ({operator})"] = {
            "average_delay": data["average_delay"]
        }

    # 保存结果到文件
    save_result(flat_results)
    print("Saved results to result.json:", flat_results)

    return flat_results

# 后台定时任务：每 120 秒执行一次测试
def run_periodic_tests():
    global latest_results
    while True:
        try:
            config = load_remote_config()  # 从远程加载配置
            if not config:
                print("No valid configuration found. Skipping test.")
                time.sleep(120)
                continue
            latest_results = test_all_ips(config)
        except Exception as e:
            print(f"Error during periodic tests: {e}")
        time.sleep(120)  # 每 120 秒执行一次

# 启动后台任务
def start_background_task():
    thread = threading.Thread(target=run_periodic_tests, daemon=True)
    thread.start()

# 路由：首页
@app.route("/")
def index():
    return "API Server is running. Use /get_results to fetch data."

# 路由：获取当前测试结果
@app.route("/get_results", methods=["GET"])
def get_results():
    global latest_results
    if not latest_results:
        return jsonify({"error": "No results available yet."}), 404
    return jsonify(latest_results)

if __name__ == "__main__":
    # 启动后台任务
    start_background_task()
    # 启动 Flask 应用
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)