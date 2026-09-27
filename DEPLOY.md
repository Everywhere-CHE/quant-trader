# 部署指南（Quant Trader）

在任何一台新机器上部署本平台的完整步骤。

## 环境要求

| 软件 | 版本 | 说明 |
|---|---|---|
| Python | 3.11+（推荐 3.12/3.13） | 后端运行时 |
| Node.js | 18+（推荐 20+） | 前端构建/开发服务器 |
| 操作系统 | Windows 10/11、Linux、macOS | CTP 期货接口官方支持 Windows 与主流 Linux；macOS 上 CTP 可能不可用（其余功能不受影响） |

> 无需安装数据库：默认使用 SQLite（`data/quant_trader.db` 自动创建）。
> 后续切 PostgreSQL 只需改 `backend/.env` 的 `DATABASE_URL` 并 `pip install psycopg[binary]`。

## 一、安装（新机器执行一次）

把整个项目目录拷贝/克隆到目标机器后：

**Windows：**
```bat
install.bat
```

**Linux / macOS：**
```bash
chmod +x install.sh start.sh
./install.sh
```

脚本自动完成：检查 Python/Node → 创建 `backend/.venv` → 安装后端依赖（requirements.txt）→ 生成 `backend/.env`（若不存在）→ `npm install` → `npm run build` 前端生产包。

**国内网络加速**（依赖下载慢时）：
```bash
# pip 清华镜像
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# npm 淘宝镜像
cd frontend && npm install --registry=https://registry.npmmirror.com
```

## 二、启动

### 开发模式（本机使用，带热重载）

**Windows：** 双击 `start.bat`（弹出前后端两个窗口并自动打开浏览器）
**Linux / macOS：** `./start.sh`（Ctrl+C 一键全停）

- 前端界面：http://localhost:5173
- 后端 API 文档：http://127.0.0.1:8000/docs

### 生产模式（服务器部署，单端口）

后端已内置托管前端构建包（`frontend/dist` 存在时自动挂载），只需跑一个进程：

```bash
# Linux/macOS
./start.sh --prod
# 或手动（Windows 同理，将路径换成 .venv\Scripts\python.exe）
cd backend && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器直接访问 `http://<服务器IP>:8000`（界面与 API 同端口，无需 Nginx；如需 HTTPS/域名再在前面加反向代理）。

**登录认证**：部署后访问先显示登录页，默认账号 `admin` / `admin`（设置页可修改密码）。所有 API 端点均需登录 Token。

**Linux 后台常驻（systemd 示例）** — `/etc/systemd/system/quant-trader.service`：
```ini
[Unit]
Description=Quant Trader
After=network.target

[Service]
WorkingDirectory=/opt/quant-trader/backend
ExecStart=/opt/quant-trader/backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now quant-trader
```

## 三、部署后配置（均可在网页内完成）

| 配置 | 位置 | 说明 |
|---|---|---|
| CTP 账号（SimNow/实盘） | 设置页 → CTP「账号设置」 | 投资者代码/密码/服务器，含预设；持久化 `data/ctp_config.json` |
| AI 模型与 Key | AI 助手页 →「模型设置」 | Claude/GPT/DeepSeek/中转站等；持久化 `data/ai_config.json` |
| 风控参数 | 设置页 → 风控参数 | 单笔限额/流控/熔断等 |
| 自选合约 | 交易页左侧 + 号 | 持久化 `data/watchlist.json` |
| 初始默认值 | `backend/.env` | 服务器地址、开关等（网页配置优先级更高） |

## 四、升级已有部署（不覆盖目标机数据）

**不要直接整目录覆盖**——那会把目标机的 `data/`（数据库/密码/自选）、`backend/.env`、自写策略全部冲掉。用项目自带的更新脚本：

### 第 1 步：开发机打包（只含代码）

```bat
make_update.bat        :: Windows，生成 quant-trader-update.zip
```
```bash
./make_update.sh       # Linux/macOS，生成 quant-trader-update.tar.gz
```

打包自动排除：`data/`、`backend/.env`、`backend/.venv`、`backend/strategies/`（用户自写策略）、`node_modules/`、`dist/`、数据库/日志/CTP 流水文件。**包里只有代码，绝无密码和数据。**

### 第 2 步：拷到目标机并应用

把更新包拷到目标机的 quant-trader 目录，然后：

```bat
update.bat             :: Windows
```
```bash
./update.sh            # Linux/macOS
```

更新脚本自动完成：
1. 检查服务是否已停止（8000 端口）
2. **备份**目标机的 `data/`、`.env`、`strategies/` 到 `update_backup_<日期>/`（双保险）
3. 解压覆盖代码（包内没有数据文件，所以本机数据天然不会被碰）
4. `pip install -r requirements.txt` 安装新增依赖
5. `npm install && npm run build` 重建前端
6. 删除更新包，提示用 `start.bat` / `./start.sh` 重启

### 数据兼容性

- 数据库结构变更由启动时的轻量迁移自动处理（`init_db` 会补新列），无需手工操作
- 若新版本运行异常，把 `update_backup_<日期>/` 里的内容拷回即可回滚数据；代码回滚则重新应用旧版本更新包

### 两台机器都在开发/修改代码怎么办

更新包方案是"单向分发"（开发机 → 部署机）。若两台设备都会改代码，建议改用 Git：项目根目录 `git init` 后推到私有仓库，`data/`、`.env`、`strategies/` 已被 .gitignore 排除，目标机 `git pull` 天然不碰本机数据，还能双向合并。

## 五、数据迁移（整机搬家）

所有运行数据都在 `data/` 目录：`quant_trader.db`（行情/委托/成交/K线）、`ctp_config.json`、`ai_config.json`、`watchlist.json`、日志。**迁移机器时把 `data/` 一并拷走即可保留全部历史与配置**（其中含密码/Key，注意保管）。

## 六、常见问题

- **openctp-ctp 安装失败（少数 Linux 发行版）**：CTP 网关会自动禁用，其余功能正常；期货实盘建议 Windows 或主流 Linux（Ubuntu 20.04+）
- **端口被占**：改 `backend/.env` 的 `PORT`，前端开发模式同步改 `frontend/vite.config.ts` 的 proxy target
- **验证安装**：`cd backend && .venv/Scripts/python -m pytest tests/ -m "not network"`（约 2~3 分钟，全绿即环境正常）
- **对外开放注意**：平台已内置 JWT 登录认证（默认 `admin/admin`），但建议修改默认密码并限制来源 IP，或置于带认证的反向代理之后（如 nginx + HTTPS，见 DEPLOY_UBUNTU.md）
