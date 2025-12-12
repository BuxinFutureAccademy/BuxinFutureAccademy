"""Add home_gallery and student_victory tables

Revision ID: add_gallery_victory
Revises: c104c57a24b8
Create Date: 2025-12-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_gallery_victory'
down_revision = 'c104c57a24b8'
branch_labels = None
depends_on = None


def upgrade():
    # Create home_gallery table
    op.create_table('home_gallery',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('media_url', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=True, default='admin'),
        sa.Column('source_project_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_featured', sa.Boolean(), nullable=True, default=False),
        sa.Column('display_order', sa.Integer(), nullable=True, default=0),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['source_project_id'], ['student_project.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create student_victory table
    op.create_table('student_victory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('achievement_type', sa.String(length=50), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('achievement_date', sa.Date(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('student_name', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_featured', sa.Boolean(), nullable=True, default=False),
        sa.Column('display_order', sa.Integer(), nullable=True, default=0),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('student_victory')
    op.drop_table('home_gallery')

