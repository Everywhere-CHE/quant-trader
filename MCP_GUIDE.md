# MCP 接入使用文档

把量化交易平台以 **MCP（Model Context Protocol）工具**的形式接入 AI 助手客户端（Claude Code、Cursor、Windsurf、Cline、CC-Switch、Antigravity 等），让 AI 直接查询行情/持仓、管理策略、执行回测乃至下单交易。

平台共暴露 **28 个工具**，客户端脚本是**单文件零依赖**（纯 Python 标准库），下载即用。

---

## 一、接入方式一：导出专属客户端脚本（推荐）

适用于绝大多数场景：AI 客户端在你的电脑上，通过公网或局域网连接部署在服务器上的量化系统。

### 步骤

1. 登录量化系统 Web 界面，点击顶栏右上角 **「MCP 配置」**
2. （可选）修改 **服务地址** —— 默认为当前访问地址，可按需改成直连端口或本机地址（见下表）
3. 点击 **「下载 quant_trader_mcp.py」** —— 脚本已预置服务地址与 MCP Token
4. 把脚本放到固定位置（默认约定 `~/Downloads/quant_trader_mcp.py`）
5. 在 AI 客户端的 `mcpServers` 节点添加配置（见下方示例）

**Claude Code 命令行方式**：

```bash
claude mcp add quant-trader -- python3 ~/Downloads/quant_trader_mcp.py
```

**通用 JSON 配置**（Cursor / Windsurf / Cline / CC-Switch 等客户端的 `mcpServers` 节点）：

```json
{
  "mcpServers": {
    "quant-trader": {
      "command": "python3",
      "args": [
        "~/Downloads/quant_trader_mcp.py"
      ]
    }
  }
}
```

> Windows 环境请把 `python3` 改为 `python`，`args` 用脚本的实际绝对路径。

### 服务地址怎么填

| 场景 | 服务地址 | 说明 |
|---|---|---|
| 公网访问（默认） | `https://服务器IP` | 走 nginx 443，安全组无需额外放行 |
| MCP 专用直连 | `https://服务器IP:38443` | nginx 专用端口（TLS），需云安全组放行 TCP 38443 |
| 服务器本机 | `http://127.0.0.1:8000` | AI 客户端跑在量化系统所在机器上 |

> - 尽量避免使用 8000 等常用端口对外；8000 仅作为后端内部监听端口（nginx 代理目标 / 本机直连）。
> - 服务器 443/38443 使用自签名证书，客户端脚本已内置跳过证书校验，开箱即用。

### 凭据优先级

脚本读取凭据的顺序：**环境变量 > 脚本内置预置值**。可随时用环境变量临时切换目标：

```bash
QT_HOST="https://your-server.com:38443" \
QT_TOKEN="你的MCP Token" \
python3 quant_trader_mcp.py
```

---

## 二、接入方式二：服务器本机免认证模式

AI 客户端与量化系统在同一台机器上时（127.0.0.1 直连免认证），可用项目内置的完整 MCP 服务器，无需 Token：

```json
{
  "mcpServers": {
    "quant-trader": {
      "command": "backend/.venv/Scripts/python.exe",
      "args": ["backend/mcp_server/server.py"],
      "env": {
        "QT_API_BASE": "http://127.0.0.1:8000/api",
        "AI_ALLOW_TRADING": "false"
      }
    }
  }
}
```

项目根的 `.mcp.json` 即此模式（Claude Code 自动识别）。该方式依赖后端 venv 与 `app` 包，**不适合跨机器远程接入**——远程请用方式一。

---

## 三、MCP Token 管理

远程接入使用**长效 MCP Token**（区别于 Web 登录的 24 小时 JWT），存储于 `data/auth_config.json`：

| 操作 | 接口 | 说明 |
|---|---|---|
| 查询（自动生成） | `GET /api/auth/mcp-token` | 首次访问自动生成 48 位 hex，需 JWT 登录态 |
| 轮换 | `POST /api/auth/mcp-token/refresh` | 旧 Token 立即失效，需 JWT 登录态 |

- Web 界面：MCP 配置弹窗 → **「刷新 Token」**按钮一键轮换
- **凭据安全**：导出的脚本包含高权限 API Token，请妥善保管勿公开提交；怀疑泄露立即「刷新 Token」并重新下载脚本
- 轮换后所有已导出的旧脚本立即失效（表现为 401），需重新下载

---

## 四、工具清单（28 个）

| 分类 | 工具 | 功能 |
|---|---|---|
| 行情 | `get_market_overview` / `get_tick` / `get_bars` / `get_intraday_bars` | 市场总览、单合约快照、历史/分钟 K 线 |
| 账户 | `get_positions` / `get_accounts` / `get_orders` / `get_trades` / `get_performance` | 持仓、资金、委托、成交、绩效统计 |
| 交易 | `place_order` / `cancel_order` | 下单、撤单（受交易权限开关约束） |
| 策略 | `list_strategies` / `list_strategy_classes` / `create_strategy` / `control_strategy` / `edit_strategy` | 策略实例增删改查、启停控制、参数修改 |
| 策略代码 | `list_strategy_files` / `read_strategy_file` / `write_strategy_file` / `reload_strategies` | 用户策略文件读写（AST 校验）与热加载 |
| 持仓对账 | `reconcile_positions` / `sync_strategy_pos` | 与网关对账、手动同步策略持仓 |
| 回测 | `run_backtest` / `download_backtest_data` | 运行回测任务、下载历史数据 |
| 风控/系统 | `get_risk_settings` / `update_risk_settings` / `get_gateways` / `get_logs` | 风控参数、网关状态、日志查询 |

**交易权限**：`place_order` / `cancel_order` 受平台「AI 助手」页的下单权限开关（`AI_ALLOW_TRADING`）约束，默认关闭（仅分析建议）；其余只读与管理工具不受影响。所有订单仍需经过 RiskEngine 风控。

---

## 五、客户端脚本实现说明

`backend/mcp_server/standalone_client.py`（导出脚本的模板），单文件、纯标准库（`sys/json/os/ssl/urllib`），无任何 pip 依赖：

- **协议**：JSON-RPC 2.0 over stdio，支持 NDJSON（按行）与 LSP `Content-Length` 双帧，兼容主流 AI 客户端
- **动态工具集**：`tools/list` 实时拉取 `GET {host}/api/mcp/tools`，与服务端注册表自动同步，脚本无需随工具升级
- **调用转发**：`tools/call` → `POST {host}/api/mcp/call`，服务端复用 AI 助手的执行引擎
- **快速超时**：8 秒，避免 Agent 终端长时间挂起；鉴权失败返回明确的 `auth_error` 语义
- **精简输出**：紧凑 JSON 序列化，最大化节省 Token 消耗

后端桥接端点：

| 端点 | 认证 | 说明 |
|---|---|---|
| `GET /api/mcp/tools` | JWT 或 MCP Token | MCP `tools/list` 数据源 |
| `POST /api/mcp/call` | JWT 或 MCP Token | 执行一次工具调用 |
| `GET /api/mcp/script?base=地址` | 仅 JWT | 下载预置专属脚本，`base` 为可选服务地址（严格白名单校验） |

> 本机直连 `127.0.0.1` 的请求免认证（与平台现有安全模型一致）；经 nginx 代理的远程请求必须携带 Bearer Token。

---

## 六、常见问题

| 现象 | 原因与处理 |
|---|---|
| `tools/list` 返回 401 | Token 已被轮换——Web 弹窗重新下载脚本，或更新 `QT_TOKEN` 环境变量 |
| 连接超时 | 检查服务地址与端口；公网直连端口（38443）需云安全组放行；8000 未对公网开放 |
| 证书错误 | 脚本已内置跳过自签名证书校验；若自行改写脚本请保留 `ssl.CERT_NONE` 上下文 |
| 工具缺失/与文档不符 | 服务端版本较旧——升级后端后脚本会自动同步最新工具清单 |
| AI 无法下单 | 平台「AI 助手」页下单权限未开启（`AI_ALLOW_TRADING`），开启后仍受风控约束 |
| 策略写入被拒 | AST 校验：禁止 os/subprocess 等危险导入、必须继承 `StrategyTemplate`、文件名须匹配 `^[A-Za-z][A-Za-z0-9_]*\.py$` |
