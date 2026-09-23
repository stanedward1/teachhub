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

    Args:
        message: 错误描述（不得包含密钥等敏感信息）。
        truncated: True 表示失败原因是输出被 max_tokens 截断
            （``finish_reason == "length"``），正文可能为空 ——
            调用方据此可用更大预算重试一次。
    """

    def __init__(self, message: str, *, truncated: bool = False):
        super().__init__(message)
        self.truncated = truncated


#: HTTP 状态码 → 可直接行动的中文提示。
#: 这类错误**重试不会有不同结果**，必须先由人去平台侧处理（充值 / 换密钥 / 改模型），
#: 所以把结论放在最前面，让教师一眼知道该找谁，而不是对着一串英文 JSON 发懵。
_HTTP_ERROR_HINTS: dict[int, str] = {
    401: "AI 服务鉴权失败（密钥无效或已过期），请在平台设置中重新配置凭证",
    402: "AI 服务账户余额不足，请充值后重试",
    403: "上游拒绝访问（密钥无权调用该模型，或模型名填写有误）",
    429: "触发上游调用频率限制，请稍后重试",
}


def _describe_http_error(status_code: int, snippet: str) -> str:
    """把上游的 HTTP 错误翻译成「结论 + 原始片段」。

    原始片段保留是为了排查（截断到 160 字符），但可读结论必须排在最前 ——
    教师看到的是「余额不足，请充值」，运维仍能从片段里拿到上游原文。
    """
    hint = _HTTP_ERROR_HINTS.get(status_code)
    if hint is None and 500 <= status_code < 600:
        hint = "上游 AI 服务异常，请稍后重试"
    if hint is None:
        return f"服务返回 {status_code}：{snippet}"
    return f"{hint}（服务返回 {status_code}：{snippet}）"


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


def supports_thinking_control(base_url: str | None) -> bool:
    """判断该端点是否支持 DeepSeek 专有的思考控制字段。

    ``thinking`` / ``reasoning_effort`` 是 DeepSeek 专有字段；其他 OpenAI 兼容服务商
    对未知 body 字段可能直接返回 400，故只对 DeepSeek 端点发送。
    """
    return bool(base_url) and "deepseek" in (base_url or "").lower()


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
    timeout: int | None = None,
    temperature: float = 0.2,
    thinking: str | None = None,
    reasoning_effort: str | None = None,
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
        thinking: 思考模式开关（``enabled`` / ``disabled``），仅对支持的服务商下发。
        reasoning_effort: 思考强度（``low`` / ``high`` / ``max``），仅对支持的服务商下发。

    Returns:
        ``{"content": str, "usage": dict, "elapsed_ms": int, "finish_reason": str | None,
        "reasoning_tokens": int | None}``

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
    # 思考控制是 DeepSeek 专有字段，其他 OpenAI 兼容端点对未知 body 字段可能直接 400，
    # 故只对 DeepSeek 发送；空串/None 不发送对应键，交由服务商默认。
    if supports_thinking_control(base_url):
        if thinking:
            payload["thinking"] = {"type": thinking}
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
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
        raise AiClientError(_describe_http_error(resp.status_code, snippet))

    try:
        data = resp.json()
    except ValueError as exc:
        raise AiClientError("服务返回内容不是合法 JSON") from exc

    choices = data.get("choices") or []
    if not choices:
        raise AiClientError("服务未返回任何结果")
    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    usage = data.get("usage") or {}
    # 思考产生的 token（推理模型特有）：优先取 completion_tokens_details.reasoning_tokens，
    # 兼容部分端点直接放在 usage.reasoning_tokens 的形态。
    reasoning_tokens = (
        (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        or usage.get("reasoning_tokens")
    )
    # finish_reason 提前读取，正文为空时也要据此区分「被截断」与「真空」。
    finish_reason = choices[0].get("finish_reason")
    if not content:
        if finish_reason == "length":
            raise AiClientError(
                "模型输出达到 max_tokens 上限但仍无正文（思考过程占满了输出预算）——"
                "请关闭模型思考模式，或调高平台设置中的「单次调用 max_tokens」后重新批改",
                truncated=True,
            )
        raise AiClientError("模型返回内容为空")

    return {
        "content": content,
        "usage": usage,
        "elapsed_ms": elapsed_ms,
        "finish_reason": finish_reason,
        "reasoning_tokens": reasoning_tokens,
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
            max_tokens=16,
            timeout=timeout,
            thinking=settings.AI_THINKING_MODE or None,
            reasoning_effort=settings.AI_REASONING_EFFORT or None,
        )
    except AiClientError as exc:
        return {"ok": False, "message": str(exc), "elapsed_ms": None}
    return {
        "ok": True,
        "message": "连接成功",
        "elapsed_ms": result["elapsed_ms"],
    }
