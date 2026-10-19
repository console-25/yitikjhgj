"""Workspace settings, ticket routing and plan presentation."""
from alembic import op
import sqlalchemy as sa
revision = 'c83a41d9a120'
down_revision = '68a02e0f29f2'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('workspace_setting', sa.Column('key',sa.String(60),primary_key=True),sa.Column('value',sa.JSON(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False))
    op.create_table('plan_addon',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('name',sa.String(100),nullable=False),sa.Column('description',sa.String(500),nullable=False),sa.Column('amount',sa.Integer(),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.CheckConstraint('amount >= 0'))
    op.add_column('plan',sa.Column('featured',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('plan',sa.Column('display_order',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('ticket',sa.Column('priority',sa.String(12),nullable=False,server_default='normal'))
    if op.get_bind().dialect.name == 'sqlite':
        op.execute('ALTER TABLE ticket ADD COLUMN assigned_id INTEGER REFERENCES user(id)')
    else:
        op.add_column('ticket',sa.Column('assigned_id',sa.Integer(),sa.ForeignKey('user.id',name='fk_ticket_assigned_user')))
    op.add_column('announcement',sa.Column('archived',sa.Boolean(),nullable=False,server_default=sa.false()))

def downgrade():
    op.drop_column('announcement','archived')
    if op.get_bind().dialect.name != 'sqlite': op.drop_constraint('fk_ticket_assigned_user','ticket',type_='foreignkey')
    op.drop_column('ticket','assigned_id')
    op.drop_column('ticket','priority')
    op.drop_column('plan','display_order')
    op.drop_column('plan','featured')
    op.drop_table('plan_addon')
    op.drop_table('workspace_setting')
