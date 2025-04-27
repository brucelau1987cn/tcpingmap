import concurrent
from flask import Flask, request, jsonify, render_template
import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
import time
import threading

app = Flask(__name__)

# 全局变量存储最新结果
latest_results = {}

# 配置文件路径
CONFIG_FILE = "config.json"
RESULT_FILE = "result.json"

# 加载配置文件
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# 保存结果到文件
def save_result(data):
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
        ipv4 = socket.gethostbyname(domain_or_ip)
        print(f"Resolved {domain_or_ip} to {ipv4}")
        return ipv4
    except Exception as e:
        print(f"Error resolving domain {domain_or_ip}: {e}")
        return None

# 执行 TCP Ping 测试
def tcp_ping(ip, port, timeout=2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start_time = time.time()
        result = sock.connect_ex((ip, port))
        end_time = time.time()
        sock.close()
        if result == 0:  # 成功连接
            delay = (end_time - start_time) * 1000  # 转换为毫秒
            return round(delay, 2)
        print(f"TCP Ping failed for {ip}:{port}")
        return None
    except Exception as e:
        print(f"Error performing TCP ping for {ip}:{port}: {e}")
        return None

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

    # 并发执行 TCP Ping 测试
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_key = {
            executor.submit(tcp_ping, target["ip"], target["port"]): key
            for key, target in resolved_ips.items()
        }
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            delay = future.result()
            results[key] = delay
            print(f"Ping result for {key}: {delay}")

    # 将嵌套结构转换为扁平化结构，方便前端使用
    flat_results = {}
    for key, delay in results.items():
        province, city, operator = key.split("-")
        flat_results[f"{province}-{city} ({operator})"] = delay

    # 保存结果到文件
    save_result(flat_results)
    print("Saved results to result.json:", flat_results)

    return flat_results

# 后台定时任务：每 30 秒执行一次测试
def run_periodic_tests():
    global latest_results
    while True:
        config = load_config()
        latest_results = test_all_ips(config)
        time.sleep(30)  # 每 30 秒执行一次

# 启动后台任务
def start_background_task():
    thread = threading.Thread(target=run_periodic_tests, daemon=True)
    thread.start()

# 路由：首页
@app.route("/")
def index():
    return render_template("index.html")

# 路由：控制面板页面
@app.route("/control")
def control():
    config = load_config()
    return render_template("control.html", config=json.dumps(config, ensure_ascii=False, indent=4))

# 路由：获取当前测试结果
@app.route("/get_results", methods=["GET"])
def get_results():
    global latest_results
    return jsonify(latest_results)

# 路由：更新测试 IP 地址
@app.route("/update_ips", methods=["POST"])
def update_ips():
    new_config = request.json
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, ensure_ascii=False, indent=4)
    return jsonify({"status": "success"})

# 新增：获取当前配置文件内容
@app.route("/get_config", methods=["GET"])
def get_config():
    config = load_config()
    return jsonify(config)

if __name__ == "__main__":
    # 启动后台任务
    start_background_task()
    # 启动 Flask 应用
    app.run(debug=True)