"""Update relationships using back_populates

Revision ID: d812ab051828
Revises: e6fe956cbfce
Create Date: 2025-04-17 20:07:21.495933

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd812ab051828'
down_revision = 'e6fe956cbfce'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quiz_attempt', schema=None) as batch_op:
        batch_op.alter_column('lessons_attempted',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=256),
               existing_nullable=True)
        batch_op.create_index(batch_op.f('ix_quiz_attempt_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('username',
               existing_type=sa.VARCHAR(length=64),
               nullable=False)
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=120),
               nullable=False)

    with op.batch_alter_table('vocabulary', schema=None) as batch_op:
        batch_op.alter_column('part_of_speech',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=32),
               existing_nullable=True)
        batch_op.drop_constraint('_lesson_word_pos_book_uc', type_='unique')
        batch_op.drop_index('ix_vocabulary_part_of_speech')
        batch_op.drop_index('ix_vocabulary_source_book')
        batch_op.drop_column('source_book')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vocabulary', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_book', sa.INTEGER(), nullable=False))
        batch_op.create_index('ix_vocabulary_source_book', ['source_book'], unique=False)
        batch_op.create_index('ix_vocabulary_part_of_speech', ['part_of_speech'], unique=False)
        batch_op.create_unique_constraint('_lesson_word_pos_book_uc', ['lesson_number', 'english_word', 'part_of_speech', 'source_book'])
        batch_op.alter_column('part_of_speech',
               existing_type=sa.String(length=32),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=120),
               nullable=True)
        batch_op.alter_column('username',
               existing_type=sa.VARCHAR(length=64),
               nullable=True)

    with op.batch_alter_table('quiz_attempt', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_quiz_attempt_user_id'))
        batch_op.alter_column('lessons_attempted',
               existing_type=sa.String(length=256),
               type_=sa.VARCHAR(length=200),
               existing_nullable=True)

    # ### end Alembic commands ###
