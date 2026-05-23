"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nodes",
        sa.Column("node_id", sa.String(32), primary_key=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("meter_type", sa.String(16), nullable=False, server_default="residential"),
        sa.Column("commissioned_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "load_readings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "node_id",
            sa.String(32),
            sa.ForeignKey("nodes.node_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kwh", sa.Float, nullable=False),
        sa.Column("meter_type", sa.String(16), nullable=False, server_default="residential"),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("kwh > 0", name="ck_readings_kwh_positive"),
    )
    op.create_index("idx_readings_node_ts", "load_readings", ["node_id", sa.text("ts DESC")])
    op.create_index("idx_readings_ts", "load_readings", [sa.text("ts DESC")])

    op.create_table(
        "node_forecasts",
        sa.Column(
            "node_id",
            sa.String(32),
            sa.ForeignKey("nodes.node_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("forecast_kwh", sa.Float, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_size", sa.Integer, nullable=False, server_default="12"),
    )


def downgrade() -> None:
    op.drop_table("node_forecasts")
    op.drop_index("idx_readings_ts", table_name="load_readings")
    op.drop_index("idx_readings_node_ts", table_name="load_readings")
    op.drop_table("load_readings")
    op.drop_table("nodes")
