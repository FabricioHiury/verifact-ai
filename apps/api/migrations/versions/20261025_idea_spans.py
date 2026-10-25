"""Preserve complete transcript context and multi-segment claim provenance."""

import sqlalchemy as sa
from alembic import op

revision = "20261025_idea_spans"
down_revision = "573a253f27f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("claims", sa.Column("end_segment_id", sa.String(36), nullable=True))
    op.add_column(
        "claims", sa.Column("transcript_context", sa.Text(), server_default="", nullable=False)
    )
    op.create_foreign_key(
        "fk_claim_end_segment", "claims", "transcript_segments", ["end_segment_id"], ["id"]
    )


def downgrade():
    op.drop_constraint("fk_claim_end_segment", "claims", type_="foreignkey")
    op.drop_column("claims", "transcript_context")
    op.drop_column("claims", "end_segment_id")
