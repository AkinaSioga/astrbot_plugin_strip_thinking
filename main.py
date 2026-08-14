import re

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext


# 仅删除完整闭合的 <think>...</think> / <thinking>...</thinking> 块。
# 不处理未闭合标签，避免误删后面的正常回复。
_THINKING_BLOCK_RE = re.compile(
    r"<(?:think|thinking)\b[^>]*>.*?</(?:think|thinking)\s*>",
    re.IGNORECASE | re.DOTALL,
)


def _clean_text(text: str) -> tuple[str, int]:
    """删除完整 thinking 块，返回 (清理后的文本, 删除数量)。"""
    if not text:
        return text, 0
    matches = list(_THINKING_BLOCK_RE.finditer(text))
    if not matches:
        return text, 0
    cleaned = _THINKING_BLOCK_RE.sub("", text).strip()
    return cleaned, len(matches)


@register(
    "astrbot_plugin_strip_thinking",
    "AkinaSioga",
    "移除第三方模型混入正文的 <think>/<thinking> 推理块。",
    "1.1.0",
)
class StripThinkingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.on_llm_response(priority=1000)
    async def strip_llm_response(
        self,
        event: AstrMessageEvent,
        resp: LLMResponse,
    ) -> None:
        """第一层：直接清理 LLMResponse。"""
        text = resp.completion_text or ""
        cleaned, count = _clean_text(text)
        if not count:
            return

        resp.completion_text = cleaned
        logger.info(
            "strip_thinking: removed %d reasoning block(s) from LLMResponse.",
            count,
        )

    @filter.on_agent_done(priority=1000)
    async def strip_agent_history(
        self,
        event: AstrMessageEvent,
        run_context: ContextWrapper[AstrAgentContext],
        resp: LLMResponse,
    ) -> None:
        """第二层：清理 Agent 已写入上下文的最后一条 assistant 消息。

        AstrBot ToolLoopAgentRunner 会先把 assistant 消息写入 run_context.messages，
        再触发 on_llm_response/on_agent_done，因此只改 LLMResponse 仍可能把 thinking
        留在后续会话历史中。
        """
        if not run_context.messages:
            return

        last_message = run_context.messages[-1]
        if getattr(last_message, "role", None) != "assistant":
            return

        content = getattr(last_message, "content", None)
        removed = 0

        if isinstance(content, str):
            cleaned, count = _clean_text(content)
            if count:
                last_message.content = cleaned
                removed += count
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, TextPart):
                    cleaned, count = _clean_text(part.text)
                    if count:
                        part.text = cleaned
                        removed += count

        if removed:
            logger.info(
                "strip_thinking: removed %d reasoning block(s) from agent history.",
                removed,
            )

    @filter.on_decorating_result(priority=1000)
    async def strip_before_send(self, event: AstrMessageEvent) -> None:
        """第三层：发送前再次清理最终消息链，作为兜底。"""
        result = event.get_result()
        if result is None or not result.chain:
            return

        removed = 0
        new_chain = []
        for component in result.chain:
            if isinstance(component, Comp.Plain):
                cleaned, count = _clean_text(component.text or "")
                removed += count
                component.text = cleaned
                if not component.text.strip():
                    continue
            new_chain.append(component)

        result.chain = new_chain

        # 本插件的目标是“不把 reasoning 发给用户”。AstrBot 会在此钩子之后
        # 根据 _llm_reasoning_content 再次把推理插入消息链，因此这里同时清空它。
        event.set_extra("_llm_reasoning_content", None)

        if removed:
            logger.info(
                "strip_thinking: removed %d reasoning block(s) from outgoing chain.",
                removed,
            )
