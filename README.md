# astrbot_plugin_strip_thinking

一个很小的 AstrBot 插件，用来清理第三方模型/中转把推理内容直接混进最终正文的问题。

## 作用

当模型返回：

```text
<thinking>
这里是模型推理内容……
</thinking>

这里才是最终回复。
```

插件会在 AstrBot 发送消息前将其处理为：

```text
这里才是最终回复。
```

同时兼容：

- `<think>...</think>`
- `<thinking>...</thinking>`
- 标签大小写差异
- 多行推理内容

提取到的推理文本会尽量写入 `LLMResponse.reasoning_content`，不再保留在用户可见的 `completion_text` 中。

## 安全策略

插件只删除**完整闭合**的 thinking 块。

如果第三方只返回了 `<thinking>` 却没有闭合标签，插件不会强行删除后续文本，避免把正常回复一起吞掉。

## 安装

将本仓库作为 AstrBot 插件安装，或把仓库目录放到：

```text
AstrBot/data/plugins/astrbot_plugin_strip_thinking
```

然后在 AstrBot WebUI 中重载插件。

## 说明

本插件不负责开启或关闭模型的 Thinking/Reasoning，只负责清理第三方服务错误混入最终正文的 XML 风格推理标签。
