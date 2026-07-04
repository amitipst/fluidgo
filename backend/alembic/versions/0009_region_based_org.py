"""
Migration 0009: Region-based org structure
- Rename 'bu' semantically to represent India regions
- Add region analytics slicing
- Update Amit Singh to business_head scope (sees all regions)
- Existing 'bu' column stays in DB (backward compat) — just update values

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

# Canonical region values for fluidPro India
REGIONS = [
    'India - North',
    'India - South',
    'India - West',
    'India - East',
    'India - Central',
]

def upgrade():
    # Add region column (maps to bu semantically)
    op.add_column('users', sa.Column('region', sa.String(100), nullable=True))

    # Migrate existing bu values → region values
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE users SET region = CASE
            WHEN bu = 'West'  THEN 'India - West'
            WHEN bu = 'North' THEN 'India - North'
            WHEN bu = 'South' THEN 'India - South'
            WHEN bu = 'East'  THEN 'India - East'
            ELSE 'India - West'
        END
    """))

    # Update Amit Singh to business_head — he sees all regions
    conn.execute(sa.text("""
        UPDATE users
        SET role = 'business_head', region = 'Global - fluidPro'
        WHERE email IN ('amit@wepsol.com', 'amit.singh@wepsol.com')
    """))

    op.create_index('ix_users_region', 'users', ['region'])
    op.create_index('ix_users_business_region', 'users', ['business', 'region'])

    # Add region to analytics-relevant tables for fast slicing
    op.add_column('dsr_daily', sa.Column('region', sa.String(100), nullable=True))
    op.add_column('pipeline', sa.Column('region', sa.String(100), nullable=True))

    # Backfill dsr_daily.region from user.region
    conn.execute(sa.text("""
        UPDATE dsr_daily d
        SET region = u.region
        FROM users u
        WHERE d.user_id = u.id
    """))

    # Backfill pipeline.region
    conn.execute(sa.text("""
        UPDATE pipeline p
        SET region = u.region
        FROM users u
        WHERE p.user_id = u.id
    """))

    op.create_index('ix_dsr_region', 'dsr_daily', ['region'])
    op.create_index('ix_pipeline_region', 'pipeline', ['region'])

def downgrade():
    op.drop_index('ix_pipeline_region', 'pipeline')
    op.drop_index('ix_dsr_region', 'dsr_daily')
    op.drop_column('pipeline', 'region')
    op.drop_column('dsr_daily', 'region')
    op.drop_index('ix_users_business_region', 'users')
    op.drop_index('ix_users_region', 'users')
    op.drop_column('users', 'region')
