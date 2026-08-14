import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register


# 仅删除完整闭合的 <think>...</think> / <thinking>...</thinking> 块。
# 不处理未闭合标签，避免误删后面的正常回复。
_THINKING_BLOCK_RE = re.compile(
    r"<(?:think|thinking)\b[^>]*>(.*?)</(?:think|thinking)\s*>",
    re.IGNORECASE | re.DOTALL,
)


@register(
    "astrbot_plugin_strip_thinking",
    "AkinaSioga",
    "移除第三方模型混入正文的 <think>/<thinking> 推理块。",
    "1.0.0",
)
class StripThinkingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.on_llm_response()
    async def strip_thinking(
        self,
        event: AstrMessageEvent,
        resp: LLMResponse,
    ) -> None:
        """在 AstrBot 发送 LLM 回复前移除泄露到正文中的推理标签块。"""
        text = resp.completion_text or ""
        matches = list(_THINKING_BLOCK_RE.finditer(text))
        if not matches:
            return

        # 尽量保留已提取出的推理文本到 reasoning_content；
        # 用户可见的 completion_text 只保留最终回复。
        extracted = "\n\n".join(
            match.group(1).strip() for match in matches if match.group(1).strip()
        )
        if extracted:
            if resp.reasoning_content:
                resp.reasoning_content = f"{resp.reasoning_content}\n\n{extracted}"
            else:
                resp.reasoning_content = extracted

        cleaned = _THINKING_BLOCK_RE.sub("", text).strip()
        resp.completion_text = cleaned

        logger.debug(
            "strip_thinking: removed %d reasoning block(s) from LLM response.",
            len(matches),
        )
