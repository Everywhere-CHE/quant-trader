"""QuantTrader 启动入口。

供 PyInstaller 打包使用，避免相对导入问题。
"""
import logging
import os
import sys
from pathlib import Path

# 确保当前目录在 sys.path 中，使 `app` 包可导入
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 设置 QT_DATA_DIR 环境变量（默认指向 exe 同级的 data/ 目录）
exe_dir = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else backend_dir
data_dir = os.environ.get("QT_DATA_DIR", "") or str(exe_dir / "data")
os.environ.setdefault("QT_DATA_DIR", data_dir)

# 从 exe 同级的 .env 加载配置（CTP 账号、AI API key 等）
# 打包时 .env 不会被打进 exe 内部，需要用户自己放在 exe 旁边
env_file = exe_dir / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key not in os.environ:
                os.environ[key] = value

# 确保数据库路径指向 exe 同级的 data/ 目录，而不是 PyInstaller 临时目录
# 注意：必须覆盖 .env 中已有的 DATABASE_URL，不能用 setdefault
db_path = Path(data_dir) / "quant_trader.db"
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

# PyInstaller 打包为 GUI 模式（console=False）时 sys.stderr 为 None，
# uvicorn 的日志配置会因 stderr.isatty() 调用而崩溃。
# 此处将日志重定向到文件，同时确保 stderr 不为 None。
if sys.stderr is None:
    log_file = Path(data_dir) / "quant_trader.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    sys.stderr = open(str(log_file), "a", encoding="utf-8")

from app.main import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    import webbrowser

    # GUI 模式下 stderr 被重定向到文件，不是 TTY，
    # 显式关闭 uvicorn 日志颜色，避免 DefaultFormatter 内部调用 stderr.isatty()
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": False,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                "use_colors": False,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }

    # 绑定地址/端口读取 Settings（.env 的 HOST/PORT 可覆盖，默认仅本机）
    from app.config import get_settings

    settings = get_settings()

    # 启动后自动打开浏览器
    webbrowser.open(f"http://127.0.0.1:{settings.port}")

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
        log_config=log_config,
    )