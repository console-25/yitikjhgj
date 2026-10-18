"""Remove the legacy SQLite role check that blocks Super Admin creation.

Revision ID: 68a02e0f29f2
Revises: 172997f4c441
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa


revision = '68a02e0f29f2'
down_revision = '172997f4c441'
branch_labels = None
depends_on = None

ROLE_CHECK = "role IN ('super_admin','admin','support','billing','client')"
NAMING = {'ck': 'ck_%(table_name)s_%(column_0_name)s'}


def _role_checks():
    return [
        item for item in sa.inspect(op.get_bind()).get_check_constraints('user')
        if 'role' in (item.get('sqltext') or '').lower()
    ]


def upgrade():
    checks = _role_checks()
    with op.batch_alter_table('user', schema=None, naming_convention=NAMING) as batch_op:
        for item in checks:
            # With NAMING, unnamed SQLite constraints are reflected as ck_user_.
            batch_op.drop_constraint(item.get('name') or 'ck_user_', type_='check')
        batch_op.create_check_constraint('ck_user_role_supported', ROLE_CHECK)


def downgrade():
    checks = _role_checks()
    with op.batch_alter_table('user', schema=None, naming_convention=NAMING) as batch_op:
        for item in checks:
            batch_op.drop_constraint(item.get('name') or 'ck_user_', type_='check')
        batch_op.create_check_constraint('ck_user_role_supported', ROLE_CHECK)
