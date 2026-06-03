"""Initial schema: assets, telemetry (hypertable), forecast, schedule tables.

Revision ID: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("capacity_mw", sa.Float, nullable=False),
        sa.Column("ramp_rate_mw_per_min", sa.Float, server_default="999"),
    )

    op.create_table(
        "telemetry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("power_mw", sa.Float, nullable=False),
        sa.UniqueConstraint("asset_id", "measured_at"),
    )

    # Create TimescaleDB hypertable if the extension is available
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            ) THEN
                PERFORM create_hypertable(
                    'telemetry', 'measured_at',
                    chunk_time_interval => INTERVAL '7 days',
                    if_not_exists => TRUE
                );
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("horizon_h", sa.Integer),
        sa.Column("mape", sa.Float),
        sa.Column("model_params_json", sa.String, server_default="{}"),
    )

    op.create_table(
        "forecast_intervals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("forecast_runs.id"), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True)),
        sa.Column("interval_end", sa.DateTime(timezone=True)),
        sa.Column("mean_mw", sa.Float),
        sa.Column("std_mw", sa.Float),
    )

    op.create_table(
        "schedules",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("portfolio_id", sa.Integer),
        sa.Column("date", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "schedule_intervals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("schedule_id", sa.String, sa.ForeignKey("schedules.id"), nullable=False),
        sa.Column("asset_id", sa.Integer),
        sa.Column("interval_start", sa.DateTime(timezone=True)),
        sa.Column("interval_end", sa.DateTime(timezone=True)),
        sa.Column("scheduled_mw", sa.Float),
        sa.Column("status", sa.String, server_default="DRAFT"),
    )


def downgrade() -> None:
    op.drop_table("schedule_intervals")
    op.drop_table("schedules")
    op.drop_table("forecast_intervals")
    op.drop_table("forecast_runs")
    op.drop_table("telemetry")
    op.drop_table("assets")
