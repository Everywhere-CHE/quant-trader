"""带对话管理的 AI 助手端点。"""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from ...ai.engine import AIEngine
from ...ai.presets import PRESETS
from ...conversations import _extract_display, get_conversation, update_conversation
from ..schemas import AiConfigBody, ChatRequestBody

router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_engine(request: Request) -> AIEngine:
    engine = getattr(request.app.state, "ai_engine", None)
    if engine is None:
        raise HTTPException(503, "AI engine not initialized")
    return engine


@router.get("/status")
def ai_status(request: Request) -> dict:
    return get_ai_engine(request).status()


@router.get("/presets")
def ai_presets() -> list[dict]:
    """供前端快速切换 UI 使用的主流模型预设。"""
    return PRESETS


@router.put("/config")
def ai_update_config(body: AiConfigBody, request: Request) -> dict:
    """在运行时更新 provider/model/base_url/api_key/allow_trading/auto_optimize。"""
    engine = get_ai_engine(request)
    try:
        return engine.update_config(
            provider=body.provider,
            model=body.model,
            base_url=body.base_url,
            api_key=body.api_key,
            allow_trading=body.allow_trading,
            auto_optimize=body.auto_optimize,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.put("/auto-optimize")
def ai_toggle_auto_optimize(body: dict, request: Request) -> dict:
    """开关自动策略优化功能。"""
    enabled = body.get("enabled", False)
    engine = get_ai_engine(request)
    return engine.update_config(auto_optimize=enabled)


@router.post("/chat")
async def ai_chat(body: ChatRequestBody, request: Request) -> dict:
    engine = get_ai_engine(request)
    if not engine.enabled:
        raise HTTPException(
            503,
            "No API Key configured. Please set it in the AI settings page.",
        )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    if not messages:
        raise HTTPException(422, "messages cannot be empty")

    try:
        result = await run_in_threadpool(engine.chat, messages)
    except Exception as e:
        raise HTTPException(502, f"Model call failed: {e}") from None

    # 保存/更新对话：从完整对话中提取用于展示的消息，
    # 以便把 AI 的回复也包含进来。
    conv_id = body.conversation_id
    if conv_id:
        conv = get_conversation(conv_id)
        if conv:
            update_conversation(
                conv_id, result.messages,
                display_messages=_extract_display(result.messages),
            )

    return {
        "reply": result.reply,
        "tool_calls": [asdict(t) for t in result.tool_calls],
        "messages": result.messages,
    }