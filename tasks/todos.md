# TODOS

## P2 — 历史消息搜索
- **What:** 对话页内嵌入搜索入口，支持全文关键词匹配历史消息并跳转。
- **Why:** 让历史消息真正有用 — 用户可以找回任意历史上下文。
- **Pros:** 高频需求，复用本次分页 /chat/history 端点加 q 参数即可。
- **Cons:** 需要后端全文搜索支持，Flutter 搜索 UI 有一定复杂度。
- **Context:** 本次分页 API 完成后，搜索可利用同一端点加 q 参数，backend 加 WHERE content ILIKE %q% 即可快速验证。长期可替换为 PostgreSQL FTS。
- **Effort:** M (human: 3天 / CC: 25min)
- **Depends on:** 本次简报折叠+懒加载 PR 合并后实现。

## P3 — 尊日上下文自适应布局
- **What:** 根据时间段（早/午/晚）和简报已读状态，对话页自动切换展现形态。
- **Why:** 早晨打开应该看简报，下午打开已读简报应该直接到对话。
- **Pros:** 减少用户手动操作，增强 AI 助手"感知上下文"的感觉。
- **Cons:** 需要定义时间段逻辑，与 briefing_read_date 联动。
- **Context:** 依赖本次 already-read auto-collapse (#1) 基础实现。在此之上，根据 DateTime.now().hour 判断早/午/晚，调整初始滚动位置和简报状态。
- **Effort:** M (human: 3天 / CC: 30min)
- **Depends on:** 本次简报折叠+懒加载 PR 合并后实现。
