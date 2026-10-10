# 礼物推荐功能优化方案

> 多角色产品讨论会结论 · 2026-02-26

---

## 一、现状诊断

### 当前存在两套并行系统

| 系统 | 入口 | 实现状态 | 问题 |
|------|------|----------|------|
| **对话式推荐** | 用户在聊天中说"给爸爸推荐生日礼物" | 基本可用 | gift_advisor 子 Agent + recommend_gift 工具链完整 |
| **独立 UI 页面** | 简报卡片"看礼物"按钮 → /discover 页面 | 多处报错 | 404 (trending/recommend)、500 (memory/budget)、路由断裂 |

### 报错清单

1. `GET /gifts/trending` → 404 (路由未注册或前缀不匹配)
2. `GET /gifts/recommend` → 404 (同上)
3. `GET /gifts/memory/{id}` → 500 (`PreferenceRepository.get_top_preferences` 方法不存在)
4. `GET /gifts/budget-suggestion/{id}` → 500 (`Member.relation` 属性不存在)

### 对话式 vs 独立 UI 能力对比

| 能力 | 对话式 | 独立 UI |
|------|--------|---------|
| 个性化推荐 | LLM + 成员画像 + 网络搜索 | 依赖 API (当前报错) |
| 预算建议 | Agent 自行判断 | BudgetSuggestionService (报错) |
| 热门商品 | web_search 工具实时搜索 | TrendingGiftService (报错) |
| 偏好记忆 | MemoryService + 对话上下文 | MemberGiftMemory (报错) |
| 购买链接 | 京东搜索链接 | 同上 |
| 后续跟踪 | GiftTask + Briefing 提醒 | GiftTask UI (部分可用) |
| 对比/筛选 | 自然语言交互 | 分类筛选 UI |
| 收藏 | 无 | UserGiftSave (可用) |

---

## 二、多角色讨论

### 角色 A：产品经理 — "对话优先，页面辅助"

> 我们的产品定位是"生活秘书"，像妈妈一样。妈妈帮你挑礼物的场景是什么样的？
>
> 你说："妈，下周小李过生日，送什么好？"
> 妈妈不会甩给你一个商城页面让你自己翻。她会说："小李不是喜欢钓鱼吗？我看到一款不错的路亚竿，500 块左右，要不要看看？"
>
> **结论**：礼物推荐的主链路必须是对话，而不是一个独立的电商浏览页。

**核心观点**：
- 独立的礼物浏览页面（热门、分类、搜索）本质上是在做一个"小型电商"，这偏离了产品定位
- 用户需要的不是"逛"，而是"被推荐"
- 对话天然支持多轮 refinement："太贵了"、"换个实用点的"、"他不喝茶"

### 角色 B：UX 设计师 — "对话是引擎，卡片是展示层"

> 用户打开礼物功能有两种场景：
> 1. **有明确目标**：知道要给谁送、什么场合 → 应该直接进入对话
> 2. **无明确目标**：简报提醒"爸爸生日还有 7 天" → 需要一个引导入口
>
> 两种场景都不需要一个传统电商式的浏览页。

**推荐交互流**：

```
场景 1：简报提醒触发
┌─────────────────────────────────┐
│  简报卡片                        │
│  "爸爸生日还有 7 天"              │
│  [开始准备礼物]                   │  ← 点击后跳转到对话页
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  对话页（自动发起）               │
│                                  │
│  🤖: 爸爸的生日快到了！我来帮     │
│      你挑礼物吧。                │
│      根据我的记忆，爸爸喜欢钓鱼、 │
│      品茶，上次你送了茶具套装。   │
│      这次预算大概多少？           │
│                                  │
│  👤: 500 左右吧                  │
│                                  │
│  🤖: 好的，我帮你找了几个方案：   │
│  ┌──────────────────────────┐    │
│  │ 🎁 推荐方案               │    │
│  │                          │    │
│  │ 1. 大益普洱茶饼 · ¥388    │    │
│  │    "爸爸喜欢喝茶，但上次   │    │
│  │    送了茶具，这次换茶叶"   │    │
│  │    [查看] [换一个]        │    │
│  │                          │    │
│  │ 2. 光威路亚竿套装 · ¥459  │    │
│  │    "钓鱼爱好者的进阶装备"  │    │
│  │    [查看] [换一个]        │    │
│  │                          │    │
│  │ 3. 小米手环 8 · ¥249      │    │
│  │    "关心爸爸健康"          │    │
│  │    [查看] [换一个]        │    │
│  │                          │    │
│  │ [收藏方案] [帮我下单提醒]  │    │
│  └──────────────────────────┘    │
│                                  │
│  👤: 第二个不错，但再推荐个备选   │
│  🤖: 好的，再给你找一个...       │
└─────────────────────────────────┘
```

```
场景 2：用户主动发起
┌─────────────────────────────────┐
│  对话页                          │
│                                  │
│  👤: 同事小王帮了我一个大忙，    │
│      想送个谢礼，300 以内        │
│                                  │
│  🤖: 收到！我记得你之前提过小王   │
│      喜欢咖啡。我来找几个方案... │
│  ┌──────────────────────────┐    │
│  │ 🎁 谢礼推荐               │    │
│  │ ...                       │    │
│  └──────────────────────────┘    │
└─────────────────────────────────┘
```

### 角色 C：技术架构师 — "收敛投入，强化对话链路"

> 当前独立 UI 系统有 41 个文件，但核心 API 全在报错。修复它需要：
> - 修复路由注册问题
> - 给 PreferenceRepository 补 get_top_preferences 方法
> - 修复 Member 模型属性引用
> - 维护两套推荐逻辑（对话 + API）
>
> 不如把精力聚焦在对话链路上，让独立页面变成"对话结果的展示层"。

**建议架构**：

```
用户交互层
├── 对话（主链路）
│   ├── 自然语言 → Agent 推荐 → 富文本卡片
│   ├── 卡片内按钮 → 触发新一轮对话
│   └── "帮我下单提醒" → GiftTask + Briefing
│
└── 礼物记录页（辅助，只读为主）
    ├── 推荐历史：过去对话产生的推荐记录
    ├── 已收藏：对话中收藏的礼物
    └── 送礼日历：即将到来的送礼日期

后台能力层（对话和页面共享）
├── GiftTask：送礼任务跟踪
├── GiftHistory：送礼历史
├── PreferenceLearning：偏好学习
├── PriceTracker：比价跟踪（后台异步）
└── BriefingStrategy：主动提醒
```

### 角色 D：忙碌家长用户 — "别让我逛，帮我选"

> 我每天很忙，打开 App 就是想快速解决问题。如果要我自己去分类里翻，我还不如直接上淘宝。
>
> 我需要的是：
> 1. **提醒我**：快到某人生日了，该准备礼物了
> 2. **帮我选**：基于了解给出 2-3 个靠谱方案
> 3. **帮我跟**：选好后提醒我下单、比价、快递跟踪
> 4. **帮我记**：记住送过什么，下次别重复

### 角色 E：社交达人用户 — "人情往来要记清"

> 我经常需要回礼，关键痛点是记不住谁送过我什么、我该回什么。
>
> 最好的体验是：
> 1. 收到礼物时告诉秘书："小张送了我一瓶茅台"
> 2. 秘书自动记录人情账，到合适时机主动提醒
> 3. 回礼时基于对方偏好和之前的往来推荐方案
>
> 这些都是对话就能完成的，不需要什么独立页面。

---

## 三、优化方案

### 核心原则

**对话为中心，页面为辅助，后台为引擎。**

### Phase 1：收敛 UI，强化对话（建议立即执行）

#### 1.1 简报"看礼物"按钮改为发起对话

**当前**：点击 → 跳转到 /discover 礼物浏览页 → 多个 API 报错
**优化**：点击 → 跳转到对话页，自动发送预设 prompt

```dart
// 当前（conversation_page.dart）
case 'view_gifts':
  context.push(Routes.gifts);  // → /discover 页面

// 优化后
case 'view_gifts':
  // 跳转到对话页，自动发起礼物对话
  _sendAutoMessage(
    "帮我准备${suggestion.metadata['member_name']}的"
    "${suggestion.metadata['occasion']}礼物"
  );
```

**效果**：利用已有的 gift_advisor 子 Agent，直接在对话中完成推荐，无需修复独立页面的 API。

#### 1.2 对话中的礼物卡片增强

当前的 `GiftRecommendationBubble` 已有基础，增强为：

```
┌─────────────────────────────────┐
│ 🎁 为 爸爸 推荐的生日礼物        │
│ 预算 ¥500 · 基于 3 条记忆        │
├─────────────────────────────────┤
│ ┌─────────┐                     │
│ │  [图片]  │ 大益普洱茶饼        │
│ │         │ ¥388 · 茶叶         │
│ │         │ "爸爸爱喝茶..."     │
│ └─────────┘ [收藏] [去购买]     │
├─────────────────────────────────┤
│ ┌─────────┐                     │
│ │  [图片]  │ 光威路亚竿套装      │
│ │         │ ¥459 · 运动         │
│ │         │ "钓鱼进阶装备"      │
│ └─────────┘ [收藏] [去购买]     │
├─────────────────────────────────┤
│ [换一批推荐] [设置购买提醒]      │
│ [比价跟踪]                       │
└─────────────────────────────────┘
```

**新增能力**：
- "收藏" 按钮 → 调用已有的 UserGiftSave 服务
- "去购买" → 外链到电商（京东/淘宝搜索）
- "设置购买提醒" → 创建 GiftTask → 后续 Briefing 提醒
- "比价跟踪" → 后台 PriceTracker 异步跟踪

#### 1.3 礼物页面精简为"记录页"

将 /discover 页面从"浏览+推荐"精简为"记录+收藏"：

```
原 3 个 Tab:
  热门礼物（依赖 trending API，报错）  → 删除
  推荐记录 → 保留，展示对话中产生的推荐历史
  已收藏   → 保留

新 2 个 Tab:
  推荐历史：按成员分组展示过去的对话推荐
  已收藏：对话中收藏的礼物列表

底部 FAB:
  "AI 推荐" → 跳转对话页发起新推荐
```

### Phase 2：后台引擎增强（中期）

#### 2.1 对话后的自动化

当用户在对话中完成礼物推荐后，后台自动执行：

```python
# 对话后触发（post_session_reflection 或 tool 执行后）

async def on_gift_recommended(recommendation, member_id):
    # 1. 保存推荐记录
    await gift_history.save(recommendation)

    # 2. 更新偏好学习
    await preference_learning.update_from_recommendation(
        member_id, recommendation.selected_category
    )

    # 3. 如果有明确日期，创建送礼任务
    if recommendation.occasion_date:
        await gift_task.create_or_update(
            member_id=member_id,
            occasion=recommendation.occasion,
            date=recommendation.occasion_date,
            selected_gift=recommendation.selected_gift
        )

    # 4. 启动比价跟踪（如果用户点了"比价跟踪"）
    if recommendation.track_price:
        await price_tracker.start_tracking(
            gift_name=recommendation.selected_gift.name,
            target_price=recommendation.budget * 0.8
        )
```

#### 2.2 主动触发增强

```python
# Briefing 策略增强

class EnhancedGiftStrategy:
    async def generate_suggestions(self, user_id, date):
        suggestions = []

        # 1. 即将到来的送礼日期（已有）
        upcoming = await self._check_upcoming_dates(user_id, date)

        # 2. 人情债提醒（已有 favor_balance）
        favors = await self._check_favor_debts(user_id)

        # 3. 比价命中通知（新增）
        price_hits = await self._check_price_drops(user_id)

        # 4. 送礼任务临期提醒（已有）
        pending_tasks = await self._check_pending_tasks(user_id)

        return suggestions
```

#### 2.3 记忆驱动的推荐

强化对话中 recommend_gift 工具的上下文：

```python
# 增强 FavorGiftExecutor.recommend_gift()

async def recommend_gift(self, args, family_id, user_id):
    member = await self.member_repo.search_by_name(...)

    # 增强：从记忆系统获取更多上下文
    context = {
        "member_profile": member,
        "gift_history": await gift_history.get_for_member(member.id),
        "preferences": await preference_learning.get_scores(member.id),
        "favor_balance": await favor_service.get_balance(user_id, member.id),
        "recent_conversations": await memory.recall_about(member.name, limit=5),
        "things_to_avoid": await preference_learning.get_excluded(member.id),
    }

    # 用增强上下文生成推荐
    return await self._generate_with_context(context, args)
```

### Phase 3：闭环体验（远期）

#### 3.1 送礼全生命周期

```
发现需求 → 对话推荐 → 选定方案 → 下单提醒 → 购买确认 → 快递追踪 → 送出反馈
    ↑                                                              ↓
    └──────────── 偏好学习 ← 历史记录 ← 反馈收集 ←──────────────────┘
```

每个环节都通过对话 + 后台任务完成：
- **下单提醒**：GiftTask → Briefing → 对话提醒
- **购买确认**：用户对话"已经买了路亚竿" → 自动更新任务状态
- **快递追踪**：集成快递 API（远期）
- **反馈收集**：送出后主动问"爸爸喜欢吗？" → 更新偏好

#### 3.2 人情网络可视化（辅助页面）

在记录页新增一个可视化 Tab：

```
人情网络
├── 爸爸：已送 12 次 · 最近 2026-01 · 偏好：茶叶、钓鱼
├── 妈妈：已送 10 次 · 最近 2025-12 · 偏好：护肤、旅行
├── 小王：欠人情 · 去年帮忙搬家 · 建议回礼
└── 张阿姨：互赠 3 次 · 平衡 · 偏好：保健品
```

---

## 四、具体代码修复建议

### 立即可做（不影响架构）

#### Fix 1：简报"看礼物"跳转到对话

```dart
// mobile/lib/features/chat/presentation/pages/conversation_page.dart
case 'view_gifts':
  // 跳转到对话并自动发起
  final memberName = suggestion.metadata?['member_name'] ?? '';
  final occasion = suggestion.metadata?['occasion'] ?? '生日';
  _autoSendMessage('帮我给${memberName}准备${occasion}礼物');
  break;
```

#### Fix 2：修复 API 路由注册（如果仍需保留部分独立 API）

检查 `main.py` 中的路由注册，确保 gift 模块的 router 正确 include。

#### Fix 3：修复 PreferenceRepository（快速 patch）

```python
# recommendation_repositories.py
async def get_top_preferences(
    self, member_id: UUID, limit: int = 5
) -> List[GiftPreference]:
    """按 score 降序返回偏好"""
    result = await self.session.execute(
        select(GiftPreference)
        .where(GiftPreference.member_id == member_id)
        .where(GiftPreference.score > 0)
        .order_by(GiftPreference.score.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
```

#### Fix 4：修复 Member.relation 引用

```python
# budget_suggestion_service.py line 118
# 旧：if member and member.relation:
# 新：从 MemberRelation 表查询
relation = await self._get_member_relation(member.id, user_id)
if relation:
    relation_type = relation.relation_type  # 而非 member.relation
```

---

## 五、优先级排序

| 优先级 | 任务 | 工作量 | 影响 |
|--------|------|--------|------|
| P0 | 简报"看礼物"跳转改为发起对话 | 0.5 天 | 解决用户点击后遇到报错的问题 |
| P0 | 增强对话中礼物卡片的交互能力 | 1 天 | 让对话推荐可操作（收藏/购买/提醒） |
| P1 | 精简礼物页面为记录+收藏 | 1 天 | 删除报错功能，保留有价值的部分 |
| P1 | 强化 recommend_gift 工具的上下文 | 1 天 | 推荐质量提升 |
| P2 | 对话后自动化（任务/比价/偏好） | 2 天 | 闭环体验 |
| P2 | 修复独立 API（如果仍需） | 1 天 | 兜底 |
| P3 | 送礼全生命周期管理 | 3 天 | 长期价值 |
| P3 | 人情网络可视化 | 2 天 | 附加价值 |

---

## 六、结论

**共识**：当前礼物模块的独立 UI 与产品"对话为中心"的定位存在冲突，且技术实现存在多处断裂。

**决策**：
1. **短期**：将所有礼物入口收敛到对话流程，简报卡片点击直接发起对话而非跳转浏览页
2. **中期**：强化对话链路的后台能力（自动化任务、偏好学习、比价）
3. **长期**：构建以对话为中心的送礼全生命周期管理
4. **保留**：推荐历史页 + 收藏页作为"只读记录"的辅助入口

**一句话**：不做小电商，做贴心的送礼秘书。
