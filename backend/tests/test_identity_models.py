"""Identity mapping checks that require neither PostgreSQL nor its driver."""

from sqlalchemy import DateTime, UniqueConstraint, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.base import Base
from app.identity.models import Role, User, UserRole

SYNTHETIC_HASH = "SYNTHETIC_HASH"


def test_identity_metadata_contract() -> None:
    assert {User.__tablename__, Role.__tablename__, UserRole.__tablename__} == {
        "users",
        "roles",
        "user_roles",
    }
    users = Base.metadata.tables["users"]
    roles = Base.metadata.tables["roles"]
    assignments = Base.metadata.tables["user_roles"]
    assert set(users.c.keys()) == {
        "id",
        "email",
        "password_hash",
        "display_name",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert set(roles.c.keys()) == {"id", "code", "name"}
    assert list(assignments.primary_key.columns.keys()) == ["user_id", "role_id"]
    assert {fk.target_fullname for fk in assignments.foreign_keys} == {"users.id", "roles.id"}
    assert {index.name for index in assignments.indexes} == {"ix_user_roles_role_id"}
    for table, column in ((users, "email"), (roles, "code")):
        assert any(
            isinstance(constraint, UniqueConstraint) and list(constraint.columns.keys()) == [column]
            for constraint in table.constraints
        )
    for table in (users, roles, assignments):
        assert all(not column.nullable for column in table.c)
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "UUID" in ddl
    for name in ("created_at", "updated_at"):
        assert isinstance(users.c[name].type, DateTime)
        assert users.c[name].type.timezone is True


def test_assignment_relationships_and_safe_representation() -> None:
    user = User(
        email="synthetic@example.invalid", password_hash=SYNTHETIC_HASH, display_name="Test"
    )
    role = Role(code="SYNTHETIC_ROLE", name="Synthetic role")
    assignment = UserRole(user=user, role=role)
    assert user.user_roles == [assignment]
    assert role.user_roles == [assignment]
    assert assignment.user is user
    assert assignment.role is role
    assert "SYNTHETIC_HASH" not in repr(user)
    assert "synthetic@example.invalid" not in repr(user)
    assert inspect(User).relationships["user_roles"].passive_deletes == "all"
    assert inspect(Role).relationships["user_roles"].passive_deletes == "all"
