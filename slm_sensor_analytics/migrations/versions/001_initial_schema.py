"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-29
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
        "measurements",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("sensor_type", sa.String(64), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_measurements_device_recorded",
        "measurements",
        ["device_id", sa.text("recorded_at DESC")],
    )
    op.create_index("idx_measurements_recorded_at", "measurements", ["recorded_at"])
    op.create_index("ix_measurements_device_id", "measurements", ["device_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("sensor_type", sa.String(64), nullable=False),
        sa.Column("anomaly_score", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_snapshot", sa.JSON, nullable=False),
    )
    op.create_index(
        "idx_alerts_device_triggered", "alerts", ["device_id", sa.text("triggered_at DESC")]
    )
    op.create_index("idx_alerts_triggered_at", "alerts", ["triggered_at"])
    op.create_index("ix_alerts_device_id", "alerts", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_device_id", table_name="alerts")
    op.drop_index("idx_alerts_triggered_at", table_name="alerts")
    op.drop_index("idx_alerts_device_triggered", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_measurements_device_id", table_name="measurements")
    op.drop_index("idx_measurements_recorded_at", table_name="measurements")
    op.drop_index("idx_measurements_device_recorded", table_name="measurements")
    op.drop_table("measurements")
