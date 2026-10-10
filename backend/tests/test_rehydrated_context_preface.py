from uuid import UUID

from src.modules.conversation.context_service import RehydratedContext


def _build_context() -> RehydratedContext:
    return RehydratedContext(
        user_profile={},
        family_members_raw=[],
        recent_messages=[
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，我在。"},
        ],
        user_preferences={},
        _user_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
        _family_id=UUID("123e4567-e89b-12d3-a456-426614174002"),
        _session_id="123e4567-e89b-12d3-a456-426614174003",
    )


def test_with_conversation_preface_prepends_summary():
    ctx = _build_context()
    updated = ctx.with_conversation_preface("【Fast 摘要】\n- 已调用 query_trips")

    prompt_ctx = updated.agent_context.to_system_prompt_context()
    assert "【Fast 摘要】" in prompt_ctx
    assert "【压缩点之后的完整会话】" in prompt_ctx
    assert prompt_ctx.index("【Fast 摘要】") < prompt_ctx.index("【压缩点之后的完整会话】")


def test_with_conversation_preface_is_immutable():
    ctx = _build_context()
    updated = ctx.with_conversation_preface("preface")

    assert updated is not ctx
    assert ctx.conversation_preface == ""
    assert updated.conversation_preface == "preface"
