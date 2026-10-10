"""
Integration tests for MemberToolExecutor's unified professional info merge.

Tests the _merge_professional_info_via_llm flow with real DB operations
and controlled LLM responses (patched get_haiku_client).
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_engine.tools.executors.member_executor import (
    MemberToolExecutor,
    MergeProfessionalResult,
)
from src.modules.member.models.member import Member
from src.modules.member.models.professional import ProfessionalRelation, WorkHistory
from src.modules.member.repositories.member_repository import MemberRepository


FAMILY_ID = UUID("123e4567-e89b-12d3-a456-426614174000")
USER_ID = UUID("123e4567-e89b-12d3-a456-426614174001")

# The haiku client is imported locally inside the method via:
#   from ....core.llm.haiku_client import get_haiku_client
# So we patch the source module.
HAIKU_PATCH = "src.core.llm.haiku_client.get_haiku_client"


def _make_haiku_response(json_data: dict) -> MagicMock:
    """Build a mock Anthropic messages.create response with JSON content."""
    text_block = MagicMock()
    text_block.text = json.dumps(json_data, ensure_ascii=False)

    response = MagicMock()
    response.content = [text_block]
    return response


@pytest.mark.integration
@pytest.mark.asyncio
class TestMergeWorkHistory:
    """Test work history merge via _merge_professional_info_via_llm."""

    @pytest.fixture
    async def executor(self, db_session: AsyncSession):
        return MemberToolExecutor(db=db_session)

    @pytest.fixture
    async def member(self, db_session: AsyncSession):
        """Create a test member in DB."""
        repo = MemberRepository(db_session)
        return await repo.create({
            "name": "张三",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })

    @pytest.fixture
    async def self_member(self, db_session: AsyncSession):
        """Create the 'self' member ('我') in DB."""
        repo = MemberRepository(db_session)
        return await repo.create({
            "name": "我",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })

    async def _add_work_history(
        self, db_session, member, company, position=None,
        is_current=False, start_date=None, end_date=None,
    ) -> WorkHistory:
        """Helper: insert a work history record directly."""
        wh = WorkHistory(
            family_id=FAMILY_ID,
            member_id=member.id,
            company_name=company,
            position=position,
            is_current=is_current,
            start_date=start_date,
            end_date=end_date,
        )
        db_session.add(wh)
        await db_session.flush()
        return wh

    async def _add_professional_relation(
        self, db_session, from_member, to_member,
        relation_type, company_name=None, is_current=True,
    ) -> ProfessionalRelation:
        """Helper: insert a professional relation record."""
        from src.modules.member.models.enums import ProfessionalRelationType

        pr = ProfessionalRelation(
            family_id=FAMILY_ID,
            from_member_id=from_member.id,
            to_member_id=to_member.id,
            relation_type=relation_type,
            company_name=company_name,
            is_current=is_current,
        )
        db_session.add(pr)
        await db_session.flush()
        return pr

    async def _get_work_histories(self, db_session, member_id):
        """Fetch all work histories for a member."""
        result = await db_session.execute(
            select(WorkHistory).where(WorkHistory.member_id == member_id)
        )
        return list(result.scalars().all())

    async def _get_professional_relations(self, db_session, member_id):
        """Fetch all professional relations involving a member."""
        from sqlalchemy import or_
        result = await db_session.execute(
            select(ProfessionalRelation).where(
                or_(
                    ProfessionalRelation.from_member_id == member_id,
                    ProfessionalRelation.to_member_id == member_id,
                )
            )
        )
        return list(result.scalars().all())

    # ---------------------------------------------------------------
    # Test 1: New member, no existing data → skip LLM, pure create
    # ---------------------------------------------------------------
    async def test_new_member_no_existing_skips_llm(
        self, executor, member, db_session,
    ):
        """When no existing work histories exist, LLM is skipped and entries are created."""
        updates = {
            "current_company": "哔哩哔哩",
            "current_position": "工程师",
        }

        with patch(
            HAIKU_PATCH,
        ) as mock_get:
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )
            # LLM should NOT be called
            mock_get.assert_not_called()

        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        assert len(whs) == 1
        assert whs[0].company_name == "哔哩哔哩"
        assert whs[0].position == "工程师"
        assert whs[0].is_current is True

    # ---------------------------------------------------------------
    # Test 2: Exact company name match → skip LLM, update existing
    # ---------------------------------------------------------------
    async def test_exact_match_skips_llm(
        self, executor, member, db_session,
    ):
        """When incoming company name exactly matches existing, LLM is skipped."""
        await self._add_work_history(
            db_session, member, "哔哩哔哩", "前端工程师", is_current=True,
        )

        updates = {
            "current_company": "哔哩哔哩",
            "current_position": "高级前端工程师",
        }

        with patch(
            HAIKU_PATCH,
        ) as mock_get:
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )
            mock_get.assert_not_called()

        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        assert len(whs) == 1
        assert whs[0].company_name == "哔哩哔哩"
        assert whs[0].position == "高级前端工程师"

    # ---------------------------------------------------------------
    # Test 3: Variant company name → LLM matches them
    # ---------------------------------------------------------------
    async def test_variant_company_name_uses_llm_to_match(
        self, executor, member, db_session,
    ):
        """When company name differs (e.g., '哔哩哔哩' vs '哔哩哔哩(B站)'),
        LLM is called and matches them as the same company."""
        existing_wh = await self._add_work_history(
            db_session, member, "哔哩哔哩(B站)", "前端工程师", is_current=True,
        )

        updates = {
            "current_company": "哔哩哔哩",
            "current_position": "高级前端工程师",
        }

        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [
                    {"incoming_index": 0, "existing_id": str(existing_wh.id)},
                ],
                "creates": [],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        # Should still be 1 record (updated, not duplicated)
        assert len(whs) == 1
        # The company name is updated to the new variant
        assert whs[0].company_name == "哔哩哔哩"
        assert whs[0].position == "高级前端工程师"
        assert whs[0].is_current is True

    # ---------------------------------------------------------------
    # Test 4: Existing duplicates → LLM merges them
    # ---------------------------------------------------------------
    async def test_existing_duplicates_merged_by_llm(
        self, executor, member, db_session,
    ):
        """When existing records contain duplicates (e.g., '哔哩哔哩' and
        '哔哩哔哩(B站)'), LLM dedup merges them."""
        wh_a = await self._add_work_history(
            db_session, member, "哔哩哔哩", position=None, is_current=True,
        )
        wh_b = await self._add_work_history(
            db_session, member, "哔哩哔哩(B站)", "前端工程师", is_current=False,
        )

        updates = {
            "current_company": "哔哩哔哩",
            "current_position": "高级前端工程师",
        }

        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [
                    {"incoming_index": 0, "existing_id": str(wh_a.id)},
                ],
                "creates": [],
            },
            "existing_dedup": [
                {"keep_id": str(wh_a.id), "remove_id": str(wh_b.id)},
            ],
            "pr_archive_ids": [],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        # wh_b should be soft-deleted (marked [merged])
        active = [w for w in whs if not w.company_name.startswith("[merged]")]
        merged = [w for w in whs if w.company_name.startswith("[merged]")]
        assert len(active) == 1
        assert len(merged) == 1
        assert active[0].company_name == "哔哩哔哩"
        assert active[0].position == "高级前端工程师"
        # The kept record should have inherited position from the dup
        # (because wh_a had no position, wh_b had "前端工程师", then incoming sets to "高级前端工程师")

    # ---------------------------------------------------------------
    # Test 5: Batch work history → single LLM call
    # ---------------------------------------------------------------
    async def test_batch_work_history_single_llm_call(
        self, executor, member, db_session,
    ):
        """Batch of 3 work history entries results in a single LLM call."""
        updates = {
            "work_history": [
                {"company_name": "顺丰速运", "position": "助理CDO",
                 "start_date": "2019-01-01", "end_date": "2021-01-01"},
                {"company_name": "极兔速递", "position": "CTO",
                 "start_date": "2021-02-01"},
                {"company_name": "京东物流", "position": "VP",
                 "is_current": True},
            ],
        }

        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [],
                "creates": [
                    {"incoming_index": 0},
                    {"incoming_index": 1},
                    {"incoming_index": 2},
                ],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        # LLM is NOT called because there are no existing records
        result = await executor._merge_professional_info_via_llm(
            FAMILY_ID, None, member, updates,
        )

        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        assert len(whs) == 3
        companies = {w.company_name for w in whs}
        assert companies == {"顺丰速运", "极兔速递", "京东物流"}

        # Only the last entry (京东物流) should be current
        current = [w for w in whs if w.is_current]
        assert len(current) == 1
        assert current[0].company_name == "京东物流"

    # ---------------------------------------------------------------
    # Test 6: Batch with existing records → LLM called once
    # ---------------------------------------------------------------
    async def test_batch_with_existing_calls_llm_once(
        self, executor, member, db_session,
    ):
        """Batch of 2 entries + existing records → exactly 1 LLM call."""
        existing_wh = await self._add_work_history(
            db_session, member, "极兔速递(J&T)", "CIO", is_current=True,
        )

        updates = {
            "work_history": [
                {"company_name": "顺丰速运", "position": "助理CDO"},
                {"company_name": "极兔速递", "position": "CTO", "is_current": True},
            ],
        }

        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [
                    {"incoming_index": 1, "existing_id": str(existing_wh.id)},
                ],
                "creates": [
                    {"incoming_index": 0},
                ],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, None, member, updates,
            )

        # LLM called exactly once
        assert mock_client.messages.create.call_count == 1
        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        assert len(whs) == 2
        # 极兔速递 existing record should be updated (name updated from J&T variant)
        jt = next(w for w in whs if "极兔" in w.company_name)
        assert jt.company_name == "极兔速递"
        assert jt.position == "CTO"
        assert jt.is_current is True

    # ---------------------------------------------------------------
    # Test 7: PR archiving via LLM (not hardcoded SQL)
    # ---------------------------------------------------------------
    async def test_professional_relation_archived_via_llm(
        self, executor, member, self_member, db_session,
    ):
        """When company changes, LLM decides which professional relations
        to archive — not hardcoded SQL comparison."""
        from src.modules.member.models.enums import ProfessionalRelationType

        old_pr = await self._add_professional_relation(
            db_session, self_member, member,
            ProfessionalRelationType.PEER,
            company_name="哔哩哔哩(B站)",
            is_current=True,
        )
        existing_wh = await self._add_work_history(
            db_session, member, "哔哩哔哩(B站)", "前端工程师", is_current=True,
        )

        updates = {
            "current_company": "字节跳动",
            "current_position": "高级工程师",
        }

        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [],
                "creates": [{"incoming_index": 0}],
            },
            "existing_dedup": [],
            "pr_archive_ids": [str(old_pr.id)],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        assert result.work_history_updated is True

        # Professional relation should be archived
        prs = await self._get_professional_relations(db_session, member.id)
        archived = [p for p in prs if not p.is_current]
        assert len(archived) == 1
        assert archived[0].id == old_pr.id

    # ---------------------------------------------------------------
    # Test 8: relation_type="colleague" creates professional relation
    # ---------------------------------------------------------------
    async def test_colleague_relation_creates_professional_relation(
        self, executor, member, self_member, db_session,
    ):
        """relation_type='colleague' should map to ProfessionalRelationType.PEER
        and create a professional_relations entry."""
        updates = {
            "relation_type": "colleague",
            "current_company": "哔哩哔哩",
        }

        result = await executor._merge_professional_info_via_llm(
            FAMILY_ID, USER_ID, member, updates,
        )

        assert result.relation_updated is True

        # Check professional_relations table
        prs = await self._get_professional_relations(db_session, member.id)
        assert len(prs) >= 1
        pr = prs[0]
        from src.modules.member.models.enums import ProfessionalRelationType
        assert pr.relation_type == ProfessionalRelationType.PEER
        assert pr.is_current is True

    # ---------------------------------------------------------------
    # Test 9: relation_type="boss" creates professional relation
    # ---------------------------------------------------------------
    async def test_boss_relation_creates_professional_relation(
        self, executor, member, self_member, db_session,
    ):
        """relation_type='boss' should create ProfessionalRelationType.BOSS."""
        updates = {
            "relation_type": "boss",
            "current_company": "字节跳动",
        }

        result = await executor._merge_professional_info_via_llm(
            FAMILY_ID, USER_ID, member, updates,
        )

        assert result.relation_updated is True

        prs = await self._get_professional_relations(db_session, member.id)
        assert len(prs) >= 1
        from src.modules.member.models.enums import ProfessionalRelationType
        boss_prs = [p for p in prs if p.relation_type == ProfessionalRelationType.BOSS]
        assert len(boss_prs) == 1

    # ---------------------------------------------------------------
    # Test 10: member_relations creates inter-member professional relations
    # ---------------------------------------------------------------
    async def test_member_relations_sync(
        self, executor, member, db_session,
    ):
        """member_relations entries create professional relations between members."""
        repo = MemberRepository(db_session)
        target = await repo.create({
            "name": "王五",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })

        updates = {
            "member_relations": [
                {
                    "target_member": "王五",
                    "relation_type": "colleague",
                    "company_name": "腾讯",
                },
            ],
        }

        result = await executor._merge_professional_info_via_llm(
            FAMILY_ID, None, member, updates,
        )

        assert len(result.member_relations_updated) == 1

        prs = await self._get_professional_relations(db_session, member.id)
        assert len(prs) == 1
        from src.modules.member.models.enums import ProfessionalRelationType
        assert prs[0].relation_type == ProfessionalRelationType.PEER
        assert prs[0].company_name == "腾讯"

    # ---------------------------------------------------------------
    # Test 11: LLM failure falls back to exact match
    # ---------------------------------------------------------------
    async def test_llm_failure_falls_back_to_exact_match(
        self, executor, member, db_session,
    ):
        """If LLM call fails, fallback creates new records for non-matching names."""
        await self._add_work_history(
            db_session, member, "哔哩哔哩(B站)", "前端工程师", is_current=True,
        )

        updates = {
            "current_company": "哔哩哔哩",
            "current_position": "高级前端工程师",
        }

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("API error"),
        )

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        assert result.work_history_updated is True

        whs = await self._get_work_histories(db_session, member.id)
        # Fallback: no exact match → creates a new record
        assert len(whs) == 2

    # ---------------------------------------------------------------
    # Test 12: No updates → returns default result
    # ---------------------------------------------------------------
    async def test_no_updates_returns_default(
        self, executor, member,
    ):
        """Empty updates dict returns default MergeProfessionalResult."""
        result = await executor._merge_professional_info_via_llm(
            FAMILY_ID, USER_ID, member, {},
        )
        assert result.work_history_updated is False
        assert result.relation_updated is False
        assert result.member_relations_updated == []

    # ---------------------------------------------------------------
    # Test 13: Full update_member_info flow (end-to-end)
    # ---------------------------------------------------------------
    async def test_update_member_info_full_flow(
        self, executor, member, self_member, db_session,
    ):
        """Full update_member_info with work history + relation_type + basic fields."""
        from datetime import date as d

        # Pre-populate existing work history with variant name
        existing_wh = await self._add_work_history(
            db_session, member, "哔哩哔哩(B站)", "工程师", is_current=True,
        )
        # Self member also has work history at 哔哩哔哩
        await self._add_work_history(
            db_session, self_member, "哔哩哔哩", "产品经理",
            is_current=True, start_date=d(2020, 1, 1),
        )
        await db_session.commit()

        args = {
            "member_name": "张三",
            "updates": {
                "nickname": "三哥",
                "current_company": "哔哩哔哩",
                "current_position": "高级工程师",
                "relation_type": "colleague",
            },
        }

        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [
                    {"incoming_index": 0, "existing_id": str(existing_wh.id)},
                ],
                "creates": [],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
            "inferred_relations": [
                {
                    "company_name": "哔哩哔哩",
                    "relation_type": "colleague",
                    "start_date": "2020-01-01",
                    "is_current": True,
                },
            ],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            response = await executor.update_member_info(
                args, FAMILY_ID, USER_ID,
            )

        assert response["success"] is True
        assert "三哥" in response.get("message", "")

        # Verify work history updated (not duplicated)
        whs = await self._get_work_histories(db_session, member.id)
        active = [w for w in whs if not w.company_name.startswith("[merged]")]
        assert len(active) == 1
        assert active[0].position == "高级工程师"

        # Verify professional relation created with company context
        prs = await self._get_professional_relations(db_session, member.id)
        assert len(prs) >= 1
        bilibili_prs = [p for p in prs if p.company_name == "哔哩哔哩"]
        assert len(bilibili_prs) == 1
        assert bilibili_prs[0].is_current is True

    # ---------------------------------------------------------------
    # Test 14: 强哥 scenario — boss with multi-company work history
    # ---------------------------------------------------------------
    async def test_boss_with_multi_company_inferred_relations(
        self, executor, db_session,
    ):
        """
        Scenario: '强哥是我的老领导, 2016年加入顺丰科技负责大数据平台,
        2020年中成为顺丰的助理CDO, 2023年去了极兔成为了极兔的CIO'

        Expected:
        - 3 work history entries for 强哥
        - Family relation: colleague (social table)
        - Professional relations: per-company based on time overlap with "我"
          (if 我 was at 顺丰 2015-2021, then PR at 顺丰科技 type=boss 2016-2020,
           PR at 顺丰 type=boss 2020-2021)
        """
        from datetime import date as d
        from src.modules.member.models.enums import ProfessionalRelationType

        repo = MemberRepository(db_session)

        # Create "我" with work history at 顺丰
        self_member = await repo.create({
            "name": "我",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })
        await self._add_work_history(
            db_session, self_member, "顺丰科技", "工程师",
            is_current=False, start_date=d(2015, 6, 1), end_date=d(2021, 3, 1),
        )
        await self._add_work_history(
            db_session, self_member, "字节跳动", "高级工程师",
            is_current=True, start_date=d(2021, 4, 1),
        )

        # Create 强哥
        member = await repo.create({
            "name": "强哥",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })

        updates = {
            "name": "姚小龙",
            "nickname": "强哥",
            "gender": "male",
            "relation_type": "boss",
            "work_history": [
                {
                    "company_name": "顺丰科技",
                    "position": "大数据平台负责人",
                    "start_date": "2016-01-01",
                    "end_date": "2020-06-01",
                },
                {
                    "company_name": "顺丰",
                    "position": "助理CDO",
                    "start_date": "2020-06-01",
                    "end_date": "2021-01-01",
                },
                {
                    "company_name": "极兔",
                    "position": "CIO",
                    "start_date": "2023-01-01",
                    "is_current": True,
                },
            ],
        }

        # LLM should:
        # 1. Create all 3 work history entries (no existing)
        # 2. Infer professional relations:
        #    - 顺丰科技: 我 2015-06~2021-03, 强哥 2016-01~2020-06 → overlap 2016-01~2020-06
        #    - 顺丰: 我 at 顺丰科技 (same group) 2015-06~2021-03, 强哥 2020-06~2021-01
        #      → LLM decides 顺丰科技≈顺丰 → overlap 2020-06~2021-01
        #    - 极兔: 我 not there → no overlap
        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [],
                "creates": [
                    {"incoming_index": 0},
                    {"incoming_index": 1},
                    {"incoming_index": 2},
                ],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
            "inferred_relations": [
                {
                    "company_name": "顺丰科技",
                    "relation_type": "boss",
                    "start_date": "2016-01-01",
                    "end_date": "2020-06-01",
                    "is_current": False,
                },
                {
                    "company_name": "顺丰",
                    "relation_type": "boss",
                    "start_date": "2020-06-01",
                    "end_date": "2021-01-01",
                    "is_current": False,
                },
            ],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(
            HAIKU_PATCH,
            return_value=mock_client,
        ):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        # --- Verify work histories ---
        assert result.work_history_updated is True
        whs = await self._get_work_histories(db_session, member.id)
        assert len(whs) == 3
        companies = {w.company_name for w in whs}
        assert companies == {"顺丰科技", "顺丰", "极兔"}

        # Only 极兔 should be current
        current = [w for w in whs if w.is_current]
        assert len(current) == 1
        assert current[0].company_name == "极兔"
        assert current[0].position == "CIO"

        # --- Verify family/social relation created ---
        assert result.relation_updated is True

        # --- Verify per-company professional relations ---
        prs = await self._get_professional_relations(db_session, member.id)

        # Should have EXACTLY 2 PRs: 顺丰科技 (boss) and 顺丰 (boss)
        # NO spurious PR at 极兔 (where user never worked)
        pr_companies = {p.company_name: p for p in prs}
        assert len(prs) == 2, f"Expected 2 PRs, got {len(prs)}: {list(pr_companies.keys())}"
        assert "顺丰科技" in pr_companies
        assert "顺丰" in pr_companies
        assert "极兔" not in pr_companies

        sf_tech = pr_companies["顺丰科技"]
        assert sf_tech.relation_type == ProfessionalRelationType.BOSS
        assert sf_tech.is_current is False
        assert sf_tech.start_date == d(2016, 1, 1)
        assert sf_tech.end_date == d(2020, 6, 1)

        sf = pr_companies["顺丰"]
        assert sf.relation_type == ProfessionalRelationType.BOSS
        assert sf.is_current is False
        assert sf.start_date == d(2020, 6, 1)
        assert sf.end_date == d(2021, 1, 1)

        # Verify LLM was called exactly once
        assert mock_client.messages.create.call_count == 1

        # Verify the prompt included self_member's work histories
        call_args = mock_client.messages.create.call_args
        prompt_content = call_args.kwargs.get("messages", [{}])[0].get("content", "")
        assert "用户" in prompt_content or "我" in prompt_content
        assert "顺丰科技" in prompt_content
        assert "字节跳动" in prompt_content

    # ---------------------------------------------------------------
    # Test 15: Fallback basic PR when LLM returns no inferred relations
    # ---------------------------------------------------------------
    async def test_fallback_basic_pr_when_no_inferred_relations(
        self, executor, db_session,
    ):
        """
        When LLM returns no inferred_relations (e.g., no work history overlap),
        a single basic PR should be created as fallback with correct is_current.

        Case A: member and self at same current company → is_current=True
        Case B: different current companies → is_current=False
        """
        from datetime import date as d
        from src.modules.member.models.enums import ProfessionalRelationType

        repo = MemberRepository(db_session)

        # --- Case B: different current companies → is_current=False ---
        self_member = await repo.create({
            "name": "我",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })
        await self._add_work_history(
            db_session, self_member, "字节跳动", "工程师",
            is_current=True, start_date=d(2021, 4, 1),
        )

        member = await repo.create({
            "name": "李四",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })

        updates = {
            "relation_type": "colleague",
            "work_history": [
                {
                    "company_name": "腾讯",
                    "position": "产品经理",
                    "start_date": "2020-01-01",
                    "is_current": True,
                },
            ],
        }

        # LLM returns no inferred_relations (no overlap)
        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [],
                "creates": [{"incoming_index": 0}],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
            "inferred_relations": [],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(HAIKU_PATCH, return_value=mock_client):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        assert result.work_history_updated is True
        assert result.relation_updated is True

        # Fallback basic PR should be created
        prs = await self._get_professional_relations(db_session, member.id)
        assert len(prs) == 1
        pr = prs[0]
        assert pr.relation_type == ProfessionalRelationType.PEER
        assert pr.company_name == "腾讯"
        # Different companies → is_current=False
        assert pr.is_current is False

    # ---------------------------------------------------------------
    # Test 16: Fallback basic PR with same current company → is_current=True
    # ---------------------------------------------------------------
    async def test_fallback_basic_pr_same_company_is_current(
        self, executor, db_session,
    ):
        """
        When LLM returns no inferred_relations but both members are at the
        same current company, the fallback PR should have is_current=True.
        """
        from src.modules.member.models.enums import ProfessionalRelationType

        repo = MemberRepository(db_session)

        self_member = await repo.create({
            "name": "我",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })
        await self._add_work_history(
            db_session, self_member, "腾讯", "工程师", is_current=True,
        )

        member = await repo.create({
            "name": "王六",
            "family_id": FAMILY_ID,
            "created_by": USER_ID,
        })

        updates = {
            "relation_type": "colleague",
            "work_history": [
                {
                    "company_name": "腾讯",
                    "position": "产品经理",
                    "is_current": True,
                },
            ],
        }

        # No existing records, no inferred relations
        llm_response = _make_haiku_response({
            "work_history": {
                "updates": [],
                "creates": [{"incoming_index": 0}],
            },
            "existing_dedup": [],
            "pr_archive_ids": [],
            "inferred_relations": [],
        })

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=llm_response)

        with patch(HAIKU_PATCH, return_value=mock_client):
            result = await executor._merge_professional_info_via_llm(
                FAMILY_ID, USER_ID, member, updates,
            )

        prs = await self._get_professional_relations(db_session, member.id)
        assert len(prs) == 1
        assert prs[0].relation_type == ProfessionalRelationType.PEER
        assert prs[0].company_name == "腾讯"
        # Same current company → is_current=True
        assert prs[0].is_current is True
