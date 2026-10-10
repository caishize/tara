"""Create dining and nutrition management tables

Revision ID: 011_create_dining_nutrition_tables
Revises: 010_create_shopping_tables
Create Date: 2025-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_dining_nutrition'
down_revision = '010_create_shopping_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create recipes table
    op.create_table(
        'recipes',
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('cuisine', sa.String(100), nullable=False),
        sa.Column('ingredients', postgresql.JSONB, nullable=False),
        sa.Column('instructions', postgresql.JSONB, nullable=False),
        sa.Column('difficulty', sa.String(20), nullable=False),
        sa.Column('cooking_time_minutes', sa.Integer, nullable=False),
        sa.Column('nutrition', postgresql.JSONB, nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('allergens', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('servings', sa.Integer, nullable=False, server_default='2'),
        sa.Column('image_url', sa.Text, nullable=True),
        sa.Column('video_url', sa.Text, nullable=True),
        sa.Column('is_favorite', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('last_cooked_date', sa.TIMESTAMP, nullable=True),
        sa.Column('cook_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('average_rating', sa.Float, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=True),
    )
    op.create_index('idx_recipes_family', 'recipes', ['family_id'])
    op.create_index('idx_recipes_cuisine', 'recipes', ['cuisine'])
    op.create_index('idx_recipes_difficulty', 'recipes', ['difficulty'])
    op.create_index('idx_recipes_cooking_time', 'recipes', ['cooking_time_minutes'])
    op.create_index('idx_recipes_is_favorite', 'recipes', ['is_favorite'])

    # Create ingredients table
    op.create_table(
        'ingredients',
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('purchase_date', sa.Date, nullable=True),
        sa.Column('expiry_date', sa.Date, nullable=True),
        sa.Column('storage_location', sa.String(50), nullable=True),
        sa.Column('barcode', sa.String(100), nullable=True),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_consumed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=True),
    )
    op.create_index('idx_ingredients_family', 'ingredients', ['family_id'])
    op.create_index('idx_ingredients_category', 'ingredients', ['category'])
    op.create_index('idx_ingredients_expiry_date', 'ingredients', ['expiry_date'])
    op.create_index('idx_ingredients_is_consumed', 'ingredients', ['is_consumed'])

    # Create meal_records table
    op.create_table(
        'meal_records',
        sa.Column('meal_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('meal_type', sa.String(20), nullable=False),
        sa.Column('meal_date', sa.Date, nullable=False),
        sa.Column('meal_time', sa.Time, nullable=True),
        sa.Column('recipes', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('dishes', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('location', sa.String(20), nullable=False, server_default='home'),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('participants', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('total_cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('rating', sa.Integer, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('photos', postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column('nutrition_summary', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=True),
    )
    op.create_index('idx_meal_records_family', 'meal_records', ['family_id'])
    op.create_index('idx_meal_records_date', 'meal_records', ['meal_date'])
    op.create_index('idx_meal_records_type', 'meal_records', ['meal_type'])
    op.create_index('idx_meal_records_location', 'meal_records', ['location'])

    # Create restaurants table
    op.create_table(
        'restaurants',
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('cuisine', sa.String(100), nullable=False),
        sa.Column('address', sa.Text, nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('avg_cost_per_person', sa.Numeric(10, 2), nullable=True),
        sa.Column('specialty_dishes', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('rating', sa.Float, nullable=True),
        sa.Column('visit_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_visit_date', sa.Date, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('photos', postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('delivery_platforms', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('opening_hours', postgresql.JSONB, nullable=True),
        sa.Column('is_favorite', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=True),
    )
    op.create_index('idx_restaurants_family', 'restaurants', ['family_id'])
    op.create_index('idx_restaurants_cuisine', 'restaurants', ['cuisine'])
    op.create_index('idx_restaurants_is_favorite', 'restaurants', ['is_favorite'])
    op.create_index('idx_restaurants_is_active', 'restaurants', ['is_active'])

    # Create dietary_preferences table
    op.create_table(
        'dietary_preferences',
        sa.Column('preference_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('liked_dishes', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('disliked_dishes', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('liked_ingredients', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('disliked_ingredients', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('taste_preference', postgresql.JSONB, nullable=True),
        sa.Column('allergens', postgresql.ARRAY(sa.String), nullable=True),  # Encrypted
        sa.Column('health_restrictions', postgresql.ARRAY(sa.String), nullable=True),  # Encrypted
        sa.Column('preferred_cuisines', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('avoided_cuisines', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('dietary_goals', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=True),
    )
    op.create_index('idx_dietary_preferences_family', 'dietary_preferences', ['family_id'])

    # Create weekly_meal_plans table
    op.create_table(
        'weekly_meal_plans',
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('week_start_date', sa.Date, nullable=False),
        sa.Column('daily_meals', postgresql.JSONB, nullable=False),
        sa.Column('shopping_list', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('template_name', sa.String(100), nullable=True),
        sa.Column('is_template', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('nutrition_summary', postgresql.JSONB, nullable=True),
        sa.Column('estimated_cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=True),
    )
    op.create_index('idx_weekly_meal_plans_family', 'weekly_meal_plans', ['family_id'])
    op.create_index('idx_weekly_meal_plans_week_start', 'weekly_meal_plans', ['week_start_date'])
    op.create_index('idx_weekly_meal_plans_status', 'weekly_meal_plans', ['status'])
    op.create_index('idx_weekly_meal_plans_is_template', 'weekly_meal_plans', ['is_template'])


def downgrade() -> None:
    op.drop_table('weekly_meal_plans')
    op.drop_table('dietary_preferences')
    op.drop_table('restaurants')
    op.drop_table('meal_records')
    op.drop_table('ingredients')
    op.drop_table('recipes')
