# tcpingmap

🎉 **船新的屎山代码已经上线！** 🎉

你想要的功能他都没有（逃

## 快速开始

1. 确保已安装 **Python 3** 和 **pip**
2. 安装依赖:
   
   ```bash
   pip install -r https://raw.githubusercontent.com/TogawaSakiko363/tcpingmap/refs/heads/main/backend/requirements.txt
   ```
3. 启动！
   ```bash
   python3 -c "import requests,subprocess; r=requests.get('https://raw.githubusercontent.com/TogawaSakiko363/tcpingmap/refs/heads/main/backend/app.py'); open('app.py','wb').write(r.content); subprocess.run(['python3','app.py'])"
   ```

4. 将 `frontend` 文件夹中 `main.js` 的服务器数据源改成你的服务器传输地址，并部署到类似Cloudflare Pages的容器中

后端默认传输端口为 **5000**

```bash
      const servers = [
        { name: "Your Potato Server A", ip: "http://potato-a.server.au:5000" },
        { name: "Your Potato Server B", ip: "http://potato-b.server.au:5000" }
      ];
```

## 实战演示
演示网站：https://tcpingmap.pages.dev/

镜像网站：https://tcpingmap.pp.ua/

## 配置文件

定时远程拉取获取最新配置文件

   ```bash
# 远程配置文件 URL
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/TogawaSakiko363/tcpingmap/refs/heads/main/backend/config.json"
```
**拼接示例**

结构为省份/直辖市-城市-运营商

```bash
{
"上海": {
        "上海": {
            "电信": {
                "ip": "sh-ct-v4.ip.zstaticcdn.com",
                "port": 80
            },
            "联通": {
                "ip": "sh-cu-v4.ip.zstaticcdn.com",
                "port": 80
            },
            "移动": {
                "ip": "sh-cm-v4.ip.zstaticcdn.com",
                "port": 80
            }
        }
    }
}
```

单省份多城市拼接示例

```bash
{
"广东": {
    "广州": {
        "电信": {
            "ip": "www.gd.gov.cn",
            "port": 80
        },
        "联通": {
            "ip": "gd-cu-v4.ip.zstaticcdn.com",
            "port": 80
        },
        "移动": {
            "ip": "gd-cm-v4.ip.zstaticcdn.com",
            "port": 80
        }
    },
    "深圳": {
        "电信": {
            "ip": "www.sz.gov.cn",
            "port": 80
        }
    },
    "东莞": {
        "电信": {
            "ip": "cn-gddg-ct-01-04.bilivideo.com",
            "port": 443
        },
        "联通": {
            "ip": "cn-gddg-cu-01-02.bilivideo.com",
            "port": 443
        },
        "移动": {
            "ip": "cn-gddg-cm-01-04.bilivideo.com",
            "port": 443
        }
    },
    "清远": {
        "电信": {
            "ip": "www.gdqy.gov.cn",
            "port": 80
        }
    }
  }
}
```

## 服务端接口

`http://your-server.au:5000/get_results`

文件内容示例
```bash
{
  "台湾-台东 (是方电讯)": {
    "average_delay": 25.19
  },
  "台湾-台北 (台湾大哥大)": {
    "average_delay": 19.68
  },
  "台湾-桃园 (中华电信)": {
    "average_delay": 22.81
  },
  "吉林-长春 (电信)": {
    "average_delay": 62.32
  },
  "吉林-长春 (移动)": {
    "average_delay": 68.84
  },
  "吉林-长春 (联通)": {
    "average_delay": 57.55
  }
}
```
