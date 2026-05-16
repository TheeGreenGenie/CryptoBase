"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(length=42), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("reputation_score", sa.Integer(), nullable=False),
        sa.Column("kyc_status", sa.String(length=32), nullable=False),
        sa.Column("risk_tolerance", sa.String(length=32), nullable=False),
        sa.Column("max_exposure_usd", sa.Numeric(20, 2), nullable=True),
        sa.Column("preferred_assets", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_wallet_address", "users", ["wallet_address"], unique=True)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("asset_address", sa.String(length=42), nullable=False),
        sa.Column("asset_symbol", sa.String(length=32), nullable=False),
        sa.Column("position_type", sa.String(length=32), nullable=False),
        sa.Column("amount_raw", sa.String(length=96), nullable=False),
        sa.Column("amount_decimal", sa.Numeric(38, 18), nullable=False),
        sa.Column("usd_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("last_synced_block", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_positions_chain_id", "positions", ["chain_id"], unique=False)
    op.create_index("ix_positions_user_id", "positions", ["user_id"], unique=False)

    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("collateral_asset", sa.String(length=42), nullable=False),
        sa.Column("debt_asset", sa.String(length=42), nullable=False),
        sa.Column("collateral_amount_raw", sa.String(length=96), nullable=False),
        sa.Column("debt_amount_raw", sa.String(length=96), nullable=False),
        sa.Column("health_factor", sa.Numeric(38, 18), nullable=True),
        sa.Column("ltv_bps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("opened_tx_hash", sa.String(length=66), nullable=True),
        sa.Column("closed_tx_hash", sa.String(length=66), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loans_chain_id", "loans", ["chain_id"], unique=False)
    op.create_index("ix_loans_status", "loans", ["status"], unique=False)
    op.create_index("ix_loans_user_id", "loans", ["user_id"], unique=False)

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("trade_type", sa.String(length=32), nullable=False),
        sa.Column("token_in", sa.String(length=42), nullable=False),
        sa.Column("token_out", sa.String(length=42), nullable=False),
        sa.Column("amount_in_raw", sa.String(length=96), nullable=False),
        sa.Column("min_amount_out_raw", sa.String(length=96), nullable=True),
        sa.Column("quoted_amount_out_raw", sa.String(length=96), nullable=True),
        sa.Column("slippage_bps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tx_hash", sa.String(length=66), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_chain_id", "trades", ["chain_id"], unique=False)
    op.create_index("ix_trades_status", "trades", ["status"], unique=False)
    op.create_index("ix_trades_user_id", "trades", ["user_id"], unique=False)

    op.create_table(
        "agent_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("suggestion_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_tx_hash", sa.String(length=66), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_suggestions_status", "agent_suggestions", ["status"], unique=False)
    op.create_index("ix_agent_suggestions_user_id", "agent_suggestions", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_agent_suggestions_user_id", table_name="agent_suggestions")
    op.drop_index("ix_agent_suggestions_status", table_name="agent_suggestions")
    op.drop_table("agent_suggestions")
    op.drop_index("ix_trades_user_id", table_name="trades")
    op.drop_index("ix_trades_status", table_name="trades")
    op.drop_index("ix_trades_chain_id", table_name="trades")
    op.drop_table("trades")
    op.drop_index("ix_loans_user_id", table_name="loans")
    op.drop_index("ix_loans_status", table_name="loans")
    op.drop_index("ix_loans_chain_id", table_name="loans")
    op.drop_table("loans")
    op.drop_index("ix_positions_user_id", table_name="positions")
    op.drop_index("ix_positions_chain_id", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_users_wallet_address", table_name="users")
    op.drop_table("users")
