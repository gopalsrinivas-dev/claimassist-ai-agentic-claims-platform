"""Database foundation baseline. Intentionally creates no domain schema objects.

Alembic manages its own alembic_version table. Upgrade stamps this revision;
downgrade removes the revision marker. Business tables require separate migrations.
"""

revision: str = "20260921_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
