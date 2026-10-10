"""Tests for EntityResolver — entity linking from user messages to member UUIDs."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.ai_engine.entity_resolver import (
    EntityResolver,
    MemberAlias,
    RELATION_ALIASES,
    resolve_entities,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def resolver(mock_db):
    return EntityResolver(db=mock_db)


def _alias(member_id, alias, alias_type="name", gender=None):
    return MemberAlias(
        member_id=member_id,
        alias=alias,
        alias_type=alias_type,
        gender=gender,
    )


# --------------------------------------------------------------------------
# Alias table constants
# --------------------------------------------------------------------------


class TestRelationAliases:
    def test_common_aliases_present(self) -> None:
        assert "爸爸" in RELATION_ALIASES
        assert "妈妈" in RELATION_ALIASES
        assert "老公" in RELATION_ALIASES
        assert "老婆" in RELATION_ALIASES
        assert "儿子" in RELATION_ALIASES
        assert "女儿" in RELATION_ALIASES

    def test_aliases_map_to_valid_relation_types(self) -> None:
        valid_types = {
            "spouse", "father", "mother", "son", "daughter", "child",
            "brother", "sister", "grandfather_paternal", "grandmother_paternal",
            "grandfather_maternal", "grandmother_maternal",
            "father_in_law", "mother_in_law",
            "uncle_paternal", "aunt_paternal", "uncle_maternal", "aunt_maternal",
        }
        for alias, rel_type in RELATION_ALIASES.items():
            assert rel_type in valid_types, f"Unknown relation type '{rel_type}' for alias '{alias}'"


# --------------------------------------------------------------------------
# Scan message
# --------------------------------------------------------------------------


class TestScanMessage:
    def test_matches_name(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "张三")]
        matched, genders = EntityResolver._scan_message("今天张三要来吃饭", aliases)
        assert mid in matched

    def test_matches_nickname(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "小明", "nickname")]
        matched, _ = EntityResolver._scan_message("小明说了什么", aliases)
        assert mid in matched

    def test_no_match_returns_empty(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "张三")]
        matched, _ = EntityResolver._scan_message("天气怎么样", aliases)
        assert len(matched) == 0

    def test_case_insensitive(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "Alice")]
        matched, _ = EntityResolver._scan_message("I met alice today", aliases)
        assert mid in matched

    def test_multiple_matches(self) -> None:
        mid1 = uuid4()
        mid2 = uuid4()
        aliases = [_alias(mid1, "张三"), _alias(mid2, "李四")]
        matched, _ = EntityResolver._scan_message("张三和李四一起去", aliases)
        assert mid1 in matched
        assert mid2 in matched

    def test_greedy_match_longer_alias_first(self) -> None:
        mid1 = uuid4()
        mid2 = uuid4()
        aliases = [
            _alias(mid1, "小明"),
            _alias(mid2, "小明哥哥"),
        ]
        matched, _ = EntityResolver._scan_message("小明哥哥来了", aliases)
        assert mid2 in matched
        # mid1 "小明" is also a substring, so it matches too
        assert mid1 in matched

    def test_records_gender(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "张三", gender="male")]
        _, genders = EntityResolver._scan_message("张三怎么样", aliases)
        assert genders[mid] == "male"


# --------------------------------------------------------------------------
# Pronoun resolution
# --------------------------------------------------------------------------


class TestPronounResolution:
    def test_no_pronoun_returns_empty(self) -> None:
        result = EntityResolver._resolve_pronouns("天气真好", [], set(), {})
        assert result == set()

    def test_single_match_no_other_gender_candidate(self) -> None:
        """If one person matched and pronoun has no other candidate, nothing added."""
        mid = uuid4()
        aliases = [_alias(mid, "张三", gender="male")]
        result = EntityResolver._resolve_pronouns(
            "他怎么样", aliases, {mid}, {mid: "male"},
        )
        assert result == set()

    def test_male_pronoun_resolves_unique_male(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "张三", gender="male")]
        result = EntityResolver._resolve_pronouns(
            "他今天心情不好", aliases, set(), {},
        )
        assert mid in result

    def test_female_pronoun_resolves_unique_female(self) -> None:
        mid = uuid4()
        aliases = [_alias(mid, "小红", gender="female")]
        result = EntityResolver._resolve_pronouns(
            "她最近很忙", aliases, set(), {},
        )
        assert mid in result

    def test_ambiguous_pronoun_no_resolution(self) -> None:
        """Multiple males — cannot resolve '他'."""
        mid1 = uuid4()
        mid2 = uuid4()
        aliases = [
            _alias(mid1, "张三", gender="male"),
            _alias(mid2, "李四", gender="male"),
        ]
        result = EntityResolver._resolve_pronouns(
            "他怎么样", aliases, set(), {},
        )
        assert result == set()


# --------------------------------------------------------------------------
# Full resolve (integration with mocked DB)
# --------------------------------------------------------------------------


class TestResolveIntegration:
    @pytest.mark.asyncio
    async def test_empty_message_returns_empty(self, resolver) -> None:
        result = await resolver.resolve("", uuid4(), uuid4())
        assert result == set()

    @pytest.mark.asyncio
    async def test_resolve_with_aliases(self, resolver) -> None:
        mid = uuid4()
        alias_table = [_alias(mid, "爸爸", "relation")]

        with patch.object(resolver, "_build_alias_table", return_value=alias_table):
            result = await resolver.resolve("爸爸今天回来吗", uuid4(), uuid4())
            assert mid in result

    @pytest.mark.asyncio
    async def test_resolve_combines_name_and_pronoun(self, resolver) -> None:
        mid1 = uuid4()
        mid2 = uuid4()
        alias_table = [
            _alias(mid1, "张三", gender="male"),
            _alias(mid2, "小红", gender="female"),
        ]

        with patch.object(resolver, "_build_alias_table", return_value=alias_table):
            result = await resolver.resolve(
                "张三和她一起去", uuid4(), uuid4(),
            )
            # "张三" matches mid1, "她" should resolve to mid2 (only female)
            assert mid1 in result
            assert mid2 in result

    @pytest.mark.asyncio
    async def test_no_aliases_returns_empty(self, resolver) -> None:
        with patch.object(resolver, "_build_alias_table", return_value=[]):
            result = await resolver.resolve("谁在家", uuid4(), uuid4())
            assert result == set()


# --------------------------------------------------------------------------
# ContextAssembler integration slot
# --------------------------------------------------------------------------


class TestContextAssemblerSlot:
    def test_resolver_callable_signature(self, resolver) -> None:
        """EntityResolver.resolve matches ContextAssembler entity_resolver slot."""
        import inspect
        sig = inspect.signature(resolver.resolve)
        params = list(sig.parameters.keys())
        assert params == ["user_message", "user_id", "family_id"]


# --------------------------------------------------------------------------
# resolve_entities standalone factory
# --------------------------------------------------------------------------


class TestResolveEntitiesFactory:
    """Test the module-level resolve_entities() convenience function."""

    @pytest.mark.asyncio
    async def test_returns_set_on_success(self) -> None:
        mid = uuid4()
        mock_db = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.db.session.get_db_session",
            return_value=mock_cm,
        ):
            with patch.object(
                EntityResolver, "resolve", return_value={mid},
            ):
                result = await resolve_entities("张三来了", uuid4(), uuid4())
        assert isinstance(result, set)
        assert mid in result

    @pytest.mark.asyncio
    async def test_returns_empty_on_db_error(self) -> None:
        with patch(
            "src.db.session.get_db_session",
            side_effect=RuntimeError("connection failed"),
        ):
            result = await resolve_entities("hello", uuid4(), uuid4())
        assert result == set()

    @pytest.mark.asyncio
    async def test_signature_matches_assembler_slot(self) -> None:
        """resolve_entities has the correct (message, user_id, family_id) -> Set[UUID] signature."""
        import inspect
        sig = inspect.signature(resolve_entities)
        params = list(sig.parameters.keys())
        assert params == ["user_message", "user_id", "family_id"]


# --------------------------------------------------------------------------
# Pronoun resolution with already_matched exclusion
# --------------------------------------------------------------------------


class TestPronounAlreadyMatchedExclusion:
    """Verify that pronoun resolution excludes already-matched members."""

    def test_pronoun_resolves_to_unmatched_male(self) -> None:
        mid1 = uuid4()
        mid2 = uuid4()
        aliases = [
            _alias(mid1, "张三", gender="male"),
            _alias(mid2, "李四", gender="male"),
        ]
        # mid1 already matched by name; "他" should resolve to mid2
        result = EntityResolver._resolve_pronouns(
            "他怎么回事", aliases, {mid1}, {mid1: "male"},
        )
        assert mid2 in result
        assert mid1 not in result

    def test_pronoun_resolves_to_unmatched_female(self) -> None:
        mid1 = uuid4()
        mid2 = uuid4()
        aliases = [
            _alias(mid1, "小红", gender="female"),
            _alias(mid2, "小芳", gender="female"),
        ]
        result = EntityResolver._resolve_pronouns(
            "她怎么样", aliases, {mid1}, {mid1: "female"},
        )
        assert mid2 in result
        assert mid1 not in result
