"""第三方大模型调用客户端（OpenAI Chat Completions 兼容协议）。

职责单一：把 messages 发出去、把文本拿回来。所有失败统一收敛为 `AiClientError`，
由调用方降级处理。

安全红线（docs/AI-GRADING-PRD.md §7.1 S2）：密钥**只出现在请求头里**，
异常信息、日志、响应体中一律不得出现密钥 —— 因此下面所有报错都只引用
状态码与截断后的响应片段，绝不拼接 `api_key`。
"""
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger("teachhub.ai")


class AiClientError(Exception):
    """AI 调用失败（未配置 / 网络 / 超时 / 协议 / 服务端错误）。

    调用方一律按「降级」处理：不向终端用户抛出，只在批改结果里记 `failed`。
    """


def normalize_base_url(base_url: str) -> str:
    """把用户填写的 base_url 规范化成完整的 `chat/completions` 端点。

    兼容三种常见写法（DeepSeek / 通义 / OpenAI 兼容网关都适用）：

    - ``https://api.deepseek.com``        → 补 ``/v1/chat/completions``
    - ``https://api.deepseek.com/v1``     → 补 ``/chat/completions``
    - ``https://.../v1/chat/completions`` → 原样使用

    Raises:
        AiClientError: 地址为空。
    """
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise AiClientError("未配置服务地址")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
    timeout: int | None = None,
    temperature: float = 0.2,
) -> dict:
    """调用 ``/chat/completions`` 并返回模型文本。

    Args:
        base_url: 服务地址（未规范化，见 `normalize_base_url`）。
        api_key: 明文密钥（仅用于本次请求头，不落任何持久化结构）。
        model: 模型名称。
        messages: 对话消息列表。
        max_tokens: 单次输出上限（成本护栏）。
        timeout: 超时秒数，缺省取 `settings.AI_REQUEST_TIMEOUT`。
        temperature: 采样温度，批改取低值以保证稳定。

    Returns:
        ``{"content": str, "usage": dict, "elapsed_ms": int, "finish_reason": str | None}``

    Raises:
        AiClientError: 任一环节失败。
    """
    if not model:
        raise AiClientError("未配置模型名称")
    if not api_key:
        raise AiClientError("未配置 API Key")

    endpoint = normalize_base_url(base_url)
    effective_timeout = timeout or settings.AI_REQUEST_TIMEOUT
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    started = time.monotonic()
    try:
        with httpx.Client(timeout=effective_timeout) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise AiClientError(f"请求超时（{effective_timeout}s）") from exc
    except httpx.HTTPError as exc:
        # 只暴露异常类型名，避免把底层 URL / 请求细节带出去
        raise AiClientError(f"网络请求失败（{type(exc).__name__}）") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)

    if resp.status_code >= 400:
        snippet = (resp.text or "").replace("\n", " ")[:160]
        raise AiClientError(f"服务返回 {resp.status_code}：{snippet}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise AiClientError("服务返回内容不是合法 JSON") from exc

    choices = data.get("choices") or []
    if not choices:
        raise AiClientError("服务未返回任何结果")
    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise AiClientError("模型返回内容为空")
    # finish_reason 暴露给调用方：length 表示输出被 max_tokens 截断（文本可能非合法 JSON）
    finish_reason = choices[0].get("finish_reason")

    return {
        "content": content,
        "usage": data.get("usage") or {},
        "elapsed_ms": elapsed_ms,
        "finish_reason": finish_reason,
    }


def test_connection(*, base_url: str, api_key: str, model: str, timeout: int = 20) -> dict:
    """连通性测试：发一次最小请求，返回 ``{"ok", "message", "elapsed_ms"}``。

    供平台超管在保存凭证前自检。**不回显密钥**，失败也只返回归一化后的原因。
    """
    try:
        result = chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
            timeout=timeout,
        )
    except AiClientError as exc:
        return {"ok": False, "message": str(exc), "elapsed_ms": None}
    return {
        "ok": True,
        "message": "连接成功",
        "elapsed_ms": result["elapsed_ms"],
    }
