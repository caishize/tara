"""Add memory summary and person profile tables for long-term memory

Revision ID: 049_memory_summary_tables
Revises: 048_pgvector_support
Create Date: 2026-01-23

Creates:
- memory_summaries: Consolidated memory summaries from short-term memories
- person_profiles: Aggregated person information from memories
- secretary_notes: High-level preferences and routines
- relationship_edges: Knowledge graph edges between persons

These tables support the three-layer memory architecture:
- Working Memory: Current session context (in-memory)
- Short-term Memory: conversation_memories (existing)
- Long-term Memory: memory_summaries, person_profiles (this migration)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = '049_memory_summary_tables'
down_revision = '048_pgvector_support'
branch_labels = None
depends_on = None


def table_exists(connection, table_name):
    """Check if a table exists."""
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """),
        {"table_name": table_name}
    )
    return result.scalar()


def extension_installed(connection, extension_name):
    """Check if a PostgreSQL extension is installed."""
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM pg_extension
                WHERE extname = :ext_name
            )
        """),
        {"ext_name": extension_name}
    )
    return result.scalar()


def upgrade():
    connection = op.get_bind()
    has_pgvector = extension_installed(connection, 'vector')

    # 1. Create memory_summaries table
    if not table_exists(connection, 'memory_summaries'):
        op.create_table(
            'memory_summaries',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

            # Summary type: person_profile, topic_summary, period_summary
            sa.Column('summary_type', sa.String(30), nullable=False, index=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('content', sa.Text, nullable=False),

            # Source memories that were consolidated
            sa.Column('source_memory_ids', ARRAY(UUID(as_uuid=True)), default=list),

            # Consolidated entities (merged from source memories)
            sa.Column('consolidated_entities', JSONB, default=dict),

            # Tags for quick filtering
            sa.Column('tags', ARRAY(sa.String), default=list),

            # Time period covered by this summary
            sa.Column('period_start', sa.DateTime, nullable=True),
            sa.Column('period_end', sa.DateTime, nullable=True),

            # Importance and recency
            sa.Column('importance', sa.Integer, default=5),
            sa.Column('last_updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

        # Create indexes for memory_summaries
        op.create_index('ix_memory_summaries_user_type', 'memory_summaries', ['user_id', 'summary_type'])
        op.create_index('ix_memory_summaries_family_type', 'memory_summaries', ['family_id', 'summary_type'])
        op.create_index('ix_memory_summaries_tags', 'memory_summaries', ['tags'], postgresql_using='gin')
        op.create_index('ix_memory_summaries_entities', 'memory_summaries', ['consolidated_entities'], postgresql_using='gin')

        # Add pgvector column if available
        if has_pgvector:
            op.execute("""
                ALTER TABLE memory_summaries
                ADD COLUMN embedding_v vector(1536)
            """)
            op.execute("""
                CREATE INDEX idx_memory_summaries_embedding_hnsw
                ON memory_summaries
                USING hnsw (embedding_v vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)

    # 2. Create person_profiles table
    if not table_exists(connection, 'person_profiles'):
        op.create_table(
            'person_profiles',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

            # Link to member if this person is a family member
            sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='SET NULL'), nullable=True),

            # Person identification
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('aliases', ARRAY(sa.String), default=list),  # ["老张", "张总", "Zhang San"]

            # Relationship and context
            sa.Column('relationship', sa.String(50), nullable=True),  # friend, colleague, relative, etc.
            sa.Column('relationship_context', sa.Text, nullable=True),  # How they know each other
            sa.Column('organization', sa.String(200), nullable=True),  # Company, school, etc.
            sa.Column('location', sa.String(100), nullable=True),  # City or location

            # Aggregated preferences (from memory extraction)
            sa.Column('preferences', JSONB, default=dict),
            # Example: {"likes": ["coffee", "hiking"], "dislikes": ["crowds"], "dietary": ["vegetarian"]}

            # Favor/人情 balance tracking
            sa.Column('favor_balance', sa.Float, default=0.0),  # Positive = they owe us, negative = we owe them
            sa.Column('favor_history', JSONB, default=list),  # List of favor events

            # Contact frequency and importance
            sa.Column('mention_count', sa.Integer, default=0),
            sa.Column('last_mentioned_at', sa.DateTime, nullable=True),
            sa.Column('importance', sa.Integer, default=5),  # 1-10 scale

            # Source memories
            sa.Column('source_memory_ids', ARRAY(UUID(as_uuid=True)), default=list),

            # Status
            sa.Column('status', sa.String(20), default='active'),  # active, archived, merged

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

        # Create indexes for person_profiles
        op.create_index('ix_person_profiles_user_name', 'person_profiles', ['user_id', 'name'])
        op.create_index('ix_person_profiles_family', 'person_profiles', ['family_id'])
        op.create_index('ix_person_profiles_member', 'person_profiles', ['member_id'])
        op.create_index('ix_person_profiles_aliases', 'person_profiles', ['aliases'], postgresql_using='gin')
        op.create_index('ix_person_profiles_last_mentioned', 'person_profiles', ['last_mentioned_at'])

        # Add pgvector column if available
        if has_pgvector:
            op.execute("""
                ALTER TABLE person_profiles
                ADD COLUMN embedding_v vector(1536)
            """)
            op.execute("""
                CREATE INDEX idx_person_profiles_embedding_hnsw
                ON person_profiles
                USING hnsw (embedding_v vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)

    # 3. Create secretary_notes table
    if not table_exists(connection, 'secretary_notes'):
        op.create_table(
            'secretary_notes',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

            # Note category: preference, routine, important, todo, observation
            sa.Column('category', sa.String(30), nullable=False, index=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('content', sa.Text, nullable=False),

            # Confidence and verification
            sa.Column('confidence', sa.Float, default=0.8),  # 0-1, how confident the extraction is
            sa.Column('is_user_confirmed', sa.Boolean, default=False),  # User explicitly confirmed

            # Source tracking
            sa.Column('source_memory_ids', ARRAY(UUID(as_uuid=True)), default=list),
            sa.Column('observation_count', sa.Integer, default=1),  # How many times observed

            # Relevance and priority
            sa.Column('priority', sa.Integer, default=5),  # 1-10 scale
            sa.Column('status', sa.String(20), default='active'),  # active, completed, archived

            # Context for when to surface this note
            sa.Column('trigger_keywords', ARRAY(sa.String), default=list),  # Keywords that should surface this note
            sa.Column('trigger_contexts', JSONB, default=dict),  # Contexts where this note is relevant

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('last_surfaced_at', sa.DateTime, nullable=True),
        )

        # Create indexes for secretary_notes
        op.create_index('ix_secretary_notes_user_category', 'secretary_notes', ['user_id', 'category'])
        op.create_index('ix_secretary_notes_family', 'secretary_notes', ['family_id'])
        op.create_index('ix_secretary_notes_keywords', 'secretary_notes', ['trigger_keywords'], postgresql_using='gin')
        op.create_index('ix_secretary_notes_status', 'secretary_notes', ['status'])

    # 4. Create relationship_edges table for knowledge graph
    if not table_exists(connection, 'relationship_edges'):
        op.create_table(
            'relationship_edges',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

            # The two persons being connected
            sa.Column('person_a_id', UUID(as_uuid=True), sa.ForeignKey('person_profiles.id', ondelete='CASCADE'), nullable=False),
            sa.Column('person_b_id', UUID(as_uuid=True), sa.ForeignKey('person_profiles.id', ondelete='CASCADE'), nullable=False),

            # Relationship metadata
            sa.Column('relationship_type', sa.String(50), nullable=False),  # colleague, friend, family, knows, etc.
            sa.Column('strength', sa.Float, default=0.5),  # 0-1, how strong the connection
            sa.Column('context', sa.Text, nullable=True),  # Context of how they know each other
            sa.Column('bidirectional', sa.Boolean, default=True),  # Is the relationship bidirectional?

            # Source tracking
            sa.Column('source_memory_ids', ARRAY(UUID(as_uuid=True)), default=list),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

        # Create indexes for relationship_edges
        op.create_index('ix_relationship_edges_person_a', 'relationship_edges', ['person_a_id'])
        op.create_index('ix_relationship_edges_person_b', 'relationship_edges', ['person_b_id'])
        op.create_index('ix_relationship_edges_type', 'relationship_edges', ['relationship_type'])
        op.create_index('ix_relationship_edges_user', 'relationship_edges', ['user_id'])

    # 5. Create proactive_insights table for scheduled insight generation
    if not table_exists(connection, 'proactive_insights'):
        op.create_table(
            'proactive_insights',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

            # Insight type: relationship_maintenance, favor_reminder, pattern_observation, event_preparation
            sa.Column('insight_type', sa.String(50), nullable=False, index=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('content', sa.Text, nullable=False),

            # Priority and urgency
            sa.Column('priority', sa.Integer, default=5),
            sa.Column('urgency', sa.String(20), default='normal'),  # high, normal, low

            # Related entities
            sa.Column('related_person_ids', ARRAY(UUID(as_uuid=True)), default=list),
            sa.Column('related_memory_ids', ARRAY(UUID(as_uuid=True)), default=list),
            sa.Column('related_event_ids', ARRAY(UUID(as_uuid=True)), default=list),

            # Action suggestions
            sa.Column('action_options', ARRAY(sa.String), default=list),
            sa.Column('action_data', JSONB, default=dict),

            # Status tracking
            sa.Column('status', sa.String(20), default='pending'),  # pending, shown, acted, dismissed, expired
            sa.Column('shown_at', sa.DateTime, nullable=True),
            sa.Column('acted_at', sa.DateTime, nullable=True),
            sa.Column('dismissed_at', sa.DateTime, nullable=True),

            # Scheduling
            sa.Column('scheduled_for', sa.DateTime, nullable=True),  # When to show this insight
            sa.Column('expires_at', sa.DateTime, nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

        # Create indexes for proactive_insights
        op.create_index('ix_proactive_insights_user_status', 'proactive_insights', ['user_id', 'status'])
        op.create_index('ix_proactive_insights_type', 'proactive_insights', ['insight_type'])
        op.create_index('ix_proactive_insights_scheduled', 'proactive_insights', ['scheduled_for'])

    # 6. Add consolidated flag to conversation_memories
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'conversation_memories'
                AND column_name = 'is_consolidated'
            ) THEN
                ALTER TABLE conversation_memories
                ADD COLUMN is_consolidated BOOLEAN DEFAULT FALSE;

                CREATE INDEX IF NOT EXISTS ix_conv_memories_consolidated
                ON conversation_memories (is_consolidated)
                WHERE is_consolidated = FALSE;
            END IF;
        END $$;
    """)


def downgrade():
    # Drop tables in reverse order of creation
    op.execute("DROP INDEX IF EXISTS ix_conv_memories_consolidated")
    op.execute("""
        ALTER TABLE conversation_memories
        DROP COLUMN IF EXISTS is_consolidated
    """)

    op.drop_table('proactive_insights')
    op.drop_table('relationship_edges')
    op.drop_table('secretary_notes')
    op.drop_table('person_profiles')
    op.drop_table('memory_summaries')
