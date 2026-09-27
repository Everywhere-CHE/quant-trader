# Ubuntu 部署指南

## 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | Ubuntu 22.04 / 24.04 LTS |
| Python | 3.11+（24.04 自带 3.12） |
| Node.js | 20+（构建前端需要） |
| 内存 | 最低 2GB，推荐 4GB |
| 磁盘 | 最低 10GB 可用空间 |

---

## 部署方式

### 方式一：源码部署（推荐）

直接使用 `uvicorn` 运行 Python 源码，无需打包，修改方便。

#### 1. 安装系统依赖

```bash
apt update
apt install -y python3 python3-venv python3-pip nodejs npm
```

#### 2. 上传项目

将项目源码上传到服务器，例如 `/opt/quant-trader/`：

```bash
# 从本地打包上传
cd /项目目录
tar czf quant-trader.tar.gz \
  --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.pytest_cache' --exclude='dist' --exclude='build' \
  --exclude='*.log' --exclude='quant_trader.db*' \
  quant-trader/

# 上传到服务器
scp quant-trader.tar.gz root@你的服务器IP:/root/

# 在服务器上解压
ssh root@你的服务器IP
mkdir -p /opt/quant-trader
cd /opt/quant-trader
tar xzf /root/quant-trader.tar.gz
```

#### 3. 安装 Python 依赖

```bash
cd /opt/quant-trader/backend
python3 -m venv .venv
source .venv/bin/activate

# 使用国内镜像（服务器在国内时）
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
```

#### 4. 构建前端

```bash
cd /opt/quant-trader/frontend

# 使用国内镜像
npm install --registry=https://registry.npmmirror.com
npm run build
```

#### 5. 配置环境变量

编辑 `/opt/quant-trader/.env`：

```bash
# 关键配置
HOST=0.0.0.0              # 允许外部访问
PORT=8000
DEBUG=false               # 生产关闭调试

# 数据库（默认 SQLite，文件在 data/ 目录）
DATABASE_URL=sqlite:///../data/quant_trader.db

# CTP 期货账号（如需要）
CTP_USERID=你的账号
CTP_PASSWORD=你的密码
CTP_BROKERID=9999
CTP_TD_ADDRESS=tcp://182.254.243.31:30001
CTP_MD_ADDRESS=tcp://182.254.243.31:30011

# AI 助手（如需要）
ANTHROPIC_API_KEY=你的key
AI_MODEL=claude-sonnet-4-5
AI_ALLOW_TRADING=false
```

#### 6. 启动服务

```bash
cd /opt/quant-trader/backend
source .venv/bin/activate

# 设置 locale 避免 CTP 库报错
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LANGUAGE=en_US:en

# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 `http://服务器IP:8000`，首次打开显示**登录页**，默认账号 `admin` / `admin`（登录后可在设置页修改密码）。所有 API 请求均需 JWT 认证。

---

### 方式二：打包部署（PyInstaller）

将项目打包为单个 Linux 可执行文件，部署更简单。

#### 1. 安装依赖

```bash
apt update
apt install -y python3 python3-venv python3-pip nodejs npm
```

#### 2. 上传源码并构建

```bash
# 上传源码到服务器（同上）
# 进入项目目录
cd /root/quant-trader

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装 Python 依赖
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r backend/requirements.txt
pip install pyinstaller

# 构建前端
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run build

# 打包
cd ../backend
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LANGUAGE=en_US:en
python3 -m PyInstaller pack.spec
```

#### 3. 部署

```bash
# 创建部署目录
mkdir -p /opt/quant-trader/data

# 复制产物
cp /root/quant-trader/backend/dist/QuantTrader /opt/quant-trader/
cp /root/quant-trader/backend/.env /opt/quant-trader/
cp /root/quant-trader/backend/.env.example /opt/quant-trader/

# 配置 .env 中的 HOST=0.0.0.0（run.py 会读取 HOST/PORT 决定监听地址）
```

---

## nginx 反向代理与端口架构（服务器实际配置）

生产环境通过 nginx 统一入口，后端 8000 不对公网开放（云安全组仅放行下列 nginx 端口）：

| 端口 | 协议 | 作用 | 安全组 |
|---|---|---|---|
| 80 | HTTP | 301 跳转到 443 | 放行 |
| 443 | HTTPS | Web 界面 + API + WebSocket + MCP（默认入口） | 放行 |
| 38443 | HTTPS | **MCP 专用直连端口**（非常用端口，复用 443 证书） | 按需放行 |
| 8000 | HTTP | 后端原始监听（`HOST=0.0.0.0`，仅限内网/本机访问） | **不对外放行** |

nginx 配置（`/etc/nginx/sites-enabled/quant-trader`）要点：

```nginx
server {
    listen 443 ssl;                    # 另有 38443 ssl 的 MCP 专用 server 块
    ssl_certificate     /etc/nginx/ssl/quant-trader.crt;      # 自签名证书
    ssl_certificate_key /etc/nginx/ssl/quant-trader.key;
    location /ws {                      # WebSocket 升级
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
server { listen 80; return 301 https://$host$request_uri; }
```

> 后端鉴权中间件依赖 `X-Forwarded-For` 区分「本机免认证直连」与「远程需 Bearer Token」的请求，代理必须透传该头。MCP 接入详见 [MCP_GUIDE.md](MCP_GUIDE.md)。

#### 4. 启动

```bash
cd /opt/quant-trader
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LANGUAGE=en_US:en
./QuantTrader
```

---

## 一键启停脚本

将以下脚本放在 `/root/` 目录下：

### start-qt.sh

```bash
#!/bin/bash
cd /opt/quant-trader
nohup ./QuantTrader > startup.log 2>&1 &
echo "QuantTrader 已启动 (PID: $!)"
# 等待就绪
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        echo "✅ 启动成功，访问 http://服务器IP:8000"
        exit 0
    fi
    sleep 1
done
echo "⚠️ 启动超时，请检查 startup.log"
```

### stop-qt.sh

```bash
#!/bin/bash
pkill -f QuantTrader && echo "已停止" || echo "未在运行"
```

---

## 端口说明

| 端口 | 方向 | 用途 |
|------|------|------|
| 8000 | 入站（需开放） | 交易界面访问 |
| 22 | 入站（已开放） | SSH 连接 |
| 30001/30011 | 出站 | CTP 期货行情+交易（SimNow） |
| 80/443 | 出站 | 腾讯行情源 |

---

## 数据迁移

将现有 `data/` 目录复制到 `/opt/quant-trader/` 下：

```bash
# 从旧服务器/本机复制
scp -r data/ root@服务器IP:/opt/quant-trader/

# 或替换数据库
cp quant_trader.db /opt/quant-trader/data/
```

---

## 常见问题

### CTP 连接报 "can not open CFlow file"

确保启动时工作目录在部署目录下，且 `data/` 目录存在：

```bash
cd /opt/quant-trader
./QuantTrader
```

### CTP 报 "locale::facet::_S_create_c_locale name not valid"

设置 locale 环境变量：

```bash
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LANGUAGE=en_US:en
```

### 前端页面空白

检查前端构建产物是否存在：

```bash
ls /opt/quant-trader/frontend/dist/index.html
```

如果不存在，重新 `npm run build`。

### 端口被占用

修改 `.env` 中的 `PORT` 配置，或使用 `lsof -i :8000` 查看占用进程。

---

## 附录：systemd 开机自启（可选）

```ini
# /etc/systemd/system/quant-trader.service
[Unit]
Description=Quant Trader
After=network.target

[Service]
Type=simple
ExecStart=/opt/quant-trader/QuantTrader
WorkingDirectory=/opt/quant-trader
Environment="LANG=en_US.UTF-8"
Environment="LC_ALL=en_US.UTF-8"
Environment="LANGUAGE=en_US:en"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now quant-trader
```