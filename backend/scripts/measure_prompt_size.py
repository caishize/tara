#!/usr/bin/env python3
"""Measure the actual production system prompt + tool definitions size."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.ai_engine.tools.registry import ToolRegistry
from src.ai_engine.sdk.agent_factory import SYSTEM_PROMPT_TEMPLATE


def main():
    registry = ToolRegistry()
    # Register all tool executors
    from src.ai_engine.tools.tool_bridge import ToolBridge
    bridge = ToolBridge.__new__(ToolBridge)
    bridge._registry = registry
    bridge._executors = {}
    bridge._initialized = False

    # Use registry directly to get definitions
    # First, load all executors to register tools
    import importlib
    executor_modules = [
        "src.ai_engine.tools.executors.member_executor",
        "src.ai_engine.tools.executors.event_executor",
        "src.ai_engine.tools.executors.memory_executor",
        "src.ai_engine.tools.executors.insight_executor",
        "src.ai_engine.tools.executors.relationship_executor",
        "src.ai_engine.tools.executors.trip_executor",
        "src.ai_engine.tools.executors.gift_executor",
        "src.ai_engine.tools.executors.briefing_executor",
        "src.ai_engine.tools.executors.date_executor",
        "src.ai_engine.tools.executors.views_executor",
        "src.ai_engine.tools.executors.curation_executor",
        "src.ai_engine.tools.executors.conversation_executor",
    ]

    for mod_path in executor_modules:
        try:
            mod = importlib.import_module(mod_path)
            # Find executor classes
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, type) and hasattr(obj, 'get_tool_definitions'):
                    try:
                        instance = obj.__new__(obj)
                        if hasattr(instance, 'get_tool_definitions'):
                            defs = instance.get_tool_definitions()
                            if defs:
                                for d in defs:
                                    registry.register_tool_from_dict(d)
                    except Exception:
                        pass
        except Exception as e:
            print(f"  Skip {mod_path}: {e}")

    # Fallback: just instantiate ToolBridge properly
    if len(registry._tools) == 0:
        print("  Registry empty, trying ToolBridge directly...")
        try:
            bridge2 = ToolBridge(db=None)
            tool_defs = bridge2.get_tool_definitions()
            print(f"\n  ToolBridge returned {len(tool_defs)} tools")
            tools_json = json.dumps(tool_defs, ensure_ascii=False)
            print(f"  Tool definitions JSON size: {len(tools_json)} chars")
            print(f"  Estimated tokens: ~{len(tools_json) // 3}")

            for td in tool_defs:
                td_json = json.dumps(td, ensure_ascii=False)
                print(f"    {td['name']}: {len(td_json)} chars")

        except Exception as e2:
            print(f"  ToolBridge failed: {e2}")
            import traceback; traceback.print_exc()

    # System prompt size
    # Simulate realistic context
    context = """【当前时间】
2026-02-14 00:48 (Asia/Shanghai)

【用户位置】
广东省揭阳市

【家庭成员】
- 爸爸 (id: member-001): 55岁，退休工程师
- 妈妈 (id: member-002): 53岁，家庭主妇
- 我 (id: member-003): 28岁，软件工程师
- 妹妹 (id: member-004): 25岁，设计师
- 外婆 (id: member-005): 78岁，退休教师

【已连接服务】
天气查询, 日历同步, 礼物推荐

【数据概览】
事件: 23条, 记忆: 45条, 洞察: 12条, 行程: 3条, 重要日期: 15条"""

    memories = """## 你对这个家庭的了解
- 爸爸每天早上6点起床去公园钓鱼，周末会和老朋友下棋
- 妈妈负责家庭日常采购，每周三去菜市场
- 全家每月第一个周日聚餐，通常在家里做饭
- 外婆有高血压，每天需要按时服药，每月15号复诊
- 妹妹下个月生日(3月15日)，去年送了画具套装
- 爸妈结婚纪念日是农历九月初九
- 家庭年度旅行通常安排在国庆假期
- 妈妈对海鲜过敏
- 爸爸最近在学习智能手机使用
- 外婆喜欢听评书和看戏曲节目
- 妹妹喜欢ins风的装饰，房间布置偏北欧简约
- 爸爸血压最近偏高，医生建议减少钠盐摄入
- 全家计划明年翻修老房子
- 妈妈最近在学做烘焙，经常试新食谱

## 家庭成员画像
### 爸爸
性格温和内敛，注重传统礼节。退休后生活规律，喜欢清静。与老友保持定期联系。
对新科技感兴趣但学习较慢，需要耐心指导。关心子女发展但不善表达。
最近关注：学习使用微信视频通话、计划春季钓鱼比赛
健康状况：轻度高血压，服用降压药，定期复查

### 妈妈
热情开朗，社交活跃。是家庭的核心组织者，负责大小事务安排。
对家人健康饮食很关注，经常研究养生食谱。喜欢在朋友圈分享生活。
最近关注：广场舞比赛准备、春季养生食谱、外婆健康状况
健康状况：海鲜过敏，其余正常

### 外婆
慈祥和蔼，记忆力略有下降。喜欢和孙辈聊天，经常回忆往事。
需要定期服药和复诊，饮食需要低盐低脂。偶尔会忘记吃药。
最近关注：春节后身体恢复、新一季评书更新
健康状况：高血压、轻度糖尿病，每月15号复诊

### 我
软件工程师，工作忙碌但尽量周末回家。负责家庭数字化和技术支持。
关心家人健康，经常帮爸爸妈妈解决手机问题。
最近关注：工作项目上线、计划清明短途旅行

### 妹妹
设计师，有艺术天赋。性格活泼，是家庭的开心果。
喜欢探索新事物，经常给家人推荐好物。
最近关注：即将到来的生日、新工作项目

## 本次会话之前的对话摘要
用户之前询问了关于妹妹生日礼物的建议，助手推荐了几款画具和摄影相关的礼物。
用户还问了外婆下次复诊的时间，助手提醒是2月15日。
用户提到想计划清明节全家去潮汕地区短途旅行，助手建议了几个景点。
最近一次对话中用户表示对比了几款手绘板，最终倾向于Wacom入门款。"""

    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context, memories=memories)

    print(f"\n{'='*60}")
    print("SYSTEM PROMPT SIZE ANALYSIS")
    print(f"{'='*60}")
    print(f"  Template base:     {len(SYSTEM_PROMPT_TEMPLATE)} chars")
    print(f"  Context section:   {len(context)} chars")
    print(f"  Memories section:  {len(memories)} chars")
    print(f"  Full prompt:       {len(full_prompt)} chars")
    print(f"  Estimated tokens:  ~{len(full_prompt) // 2} (Chinese ~2 chars/token)")


if __name__ == "__main__":
    main()
