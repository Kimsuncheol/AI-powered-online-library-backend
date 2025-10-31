"""add sessions table

Revision ID: 56a88873c092
Revises: 7364ac84b727
Create Date: 2025-11-01 03:03:05.058825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


def _create_sessions_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_addr", sa.String(length=64), nullable=True),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.false(),
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


# revision identifiers, used by Alembic.
revision: str = '56a88873c092'
down_revision: Union[str, Sequence[str], None] = '7364ac84b727'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    target_index = "ix_sessions_member_id_last_active_at"

    if "sessions" in tables:
        _create_sessions_table("sessions__tmp")
        op.execute(
            sa.text(
                """
                INSERT INTO sessions__tmp (
                    id,
                    member_id,
                    created_at,
                    last_active_at,
                    user_agent,
                    ip_addr,
                    revoked
                )
                SELECT
                    id,
                    user_id,
                    created_at,
                    last_active_at,
                    ua,
                    ip,
                    is_revoked
                FROM sessions
                """
            )
        )
        op.drop_table("sessions")
        op.rename_table("sessions__tmp", "sessions")
    else:
        _create_sessions_table("sessions")

    op.create_index(target_index, "sessions", ["member_id", "last_active_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    target_index = "ix_sessions_member_id_last_active_at"

    if "sessions" in tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("sessions")}
        if target_index in existing_indexes:
            op.drop_index(target_index, table_name="sessions")

        op.create_table(
            "sessions__legacy",
            sa.Column("id", sa.VARCHAR(length=32), nullable=False),
            sa.Column("user_id", sa.VARCHAR(length=36), nullable=False),
            sa.Column("created_at", sa.DATETIME(), nullable=False, server_default=sa.func.now()),
            sa.Column("last_active_at", sa.DATETIME(), nullable=False, server_default=sa.func.now()),
            sa.Column("absolute_expire_at", sa.DATETIME(), nullable=False, server_default=sa.func.now()),
            sa.Column("is_revoked", sa.BOOLEAN(), nullable=False, server_default=sa.text("0")),
            sa.Column("ip", sa.VARCHAR(length=64), nullable=True),
            sa.Column("ua", sa.VARCHAR(length=512), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

        op.execute(
            sa.text(
                """
                INSERT INTO sessions__legacy (
                    id,
                    user_id,
                    created_at,
                    last_active_at,
                    absolute_expire_at,
                    is_revoked,
                    ip,
                    ua
                )
                SELECT
                    substr(id, 1, 32),
                    member_id,
                    created_at,
                    last_active_at,
                    created_at,
                    revoked,
                    ip_addr,
                    user_agent
                FROM sessions
                """
            )
        )

        op.drop_table("sessions")
        op.rename_table("sessions__legacy", "sessions")
        op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
