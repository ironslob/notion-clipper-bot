"""database id

Revision ID: aaf640656041
Revises: aa351dbad2dd
Create Date: 2021-05-26 15:26:06.949088

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aaf640656041'
down_revision = 'aa351dbad2dd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('notion_auth', sa.Column('database_id', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('notion_auth', 'database_id')
    # ### end Alembic commands ###