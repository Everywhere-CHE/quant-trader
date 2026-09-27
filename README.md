# QuantTrader 量化交易终端

现代化 **期货 + 股票** 量化交易平台，参考 [vn.py](https://github.com/vnpy/vnpy) 事件驱动架构，前后端分离设计。
内置行情网关、CTP 交易、策略引擎、回测、风控、AI 助手与 MCP 接口，开箱即可从模拟盘跑通「行情 → 策略 → 委托 → 复盘」全链路。

> ⚠️ **免责声明**：本项目仅供学习与研究。接入实盘前请务必在 SimNow / 仿真环境充分验证；市场有风险，交易产生的盈亏与后果由使用者自行承担。

## 功能特性

- **行情网关**：A 股实时五档行情（腾讯源，任意代码懒注册）+ CTP 期货（SimNow / 实盘柜台）
- **策略引擎**：事件驱动，继承 `StrategyTemplate` 即可编写策略；内置双均线交叉、唐奇安通道突破、均线突破回调 3 个经典策略
- **向导式创建策略**：选模板 → 填参数 → 自动生成代码 → 保存即校验热加载（无需手写代码）
- **在线代码编辑器**：CodeMirror 语法高亮，保存即 AST 安全校验 + 热加载
- **回测系统**：历史 K 线重放撮合，收益/回撤/夏普/胜率/盈亏比完整统计 + 资金曲线
- **风控引擎**：单笔量限、流控、当日委托数、持仓上限、当日亏损熔断、合约级移动止损
- **AI 助手**：多模型（Claude / DeepSeek / Kimi / 通义 / GLM / GPT 等），行情分析、绩效复盘、策略生成与自动回测
- **MCP 接口**：28 个工具，可接入 Claude Code / Cursor / Windsurf 等 AI 客户端，支持远程接入（详见 [MCP_GUIDE.md](MCP_GUIDE.md)）
- **现代前端**：React 19 + Ant Design v6 + ECharts，极光玻璃态 UI，亮 / 暗双主题

## 架构概览

```
Gateway 线程 (CTP/STOCK) ──put──> EventEngine (queue.Queue + 分发线程)
                                  ├─> OmsEngine  (内存缓存: ticks/orders/trades/positions)
                                  ├─> LogEngine  (logging + 环形缓冲)
                                  ├─> DataEngine (SQLAlchemy 落库)
                                  └─> EventBridge ─> WebSocket 广播
FastAPI REST ──────────────> MainEngine (connect/subscribe/send_order/cancel_order)
前端 React 19 ─────────────> REST + WebSocket (tick/order/trade/position 实时推送)
```

核心 ID 约定（沿 vn.py）：`vt_symbol = {symbol}.{exchange}`（如 `IF2509.CFFEX`）、`vt_orderid = {gateway_name}.{orderid}`。

---

## 快速开始

### 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11 或 Ubuntu 22.04/24.04（其他发行版亦可） |
| Python | 3.11+（建议 3.11 / 3.12） |
| Node.js | 20+（构建前端用；仅使用已构建产物时可跳过） |
| 数据库 | SQLite（默认，零配置；兼容 PostgreSQL） |

### 一键启动（推荐）

**Windows**：

```bat
:: 1. 双击 install.bat   —— 创建 venv、安装 Python 依赖、安装前端依赖并构建
:: 2. 双击 start.bat     —— 启动后端 + 前端开发服务器，并自动打开浏览器
```

**Linux / macOS**：

```bash
./install.sh    # 创建 venv、安装依赖（支持国内镜像加速，见脚本头部说明）
./start.sh      # 启动后端 + 前端，Ctrl+C 一键全停
```

> Linux 服务器单机部署（前端由后端直接托管，只暴露一个端口）：`./start.sh --prod`

### 手动安装

**Windows（PowerShell / CMD）**：

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

cd ..\frontend
npm install
npm run build
cd ..

:: 启动后端（前端生产模式下由后端 8000 端口直接托管）
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Linux（bash）**：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

cd ../frontend
npm install
npm run build
cd ..

# 启动后端
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> 开发模式：另开一个终端在 `frontend/` 下执行 `npm run dev`，访问
> <http://localhost:5173>（已配置 `/api`、`/ws` 代理到 8000）。

启动成功后：

| 地址 | 说明 |
|---|---|
| <http://127.0.0.1:8000> | 交易终端（默认账号 `admin` / `admin`，登录后请在「设置」页修改密码） |
| <http://127.0.0.1:8000/docs> | API 文档（Swagger） |
| <http://127.0.0.1:8000/api/health> | 健康检查 |
| ws://127.0.0.1:8000/ws | WebSocket 实时推送 |

### 连接行情与交易

- **A 股行情**：默认自动连接 STOCK 网关（腾讯源，无需账号）。交易页左侧「自选列表」点 **+**，输入任意 A 股代码（如 `601899.SSE`）即可实时订阅
- **期货（CTP）**：设置页 → 网关管理 → CTP「账号设置」——内置 SimNow / openctp 预设，填入投资者代码与密码后「连接」。SimNow 注册：<https://www.simnow.com.cn>
- 所有合约添加后自动订阅，实时五档盘口 + K 线立即推送

### 配置说明（backend/.env）

| 配置项 | 说明 |
|---|---|
| `HOST` / `PORT` | 后端监听地址，默认 `127.0.0.1:8000`；对外服务改 `HOST=0.0.0.0` |
| `CTP_USERID` / `CTP_PASSWORD` | CTP 账号（推荐直接在设置页配置，持久化到 `data/ctp_config.json`，无需重启） |
| `AI_PROVIDER` / `ANTHROPIC_API_KEY` | AI 助手初始配置（也可在界面「模型设置」中配置） |
| `AI_ALLOW_TRADING` | 是否允许 AI / MCP 直接下单（默认 `false` 仅分析） |

运行时配置（CTP 账号、AI 模型、风控参数、自选列表）均保存在 `data/` 目录，改界面即生效；该目录含密钥与交易数据，**切勿提交到版本库**（已在 .gitignore 中排除）。

---

## MCP 接入（AI 助手客户端）

平台内置 28 个 MCP 工具（行情 / 持仓 / 下单 / 策略管理 / 回测 / 风控），两种接入方式：

**方式一：本机免认证**（AI 客户端与量化系统同机）——项目根的 `.mcp.json` 即是：

```json
{
  "mcpServers": {
    "quant-trader": {
      "command": "backend/.venv/Scripts/python.exe",
      "args": ["backend/mcp_server/server.py"],
      "env": { "QT_API_BASE": "http://127.0.0.1:8000/api", "AI_ALLOW_TRADING": "false" }
    }
  }
}
```

**方式二：远程接入**（AI 客户端在另一台机器）——登录 Web 界面 → 顶栏「MCP 配置」→ 一键导出零依赖单文件客户端脚本（自动预置服务地址与长效 Token）→ 在 Claude Code / Cursor / Windsurf 的 `mcpServers` 中引用即可。

完整说明（服务地址形式、Token 轮换、工具清单、常见问题）见 **[MCP_GUIDE.md](MCP_GUIDE.md)**。

---

## 策略系统

内置策略：**双均线交叉**（SMA 金叉死叉）、**唐奇安通道突破**（N 根最高/最低价反手）、**均线突破回调**（趋势启动回调买入）。策略页底部「策略说明」含每个策略的逻辑与参数详解；更多策略可用向导创建或放入 `backend/strategies/`。

**添加自己的策略（三种方式）**：

1. **向导创建（无需写代码）**：策略页「向导创建策略」→ 选模板（双均线 / RSI / 唐奇安 / 布林带 / 网格）→ 填参数 → 自动生成代码 → 保存热加载
2. **在线编辑器**：策略页「编写策略代码」，继承 `StrategyTemplate` 实现 `on_bar` 即可，保存时服务端 AST 校验（禁止危险导入、语法错误提示行号）
3. **本地文件**：把 `.py` 放进 `backend/strategies/`，重启或调 `POST /api/strategies/reload`

安全边界：策略代码禁止 `os / subprocess / socket` 等危险导入；AI 下单受 `AI_ALLOW_TRADING` + 风控引擎双重约束。

```bash
# 命令行创建并启动一个策略实例
curl -X POST http://127.0.0.1:8000/api/strategies -H "Content-Type: application/json" \
  -d "{\"class_name\":\"MaCrossStrategy\",\"name\":\"ma1\",\"vt_symbol\":\"IF2509.CFFEX\",\"setting\":{\"fast_window\":5,\"slow_window\":20}}"
curl -X POST http://127.0.0.1:8000/api/strategies/ma1/init
curl -X POST http://127.0.0.1:8000/api/strategies/ma1/start
```

## 回测（全离线可跑）

```bash
# 1. 下载历史数据入库
curl -X POST http://127.0.0.1:8000/api/backtest/download-data -H "Content-Type: application/json" \
  -d "{\"vt_symbol\":\"IF2509.CFFEX\",\"interval\":\"1m\",\"start\":\"2026-07-14T09:00:00\",\"end\":\"2026-07-16T15:00:00\",\"gateway_name\":\"CTP\"}"
# 2. 运行回测（统计指标 + 每日资金曲线 + 成交明细）
curl -X POST http://127.0.0.1:8000/api/backtest -H "Content-Type: application/json" \
  -d "{\"class_name\":\"MaCrossStrategy\",\"vt_symbol\":\"IF2509.CFFEX\",\"interval\":\"1m\",\"start\":\"2026-07-14T12:00:00\",\"end\":\"2026-07-16T15:00:00\",\"size\":300,\"pricetick\":0.2,\"rate\":0.0001,\"slippage\":0.2,\"setting\":{\"fast_window\":5,\"slow_window\":20}}"
```

## 风控

所有订单（手动 + 策略 + AI）先过风控引擎：单笔委托量限、每秒流控、当日委托数、活动委托数、单品种持仓上限、当日亏损熔断、合约级移动止损。设置页可视化配置，实时生效。

## 生产部署

- **Ubuntu 服务器**：[DEPLOY_UBUNTU.md](DEPLOY_UBUNTU.md)——源码部署 / PyInstaller 打包 / nginx 反向代理 / 端口与安全组说明 / 常见问题
- **Windows 打包单文件 exe**：[DEPLOY.md](DEPLOY.md)——`npm run build` + `pyinstaller pack.spec`

## 开发与测试

```bash
# 后端测试（默认跳过需要外网的用例）
cd backend
.venv\Scripts\pytest tests\          # Windows
.venv/bin/pytest tests/              # Linux

# 前端开发服务器（热更新）
cd frontend && npm run dev
```

## 目录结构

```
quant-trader/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口 + lifespan
│   │   ├── config.py          # pydantic-settings 配置
│   │   ├── core/              # 量化核心（EventEngine / Gateway / 策略 / 回测 / 风控）
│   │   ├── db/                # SQLAlchemy 模型
│   │   ├── api/               # REST 路由 + WebSocket
│   │   ├── ai/                # AI 助手（多模型 tool-use 循环 + 工具注册表）
│   │   └── auth.py            # JWT 认证 + MCP 长效 Token
│   ├── mcp_server/            # MCP stdio 服务器 + 单文件客户端模板
│   ├── strategies/            # 用户自定义策略目录（放入 .py 即自动发现）
│   ├── pack.spec              # PyInstaller 打包配置
│   └── tests/                 # pytest 测试
├── frontend/                  # React 19 前端
│   └── src/components/        # 交易终端 / 策略 / 回测 / AI / 设置页组件
├── data/                      # 运行时数据（自动生成，不入库）
├── install.bat / install.sh   # 一键安装
├── start.bat / start.sh       # 一键启动
└── MCP_GUIDE.md               # MCP 接入使用文档
```

## License

[MIT](LICENSE)
