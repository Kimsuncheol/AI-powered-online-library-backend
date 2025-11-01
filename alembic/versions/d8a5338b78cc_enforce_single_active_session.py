"""enforce single active session per member

Revision ID: d8a5338b78cc
Revises: 56a88873c092
Create Date: 2024-11-23 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8a5338b78cc"
down_revision: Union[str, Sequence[str], None] = "56a88873c092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cleanup_duplicate_active_sessions() -> None:
    op.execute(
        sa.text(
            """
            UPDATE sessions
            SET revoked = 1
            WHERE id IN (
                SELECT id FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY member_id
                            ORDER BY last_active_at DESC, created_at DESC, id DESC
                        ) AS rn
                    FROM sessions
                    WHERE revoked = 0
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )


def _set_revoked_timestamps() -> None:
    op.execute(
        sa.text(
            """
            UPDATE sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE revoked = 1 AND revoked_at IS NULL
            """
        )
    )


def upgrade() -> None:
    """Upgrade schema to enforce single active session policy."""
    op.add_column(
        "sessions",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    _cleanup_duplicate_active_sessions()
    _set_revoked_timestamps()

    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_member_active "
                "ON sessions(member_id) WHERE revoked = 0"
            )
        )
    elif dialect == "postgresql":
        op.create_index(
            "uq_sessions_member_active",
            "sessions",
            ["member_id"],
            unique=True,
            postgresql_where=sa.text("revoked = false"),
        )
    else:
        # For dialects without partial unique support (e.g. MySQL),
        # application-level enforcement remains in place.
        pass


def downgrade() -> None:
    """Downgrade schema changes."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute(sa.text("DROP INDEX IF EXISTS uq_sessions_member_active"))
    elif dialect == "postgresql":
        op.drop_index("uq_sessions_member_active", table_name="sessions")

    op.drop_column("sessions", "revoked_at")
