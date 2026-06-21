"""add demo traffic jobs

Revision ID: 146526398b6a
"""

revision = "146526398b6a"
down_revision = None


def upgrade():
    # Creates a 'jobs' table. This is schema history, not a worker.
    op.create_table("jobs")


def downgrade():
    op.drop_table("jobs")
